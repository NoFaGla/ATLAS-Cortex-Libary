# PREP – vor dem Sandbox-Build

Keine echten Secret-Werte in diese Datei schreiben.

| ID | Vorbereitung | Status/Notiz |
|---|---|---|
| M03-01 | Sandbox-Paperless-Adminname (Default `atlas-admin`) | |
| M03-02 | erster Paperless-GPT Provider: Claude oder GPT | |
| M03-03 | API-Key für gewählten Provider | nur Secret-Datei |
| M03-04 | OneDrive-Konto erreichbar | |
| M03-05 | Zielordner `ATLAS-Backup` akzeptiert | |
| M03-06 | rclone-crypt Recovery-Key extern gesichert | |
| M03-07 | optionaler Cloudflare-Testhostname | |
| M03-08 | 15–20 Testdokument-Kopien | |
| M03-09 | Testassets: SVG, PNG/Icon, Vorlage | |
| M03-10 | mindestens 20 GiB freie Kapazität | |

Bootstrap erzeugt:

```text
/etc/atlas/secrets/module03-sandbox/postgres_password
/etc/atlas/secrets/module03-sandbox/paperless_secret_key
/etc/atlas/secrets/module03-sandbox/paperless_admin_password
/etc/atlas/secrets/module03-sandbox/paperless_admin_user
/etc/atlas/secrets/module03-sandbox/paperless-gpt.env
/etc/atlas/secrets/module03-sandbox/rclone.conf   # später manuell
```
