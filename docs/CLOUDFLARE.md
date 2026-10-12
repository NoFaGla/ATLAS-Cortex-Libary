# Cloudflare Tunnel + Access (Vorlagen und automatische Prüfung)

Dateien: `deploy/cloudflare/cloudflared-config.yml.template`, `deploy/cloudflare/access-applications.json.template`.
Automatisch geprüft (`tests/unit/test_deploy.py`): Ursprung nur `http://127.0.0.1:{18000,18080,18090}`; letzte Ingress-Regel `http_status:404`;
keine Wildcard-Hostnames, kein `noTLSVerify`; jede veröffentlichte Domain hat eine Access-Application und umgekehrt; keine `bypass`-Policy; Menschen:
konkrete E-Mail **plus** Passkey (`swk`) bzw. MFA; Maschinen (library-read): genau ein benanntes Service-Token (kein `any_valid_service_token`, kein
`everyone`, keine IP-Regel); Sitzungsdauer ≤ 12 h; keine Secrets in den Vorlagen.

**Nicht automatisch prüfbar (bleibt für ATLAS):** reale Tunnel-Verbindung, IdP-/MFA-Konfiguration im Cloudflare-Konto, tatsächliche Durchsetzung von Access.

## Einrichtung (Betreiber)
1. Tunnel anlegen: `cloudflared tunnel create atlas-m03` (Credentials-Datei 0600 außerhalb des Repos).
2. Vorlagen kopieren, `<...>` ersetzen, Access-Applications über Dashboard/API anlegen (Policy je Dienst wie in der Vorlage).
3. `cloudflared` als systemd-Dienst starten; danach von außen prüfen: ohne Login → Access-Anmeldeseite, nicht Paperless; direkter Zugriff auf `http://<server>:18000` von anderen Hosts → nicht erreichbar.
4. `library-read` nur mit Service-Token freigeben; Token-ID in die Policy eintragen; Token-Secret nur beim Client.
