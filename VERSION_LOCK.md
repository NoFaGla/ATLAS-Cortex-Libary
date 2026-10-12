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
