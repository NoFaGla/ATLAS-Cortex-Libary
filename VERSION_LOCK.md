# Version Lock

Stand: 2026-10-09.

| Komponente | Zielversion | Regel |
|---|---:|---|
| Paperless-ngx | 3.3.0 | gepinnt |
| PostgreSQL | 18 | gepinnt |
| Valkey | 9-alpine | gepinnt |
| Paperless-GPT | v0.30.0 | gepinnt; Update von v0.29.0 am 2026-10-12 (Sicherheitsfunde 8→2 HIGH), komplette GPT-/Restore-Testsuite bestanden (siehe `docs/DEVIATIONS.md` D22). Registry-Tag mit `v`-Präfix |

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
| `ghcr.io/icereed/paperless-gpt:v0.30.0` | `sha256:7cb0d9ebcc9d7711a1352ddc02e7fe0a93ef216ecc48d76a5ea83743b45f6974` |

Digest-Update nur bewusst (Sandbox-Test, Backup vorher). Prüfung: `tests/unit/test_repo_static.py::test_images_pinned_by_digest`.
