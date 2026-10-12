"""Statische Repo-Invarianten (ATLAS-Regeln) – laufen ohne Docker."""
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((ROOT / "compose/docker-compose.yml").read_text())


def test_no_latest_tags_and_images_pinned():
    for name, svc in COMPOSE["services"].items():
        img = svc["image"]
        assert "latest" not in img, name
        if "${" in img:
            img = re.search(r":-([^}]+)\}", img).group(1)
        assert re.search(r":v?[0-9][\w.\-]*$", img), f"{name}: Image nicht gepinnt: {img}"


def test_ports_bound_to_loopback_only():
    for name, svc in COMPOSE["services"].items():
        for p in svc.get("ports", []):
            assert str(p).startswith("127.0.0.1:"), f"{name}: Port nicht an Loopback: {p}"


def test_paperless_gpt_is_opt_in_profile():
    assert COMPOSE["services"]["paperless-gpt"]["profiles"] == ["ai"]
    assert COMPOSE["services"]["paperless-gpt"]["environment"]["AUTO_GENERATE_DOCUMENT_TYPE"] == "false"


def test_secrets_via_files_not_inline():
    text = (ROOT / "compose/docker-compose.yml").read_text()
    assert not re.search(r"(PASSWORD|SECRET_KEY|TOKEN|API_KEY):\s*[^\s$/]", text.replace("_FILE", ""))


def test_sandbox_paths_only():
    text = (ROOT / "compose/docker-compose.yml").read_text()
    assert "/srv/cortex" not in text.replace("/srv/cortex-library", "")  # keine produktiven Cortex-Pfade
    for line in text.splitlines():
        m = re.match(r"\s+- (/[^:]+):", line)
        if m:
            assert "atlas-sandbox" in m.group(1), line


def test_scripts_executable_with_strict_mode():
    for s in (ROOT / "scripts").glob("*.sh"):
        assert os.access(s, os.X_OK), s
        txt = s.read_text()
        assert txt.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in txt, s


def test_destructive_scripts_require_confirmation_flag():
    assert "--i-understand-this-deletes-the-sandbox" in (ROOT / "scripts/07-destroy-sandbox.sh").read_text()
    assert "--i-understand-this-replaces-the-sandbox" in (ROOT / "scripts/08-restore-sandbox.sh").read_text()


def test_destructive_scripts_touch_only_sandbox_paths():
    allowed = {"$SAFE", "$OPT", "$VAR", "$SEC", "$SRV", "{}", "+"}
    for s in ("07-destroy-sandbox.sh", "08-restore-sandbox.sh"):
        for m in re.finditer(r"rm -rf ([^;&|\n]+)", (ROOT / "scripts" / s).read_text()):
            for tok in m.group(1).split():
                assert tok.strip('"') in allowed, (s, tok)


def test_upload_requires_crypt_remote():
    assert '"crypt"' in (ROOT / "scripts/06-backup-sandbox.sh").read_text()


def test_no_private_files_tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    for f in out:
        assert not re.search(r"(^|/)\.env(\.|$)", f) or f.endswith(".env.example"), f
        assert not f.endswith((".pem", ".key", ".dump", ".zip")), f
        assert "rclone.conf" not in f


def test_no_secret_like_literals():
    pat = re.compile(r"(sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY)")
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    for f in files:
        p = ROOT / f
        if p.is_file():
            assert not pat.search(p.read_text(errors="ignore")), f


def test_env_examples_contain_only_placeholders():
    t = (ROOT / "compose/paperless-gpt.env.example").read_text()
    for line in t.splitlines():
        if re.match(r"(PAPERLESS_API_TOKEN|ANTHROPIC_API_KEY|LLM_MODEL)=", line):
            assert "REPLACE" in line
