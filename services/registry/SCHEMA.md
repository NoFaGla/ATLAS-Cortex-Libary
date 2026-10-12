# library-registry

Erst nach Core-Abnahme implementieren.

```text
atlas_id       UUIDv7 PRIMARY KEY
kind           document | asset
backend        paperless | asset-store
backend_id     nullable
relative_path  nullable
status         active | trashed | deleted
created_at     timestamp
current_hash   sha256
mime_type      nullable
last_title     nullable
```

Regeln: ID nie wiederverwenden; Paperless-ID nur Backend-ID; Tombstone bei Hard Delete; keine Dokumentkopien.
