"""Automatisierte Konfigurationsprüfungen: Cloudflare Tunnel/Access, systemd-Härtung, Compose-Isolation."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CF = ROOT / "deploy/cloudflare"
SD = ROOT / "deploy/systemd"
ALLOWED_ORIGIN_PORTS = {18000, 18080, 18090}


def test_cloudflared_ingress_only_loopback_and_catch_all_404():
    cfg = yaml.safe_load((CF / "cloudflared-config.yml.template").read_text())
    ingress = cfg["ingress"]
    assert ingress[-1] == {"service": "http_status:404"}, "letzte Regel muss 404-Catch-all sein"
    hosts = set()
    for rule in ingress[:-1]:
        assert re.fullmatch(r"http://127\.0\.0\.1:(\d+)", rule["service"]), rule
        assert int(rule["service"].rsplit(":", 1)[1]) in ALLOWED_ORIGIN_PORTS
        assert rule["hostname"].startswith("<") and "*" not in rule["hostname"], "kein Wildcard-Hostname"
        assert rule["hostname"] not in hosts
        hosts.add(rule["hostname"])
        assert "originRequest" not in rule or "noTLSVerify" not in rule["originRequest"]
    assert "noTLSVerify" not in json.dumps(cfg)
    assert cfg.get("no-autoupdate") is True


def test_cloudflare_access_policies_require_strong_auth():
    apps = json.loads((CF / "access-applications.json.template").read_text())["applications"]
    assert len(apps) >= 3
    ingress_hosts = {r["hostname"] for r in yaml.safe_load((CF / "cloudflared-config.yml.template").read_text())["ingress"][:-1]}
    assert {a["domain"] for a in apps} == ingress_hosts, "jeder veröffentlichte Hostname braucht eine Access-Application (und umgekehrt)"
    for a in apps:
        assert a["type"] == "self_hosted" and a["http_only_cookie_attribute"] is True and a["policies"]
        for pol in a["policies"]:
            assert pol["decision"] in ("allow", "non_identity"), "bypass ist verboten"
            inc = json.dumps(pol["include"])
            assert "everyone" not in inc and "any_valid_service_token" not in inc and '"ip"' not in inc
            if pol["decision"] == "allow":  # Menschen: konkrete Identität + Passkey (swk) bzw. MFA
                assert "email" in inc and any(k in json.dumps(pol["require"]) for k in ("swk", "mfa"))
            else:  # Maschinen: genau ein benanntes Service-Token
                assert re.search(r'"service_token": \{"token_id"', inc)
        assert int(a["session_duration"].rstrip("h")) <= 12


def test_templates_contain_no_secrets():
    for f in list(CF.glob("*")) + list(SD.glob("*")):
        t = f.read_text()
        assert not re.search(r"eyJ[A-Za-z0-9_-]{20,}|[A-Fa-f0-9]{40,}|AccountTag|TunnelSecret", t), f


@pytest.mark.parametrize("unit", ["atlas-library-read", "atlas-library-ingest"])
def test_systemd_unit_hardening(unit):
    t = (SD / f"{unit}.service.template").read_text()
    for must in ("NoNewPrivileges=yes", "ProtectSystem=strict", "ProtectHome=yes", "PrivateTmp=yes", "PrivateDevices=yes",
                 "CapabilityBoundingSet=", "RestrictAddressFamilies=AF_INET AF_INET6", "MemoryDenyWriteExecute=yes",
                 "IPAddressDeny=any", "IPAddressAllow=localhost", "LockPersonality=yes", "RestrictSUIDSGID=yes", "SystemCallFilter=@system-service"):
        assert must in t, f"{unit}: {must} fehlt"
    assert "User=@SERVICE_USER@" in t and "User=root" not in t
    assert "LoadCredential=" in t and "_TOKEN_FILE=%d/" in t  # Secrets nur über Credentials, nie inline
    assert not re.search(r"Environment=\S*TOKEN=\S", t)
    assert "ATLAS_ALLOW_NON_LOOPBACK" not in t
    if unit.endswith("read"):
        assert "ReadWritePaths" not in t and "ReadOnlyPaths=" in t  # library-read hat keinen Schreibzugriff


def test_systemd_units_render_and_verify(tmp_path):
    if not shutil.which("systemd-analyze"):
        pytest.skip("systemd-analyze fehlt")
    for unit in ("atlas-library-read", "atlas-library-ingest"):
        t = (SD / f"{unit}.service.template").read_text()
        for k, v in {"@SERVICE_USER@": "root", "@SERVICE_GROUP@": "root", "@OPT@": "/opt/x", "@VAR@": "/var/x", "@SRV@": "/srv/x",
                     "@SEC@": "/etc/x", "@GPT_ENABLED@": "0"}.items():
            t = t.replace(k, v)
        assert not re.search(r"@[A-Z_]+@", t), "nicht ersetzte Platzhalter"
        (tmp_path / f"{unit}.service").write_text(t)
    r = subprocess.run(["systemd-analyze", "verify", "--man=no", str(tmp_path / "atlas-library-read.service"), str(tmp_path / "atlas-library-ingest.service")],
                       capture_output=True, text=True)
    bad = [l for l in r.stderr.splitlines() if re.search(r"Unknown (key|section)|Invalid|syntax|bad", l, re.I)]
    assert not bad, bad


def test_compose_container_isolation_flags():
    c = yaml.safe_load((ROOT / "compose/docker-compose.yml").read_text())
    for name, svc in c["services"].items():
        assert svc.get("privileged") is not True and svc.get("network_mode") not in ("host", None) or "network_mode" not in svc, name
        assert "pid" not in svc and "ipc" not in svc and not svc.get("cap_add"), name
        assert "no-new-privileges:true" in svc.get("security_opt", []), f"{name}: no-new-privileges fehlt"
        for v in svc.get("volumes", []):
            src = v.split(":")[0] if isinstance(v, str) else v.get("source", "")
            assert "docker.sock" not in src and src not in ("/", "/etc", "/root", "/home"), (name, v)
