"""UUIDv7 (RFC 9562) ohne externe Abhängigkeiten, monoton innerhalb eines Prozesses."""
from __future__ import annotations

import os
import threading
import time
import uuid

_lock = threading.Lock()
_last_ms = 0
_last_seq = 0


def uuid7() -> uuid.UUID:
    """Erzeugt eine UUIDv7: 48 Bit ms-Zeitstempel, 12 Bit Sequenz, 62 Bit Zufall."""
    global _last_ms, _last_seq
    with _lock:
        ms = time.time_ns() // 1_000_000
        if ms <= _last_ms:
            ms = _last_ms
            _last_seq += 1
            if _last_seq > 0xFFF:  # Sequenz erschöpft -> nächste Millisekunde
                ms += 1
                _last_seq = 0
        else:
            _last_seq = int.from_bytes(os.urandom(2), "big") & 0x3FF  # Platz für Zähler lassen
        _last_ms = ms
        seq = _last_seq
    rand = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    value = (ms << 80) | (0x7 << 76) | (seq << 64) | (0b10 << 62) | rand
    return uuid.UUID(int=value)


def is_uuid7(value: str) -> bool:
    try:
        u = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return u.version == 7 and u.variant == uuid.RFC_4122 and str(u) == value.lower()
