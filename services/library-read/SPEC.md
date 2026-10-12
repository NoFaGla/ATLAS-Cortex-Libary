# library-read

Read-only Adapter. Erst nach Core-Abnahme.

```text
search_documents(...)
resolve_atlas_ref(ref)
get_document_metadata(ref)
get_document_text(ref)
get_document_file(ref)
get_asset(ref)
```

Retrieval: ID -> strukturierte Metadaten -> Volltext -> Snippet -> OCR -> Datei.

Keine Lösch-/Merge-/PDF-Edit-/User-/Workflow-Funktionen.
