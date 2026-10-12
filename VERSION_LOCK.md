# Version Lock

Stand: 2026-10-09.

| Komponente | Zielversion | Regel |
|---|---:|---|
| Paperless-ngx | 3.3.0 | gepinnt |
| PostgreSQL | 18 | gepinnt |
| Valkey | 9-alpine | gepinnt |
| Paperless-GPT | v0.29.0 | Ziel; Manifest am 2026-10-12 auf ghcr.io verifiziert (Tag `0.29.0` ohne `v` existiert nicht) |

## Regel

- Paperless-Update != PostgreSQL-Major-Upgrade
- Paperless-Update != Valkey-Major-Upgrade
- Paperless-GPT-Update nur nach eigenem Sandbox-Test
- vor Upgrade vollständiges Backup
- kein `latest` im validierten Release

## Image-Digests (Index-Manifest, verifiziert 2026-10-12)

Compose und `compose/.env.example` pinnen `tag@sha256`. Der Tag dient der Lesbarkeit, der Digest ist maßgeblich.

| Image | Digest |
|---|---|
| `docker.io/valkey/valkey:9-alpine` | `sha256:48332870af354a799964c0012ae1194a0bf2bf894eb508f945810596dc2d8d11` |
| `docker.io/library/postgres:18` | `sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` |
| `ghcr.io/paperless-ngx/paperless-ngx:3.3.0` | `sha256:6b94799bc769a063b3340cc5847402e626d4d91d29a295a8e747f8e9bead4207` |
| `ghcr.io/icereed/paperless-gpt:v0.29.0` | `sha256:4127ea223e0f496c1075a3a05661df4847140974c3c3ce89a4ba991be50320cb` |

Digest-Update nur bewusst (Sandbox-Test, Backup vorher). Prüfung: `tests/unit/test_repo_static.py::test_images_pinned_by_digest`.
