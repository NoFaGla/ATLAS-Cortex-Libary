# Image-Schwachstellenscan (Trivy 0.58.0, Stand 2026-10-12) — Gate G7b

Gescannt: die **gepinnten** Upstream-Images (Digests siehe `VERSION_LOCK.md`), Schweregrad HIGH/CRITICAL, nur Funde **mit verfügbarem Fix** (`--ignore-unfixed`); Zahlen sind **eindeutige CVE-IDs**.
Befehl: `trivy image --severity HIGH,CRITICAL --ignore-unfixed <image@digest>` (CI-Job `image-scan`, informativ, blockiert nicht – wir bauen diese Images nicht selbst).
Der Scan vom 2026-10-12 vor der Bereinigung (zählte Paketzeilen statt CVE-IDs: 9 / 10 / 24+1) wurde reproduziert und stimmt mit den Funden unten überein.

## Ergebnis nach Bereinigung
| Image (gepinnt) | CRITICAL | HIGH | Veränderung |
|---|---|---|---|
| paperless-ngx 3.3.0 | 0 | 3 | unverändert – 3.3.0 ist die **neueste** Version, der Tag-Digest ist seit dem Pin unverändert |
| paperless-gpt **v0.30.0** | 0 | 2 | **behoben: 8 → 2 HIGH** (Update von v0.29.0, D22) |
| valkey 9-alpine | 0 | 0 | sauber |
| postgres 18 (= 18.6) | 1 | 24 | unverändert – 18.6 ist die **neueste** Version; Alpine-Variante hat dieselben Funde |

## Maßnahmen dieses Laufs
1. **Digests geprüft:** Alle vier Tags zeigen weiterhin auf die gepinnten Digests; kein stiller Rebuild mit Sicherheitsfixes verfügbar (`postgres:18` ≙ `18.6`).
2. **paperless-gpt v0.29.0 → v0.30.0** (nur Minor-Sprung in 0.x). Nachweis: Smoke, GPT-Mock (12 Szenarien inkl. D20), E2E, Restore-E2E gegen das neue Image – siehe `TESTREPORT.md`.
3. **postgres:18-alpine geprüft und verworfen:** enthält dasselbe `gosu`-Binary (go1.24.6) → identische 1 CRITICAL / 24 HIGH, aber musl statt glibc (Collation-/Locale-Unterschiede zu Debian-Datenbanken) – Risiko ohne Nutzen.
4. **Nicht gebaut:** Ein eigenes abgeleitetes Image (`FROM paperless-ngx` + `apt upgrade ghostscript`) wurde bewusst *nicht* erstellt (Pin per Digest nicht mehr möglich, Build auf dem Zielhost, eigene Wartungspflicht). Siehe Option unten.

## Verbleibende Funde
### paperless-ngx 3.3.0 — 3 HIGH (kein Fix upstream verfügbar)
- HIGH CVE-2026-101258: ghostscript 10.05.1~dfsg-1+deb13u2, libgs-common 10.05.1~dfsg-1+deb13u2, libgs10 10.05.1~dfsg-1+deb13u2, libgs10-common 10.05.1~dfsg-1+deb13u2 → 10.05.1~dfsg-1+deb13u3
- HIGH CVE-2026-103226: ghostscript 10.05.1~dfsg-1+deb13u2, libgs-common 10.05.1~dfsg-1+deb13u2, libgs10 10.05.1~dfsg-1+deb13u2, libgs10-common 10.05.1~dfsg-1+deb13u2 → 10.05.1~dfsg-1+deb13u3
- HIGH CVE-2026-104851: fsspec 2026.1.0 → 2026.6.0

- **Betroffen:** Ghostscript (Debian 13.7) wird von OCRmyPDF/Paperless beim Verarbeiten von PDFs benutzt; `fsspec` ist eine Python-Abhängigkeit.
- **Risiko:** mittel für Ghostscript (manipulierte PDF → Codeausführung/Absturz im Container, abhängig vom konkreten CVE), niedrig für `fsspec` (wird von Paperless nicht mit fremden URLs betrieben).
- **Begründung der Akzeptanz:** Der Fix ist ein Debian-Paketupdate (`deb13u3`), das erst mit einem neuen Paperless-Release im Image landet; ein neueres Release als 3.3.0 gibt es nicht. Importiert werden nur eigene, vertrauenswürdige Dokumente über authentifizierte Wege.
- **Kompensierend:** Container ohne Privilegien/Capabilities, `no-new-privileges`, kein Docker-Socket, nur Loopback, DB/Valkey ohne veröffentlichte Ports, Cloudflare Access davor, Backup vorhanden.
- **Auflage bis zur Behebung:** keine fremden/unsicheren PDFs importieren (E-Mail-Anhänge unbekannter Absender, Downloads aus unsicheren Quellen).
- **Maßnahme:** Beim nächsten Paperless-Release (3.3.x/3.4) Digest-Update mit denselben Tests, danach Scan wiederholen. Wöchentlicher Scan über den CI-Job `image-scan`.
- **Option (Entscheidung Betreiber):** dünnes abgeleitetes Image mit aktualisiertem Ghostscript – nur wenn Ghostscript-Risiko vor dem nächsten Paperless-Release nicht tragbar ist.

