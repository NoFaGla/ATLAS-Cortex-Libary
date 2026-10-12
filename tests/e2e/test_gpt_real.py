"""Echter LLM (OpenAI/Anthropic) hinter Paperless-GPT — nur über tests/integration/gpt-real-llm.sh mit ausdrücklicher Freigabe.
Bewusst tolerante Qualitätsprüfungen (LLM-Ausgaben sind nicht deterministisch); harte Prüfungen nur für Sicherheits-/Integritätsregeln."""
import hashlib
import json
import os
import re
from pathlib import Path

import pytest

from tests.e2e.test_gpt_mock import (DONE, ING, QUEUE, URL, assert_taxonomy_intact, ingest, link, settle, state, w)  # noqa: F401 (Fixture w)

REPORT = os.environ.get("ATLAS_E2E_REPORT")
pytestmark = pytest.mark.skipif(not URL or os.environ.get("M03_REAL_LLM") != "1", reason="kein Freigabe-Flag M03_REAL_LLM=1")


def test_real_llm_metadata_extraction_is_sane_and_safe(w):  # noqa: F811
    docs = {t: ingest(w, t) for t in ("T01", "T06", "T07")}
    link(w, [a for a, _ in docs.values()])
    assert settle(w, [a for a, _ in docs.values()], 600), "kein Endzustand"
    rep = {}
    for tid, (aid, sha) in docs.items():
        s = state(w, aid)
        rep[tid] = {k: (sorted(v) if isinstance(v, set) else v) for k, v in s.items() if k != "fields"}
        assert s["title"] and 5 <= len(s["title"]) <= 128
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["created"])
        assert s["type"] is None                       # Dokumenttyp wird nie automatisch gesetzt (Architekturentscheidung)
        assert (DONE in s["tags"]) or ("Status/Prüfen" in s["tags"])
        assert hashlib.sha256(w["wc"].download_original(s["id"])).hexdigest() == sha   # Original unverändert
    assert_taxonomy_intact(w)                          # keine erfundenen Tags/Dokumenttypen
    if REPORT:
        Path(REPORT).write_text(json.dumps(rep, indent=2, ensure_ascii=False, sort_keys=True))
