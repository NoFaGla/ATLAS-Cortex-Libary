# Image-Schwachstellenscan (Trivy 0.58.0, 2026-10-12)

Gescannt: die vier **gepinnten** Upstream-Images (Digests siehe `VERSION_LOCK.md`), Schweregrad HIGH/CRITICAL, nur Funde **mit verfügbarem Fix** (`--ignore-unfixed`).
Befehl: `trivy image --severity HIGH,CRITICAL --ignore-unfixed <image@digest>` (CI-Job `image-scan`, informativ, blockiert nicht – wir bauen diese Images nicht selbst).

| Image | CRITICAL | HIGH |
|---|---|---|
| paperless-ngx 3.3.0 | 0 | 9 |
| paperless-gpt v0.29.0 | 0 | 10 |
| valkey 9-alpine | 0 | 0 |
| postgres 18 | 1 | 24 |

### paperless-ngx 3.3.0

- HIGH CVE-2026-101258: ghostscript 10.05.1~dfsg-1+deb13u2→10.05.1~dfsg-1+deb13u3, libgs-common 10.05.1~dfsg-1+deb13u2→10.05.1~dfsg-1+deb13u3, libgs10 10.05.1~dfsg-1+deb13u2→10.05.1~df
- HIGH CVE-2026-103226: ghostscript 10.05.1~dfsg-1+deb13u2→10.05.1~dfsg-1+deb13u3, libgs-common 10.05.1~dfsg-1+deb13u2→10.05.1~dfsg-1+deb13u3, libgs10 10.05.1~dfsg-1+deb13u2→10.05.1~df
- HIGH CVE-2026-104851: fsspec 2026.1.0→2026.6.0

### paperless-gpt v0.29.0

- HIGH CVE-2025-59530: github.com/quic-go/quic-go v0.54.0→0.49.1, 0.54.1
- HIGH CVE-2026-14456: libcrypto3 3.5.7-r0→3.5.8-r0, libssl3 3.5.7-r0→3.5.8-r0
- HIGH CVE-2026-46602: golang.org/x/image v0.32.0→0.43.0
- HIGH CVE-2026-46603: golang.org/x/image v0.32.0→0.45.0
- HIGH CVE-2026-7482: github.com/ollama/ollama v0.13.5→0.17.1
- HIGH CVE-2026-78667: stdlib v1.27.1→1.26.9, 1.27.2
- HIGH CVE-2026-78669: golang.org/x/net v0.59.0→0.60.0, stdlib v1.27.1→1.26.9, 1.27.2
- HIGH CVE-2026-97031: stdlib v1.27.1→1.26.9, 1.27.2

### postgres 18

- CRITICAL CVE-2025-68121: stdlib v1.24.6→1.24.13, 1.25.7, 1.26.0-rc.3
- HIGH CVE-2025-61726: stdlib v1.24.6→1.24.12, 1.25.6
- HIGH CVE-2025-61729: stdlib v1.24.6→1.24.11, 1.25.5
- HIGH CVE-2026-25679: stdlib v1.24.6→1.25.8, 1.26.1
- HIGH CVE-2026-27145: stdlib v1.24.6→1.25.11, 1.26.4
- HIGH CVE-2026-32280: stdlib v1.24.6→1.25.9, 1.26.2
- HIGH CVE-2026-32281: stdlib v1.24.6→1.25.9, 1.26.2
- HIGH CVE-2026-32283: stdlib v1.24.6→1.25.9, 1.26.2
- HIGH CVE-2026-33811: stdlib v1.24.6→1.25.10, 1.26.3
- HIGH CVE-2026-33814: stdlib v1.24.6→1.25.10, 1.26.3
- HIGH CVE-2026-33818: stdlib v1.24.6→1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-39820: stdlib v1.24.6→1.25.10, 1.26.3
- HIGH CVE-2026-39821: stdlib v1.24.6→1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-39822: stdlib v1.24.6→1.25.12, 1.26.5, 1.27.0-rc.2
- HIGH CVE-2026-39836: stdlib v1.24.6→1.25.10, 1.26.3
- HIGH CVE-2026-42499: stdlib v1.24.6→1.25.10, 1.26.3
- HIGH CVE-2026-42504: stdlib v1.24.6→1.25.11, 1.26.4
- HIGH CVE-2026-56853: stdlib v1.24.6→1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-56858: stdlib v1.24.6→1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-56859: stdlib v1.24.6→1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-56860: stdlib v1.24.6→1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-56862: stdlib v1.24.6→1.25.13, 1.26.6, 1.27.0-rc.3
- HIGH CVE-2026-78667: stdlib v1.24.6→1.26.9, 1.27.2
- HIGH CVE-2026-78669: stdlib v1.24.6→1.26.9, 1.27.2
- HIGH CVE-2026-97031: stdlib v1.24.6→1.26.9, 1.27.2

## Bewertung (Stand heute)
- Alle Funde liegen in **Upstream-Images** (Debian/Alpine-Pakete, Go-Standardbibliothek in `gosu`/Binärdateien). Es gibt Fixes in neueren Image-Builds, die wir **bewusst nicht** still übernehmen (Regel: keine stillen Versionsupgrades).
- Kompensierende Kontrollen: nur Loopback-Ports, `no-new-privileges`, keine Capabilities/Privilegien, kein Docker-Socket, PostgreSQL/Valkey ohne veröffentlichte Ports (nur internes Netz), Importweg nur für authentifizierte, eigene Dokumente.
- Relevanz: ghostscript (Paperless) betrifft die Verarbeitung manipulierter PDFs → **nur eigene/vertrauenswürdige Dokumente importieren**, bis ein Digest-Update getestet ist.
- **Maßnahme vor produktiver Nutzung:** Digests der betroffenen Tags erneut prüfen (neuere Rebuilds), in der Sandbox testen (`restore-e2e`, `e2e`), `VERSION_LOCK.md` aktualisieren, Scan wiederholen. Das ist ein bewusstes Update, kein automatisches.
- Der PostgreSQL-CRITICAL (`CVE-2025-68121`, Go-stdlib des mitgelieferten `gosu`) betrifft einen Helfer beim Containerstart, nicht den Datenbankserver im Betrieb.