### paperless-gpt v0.30.0 — 2 HIGH
- HIGH CVE-2026-7482: github.com/ollama/ollama v0.13.5 → 0.17.1
- HIGH CVE-2026-78669: golang.org/x/net v0.59.0 → 0.60.0

- `ollama`: nur relevant, wenn Ollama als LLM-Anbieter genutzt wird. ATLAS nutzt OpenAI/Anthropic (`LLM_PROVIDER`), der Ollama-Codepfad ist inaktiv. Risiko: niedrig.
- `golang.org/x/net`: betrifft HTTP/2-Serverpfade; der Dienst lauscht nur auf 127.0.0.1 hinter Cloudflare Access. Risiko: niedrig bis mittel.
- **Maßnahme:** nächstes paperless-gpt-Release beobachten (Update nur nach eigenem Sandbox-Test).

### postgres 18 — 1 CRITICAL, 24 HIGH (alle ausschließlich im Binary `usr/local/bin/gosu`)
- CRITICAL CVE-2025-68121: stdlib v1.24.6 → 1.24.13, 1.25.7, 1.26.0-rc.3
- HIGH CVE-2025-61726: stdlib v1.24.6 → 1.24.12, 1.25.6
- HIGH CVE-2025-61729: stdlib v1.24.6 → 1.24.11, 1.25.5
- HIGH CVE-2026-25679: stdlib v1.24.6 → 1.25.8, 1.26.1
- HIGH CVE-2026-27145: stdlib v1.24.6 → 1.25.11, 1.26.4
- HIGH CVE-2026-32280: stdlib v1.24.6 → 1.25.9, 1.26.2
- HIGH CVE-2026-32281: stdlib v1.24.6 → 1.25.9, 1.26.2
- HIGH CVE-2026-32283: stdlib v1.24.6 → 1.25.9, 1.26.2
- HIGH CVE-2026-33811: stdlib v1.24.6 → 1.25.10, 1.26.3
- HIGH CVE-2026-33814: stdlib v1.24.6 → 1.25.10, 1.26.3
- HIGH CVE-2026-33818: stdlib v1.24.6 → 1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-39820: stdlib v1.24.6 → 1.25.10, 1.26.3
- HIGH CVE-2026-39821: stdlib v1.24.6 → 1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-39822: stdlib v1.24.6 → 1.25.12, 1.26.5, 1.27.0-rc.2
- HIGH CVE-2026-39836: stdlib v1.24.6 → 1.25.10, 1.26.3
- HIGH CVE-2026-42499: stdlib v1.24.6 → 1.25.10, 1.26.3
- HIGH CVE-2026-42504: stdlib v1.24.6 → 1.25.11, 1.26.4
- HIGH CVE-2026-56853: stdlib v1.24.6 → 1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-56858: stdlib v1.24.6 → 1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-56859: stdlib v1.24.6 → 1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-56860: stdlib v1.24.6 → 1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-56862: stdlib v1.24.6 → 1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-78667: stdlib v1.24.6 → 1.26.9, 1.27.2
- HIGH CVE-2026-78669: stdlib v1.24.6 → 1.26.9, 1.27.2
- HIGH CVE-2026-97031: stdlib v1.24.6 → 1.26.9, 1.27.2

- **Alle** Funde betreffen die Go-Standardbibliothek (go1.24.6) im Helfer `gosu`, das beim Containerstart die Rechte absenkt und `postgres` per `exec` startet. Der Datenbankserver selbst (C, Debian-Pakete) hat **keine** fixbaren HIGH/CRITICAL-Funde.
- **Risiko:** niedrig – `gosu` läuft nur beim Start, ohne Netzwerk-/Dateneingabe; die betroffenen Pfade (`net/http`, `crypto/x509`, `archive/*` …) werden von `gosu` nicht verwendet. (Einschätzung, keine Erreichbarkeitsanalyse des Binaries.)
- **Kompensierend:** DB nur im internen Docker-Netz, kein veröffentlichter Port, `no-new-privileges`, Passwort per Secret-Datei.
- **Maßnahme:** Beim nächsten Postgres-18.x-Image (neues `gosu`) Digest-Update mit Restore-Test; **kein** Major-Upgrade (VERSION_LOCK-Regel).

## Gesamtbewertung für Gate G7b
- Alle **fixbaren** Funde, für die upstream ein getestetes Update existiert, sind behoben (paperless-gpt).
- Für die übrigen existiert upstream noch kein gefixtes Image; sie sind oben mit Risiko, Begründung und Maßnahme dokumentiert und werden durch den wiederkehrenden CI-Scan überwacht.
- **G7b: dokumentiert akzeptiert (Restrisiko), nicht „null Funde“.** Die Produktionsfreigabe erfordert die ausdrückliche Kenntnisnahme dieses Restrisikos durch den Betreiber.
