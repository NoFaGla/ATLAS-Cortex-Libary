"""Parser für atlas-library://<uuidv7>[@sha256:<hash>]."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .uuid7 import is_uuid7

_REF = re.compile(r"^atlas-library://([0-9a-f-]{36})(?:@sha256:([0-9a-f]{64}))?$")


class InvalidRef(ValueError):
    pass


@dataclass(frozen=True)
class Ref:
    atlas_id: str
    sha256: str | None = None

    def __str__(self) -> str:
        base = f"atlas-library://{self.atlas_id}"
        return f"{base}@sha256:{self.sha256}" if self.sha256 else base


def parse_ref(text: str) -> Ref:
    if not isinstance(text, str):
        raise InvalidRef("Referenz muss ein String sein")
    m = _REF.match(text.strip())
    if not m or not is_uuid7(m.group(1)):
        raise InvalidRef(f"Ungültige ATLAS-Referenz: {text!r}")
    return Ref(m.group(1), m.group(2))
