"""Konfiguration über Umgebungsvariablen; Secrets bevorzugt über ``*_FILE`` (Docker/Systemd-Secrets)."""
from __future__ import annotations

import ipaddress
import os
from pathlib import Path


def secret(name: str, env=os.environ) -> str:
    """Liest NAME oder NAME_FILE. Leere/fehlende Secrets sind ein Fehler (kein stiller Default)."""
    f = env.get(f"{name}_FILE")
    val = Path(f).read_text().strip() if f else env.get(name, "")
    if not val:
        raise SystemExit(f"Konfiguration: {name} oder {name}_FILE fehlt")
    return val


def check_bind(host: str, env=os.environ) -> str:
    """Erzwingt Loopback, außer ATLAS_ALLOW_NON_LOOPBACK=1 (bewusste Entscheidung, z. B. hinter Cloudflare Access)."""
    try:
        is_loop = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loop = False
    if not is_loop and env.get("ATLAS_ALLOW_NON_LOOPBACK") != "1":
        raise SystemExit(f"Bind-Adresse {host!r} ist nicht Loopback; ATLAS_ALLOW_NON_LOOPBACK=1 setzen, falls bewusst gewollt")
    return host
