"""Deterministische, vollständig synthetische Testdokumente T01–T17 (keine echten Personen/Firmen/Daten).

``python -m atlas_library.synthetic <ausgabeverzeichnis>`` schreibt Dateien + ``manifest.json`` mit den
erwarteten Eigenschaften. Alle Namen sind frei erfunden („Muster…“, „Beispiel…“).
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

DOC_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _esc(s: str) -> bytes:
    return s.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def text_pdf(pages: list[list[str]]) -> bytes:
    """Minimaler, deterministischer Text-PDF-Writer (Helvetica, WinAnsi => Umlaute)."""
    objs: list[bytes] = []
    kids = []
    n_pages = len(pages)
    font_id = 3 + 2 * n_pages
    for i, lines in enumerate(pages):
        content = b"BT /F1 11 Tf 14 TL 50 790 Td\n" + b"".join(b"(" + _esc(l) + b") Tj T*\n" for l in lines) + b"ET"
        page_id, cont_id = 3 + 2 * i, 4 + 2 * i
        kids.append(f"{page_id} 0 R")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {cont_id} 0 R "
                    f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    head = [b"<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {n_pages} >>".encode()]
    allobjs = head + objs
    out = b"%PDF-1.4\n"
    offs = []
    for i, o in enumerate(allobjs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(allobjs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(allobjs) + 1, x)
    return out


def _render(lines: list[str], *, noisy: bool = False, size=(1240, 1754)):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    img = Image.new("L", size, 255)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(DOC_FONT, 30 if not noisy else 26)
    y = 100
    for line in lines:
        d.text((90, y), line, fill=20, font=font)
        y += 46
    if noisy:  # schlechter Scan: Rotation, Unschärfe, Rauschen, Kontrastverlust (deterministisch)
        rnd = random.Random(42)
        img = img.rotate(1.8, expand=False, fillcolor=255).filter(ImageFilter.GaussianBlur(1.3))
        px = img.load()
        for _ in range(size[0] * size[1] // 25):
            x, yy = rnd.randrange(size[0]), rnd.randrange(size[1])
            px[x, yy] = max(0, min(255, px[x, yy] + rnd.randint(-70, 70)))
        img = img.point(lambda v: 60 + int(v * 0.65))
    return img


def image_pdf(pages: list[list[str]], **kw) -> bytes:
    import io
    imgs = [_render(p, **kw).convert("RGB") for p in pages]
    buf = io.BytesIO()
    imgs[0].save(buf, "PDF", save_all=True, append_images=imgs[1:], resolution=150.0)
    return _normalize_pdf(buf.getvalue())


def image_png(lines: list[str], **kw) -> bytes:
    import io
    buf = io.BytesIO()
    _render(lines, **kw).save(buf, "PNG")
    return buf.getvalue()


def _normalize_pdf(b: bytes) -> bytes:
    import re
    return re.sub(rb"/(CreationDate|ModDate) \(D:[^)]*\)", b"", b)


def _wage(month: str, iso: str, brutto: str) -> list[str]:
    return ["Muster Arbeitgeber GmbH", "Beispielstraße 1, 12345 Beispielstadt", "",
            f"Verdienstabrechnung {month}", f"Abrechnungsdatum: {iso}", "Mitarbeiter: Erika Mustermann (synthetisch)",
            f"Bruttoverdienst: {brutto} EUR", "Dies ist ein synthetisches Testdokument."]


def build() -> dict[str, dict]:
    """Gibt {dateiname: {data, meta}} zurück."""
    docs: dict[str, dict] = {}

    def add(tid, fname, data, **meta):
        docs[fname] = {"data": data, "meta": {"id": tid, "file": fname, **meta}}

    t01 = text_pdf([_wage("Januar 2026", "31.01.2026", "3.000,00")])
    add("T01", "T01_verdienstabrechnung_2026-01.pdf", t01, doctype="Abrechnung", correspondent="Muster Arbeitgeber GmbH",
        date="2026-01-31", precision="Tag", contains=["Verdienstabrechnung Januar 2026"], series="wage")
    add("T02", "T02_verdienstabrechnung_2026-02.pdf", text_pdf([_wage("Februar 2026", "28.02.2026", "3.000,00")]),
        doctype="Abrechnung", correspondent="Muster Arbeitgeber GmbH", date="2026-02-28", precision="Tag",
        contains=["Verdienstabrechnung Februar 2026"], series="wage")
    vertrag = ["Dienstleistungsvertrag", "zwischen Beispiel Beratung AG und Musterfirma GmbH", "Datum: 15.03.2025", ""]
    vertrag += [f"§ {i} Leistungsumfang Absatz {i}: Die Parteien vereinbaren synthetische Leistungen Nummer {i}." for i in range(1, 25)]
    t03_pages = [vertrag[:14], vertrag[14:]]
    t03 = text_pdf(t03_pages)
    add("T03", "T03_dienstleistungsvertrag.pdf", t03, doctype="Vertrag", correspondent="Beispiel Beratung AG",
        date="2025-03-15", precision="Tag", contains=["Dienstleistungsvertrag", "Leistungsumfang"], pages=2)
    add("T04", "T04_mietvertrag.pdf", text_pdf([["Mietvertrag", "Vermieter: Beispiel Wohnbau GmbH", "Mieter: Max Mustermann (synthetisch)",
                                                 "Mietbeginn: 01.07.2024", "Kaltmiete: 850,00 EUR", "Objekt: Musterweg 5, 12345 Beispielstadt"]]),
        doctype="Vertrag", correspondent="Beispiel Wohnbau GmbH", date="2024-07-01", precision="Tag",
        contains=["Mietvertrag", "Kaltmiete"], tags=["Kontext/Wohnen"])
    add("T05", "T05_betriebskostenabrechnung.pdf", text_pdf([["Beispiel Wohnbau GmbH", "Betriebskostenabrechnung", "Abrechnungsmonat: März 2026",
                                                              "Abrechnungszeitraum: 01.01.2025 bis 31.12.2025", "Nachzahlung: 1.234,56 EUR",
                                                              "Fällig bis: 30.04.2026"]]),
        doctype="Abrechnung", correspondent="Beispiel Wohnbau GmbH", date="2026-03", precision="Monat",
        contains=["Betriebskostenabrechnung", "1.234,56"], betrag="1234.56", tags=["Kontext/Wohnen", "Thema/Finanzen"])
    add("T06", "T06_bescheid.pdf", text_pdf([["Beispielstadt Finanzamt (synthetisch)", "Steuerbescheid", "Datum: 10.04.2026",
                                              "Aktenzeichen: AZ-2026-0042", "Festgesetzte Steuer: 1.000,00 EUR"]]),
        doctype="Bescheid", correspondent="Finanzamt Beispielstadt", date="2026-04-10", precision="Tag",
        contains=["Steuerbescheid", "AZ-2026-0042"], aktenzeichen="AZ-2026-0042", tags=["Thema/Steuern"])
    add("T07", "T07_zeugnis.pdf", text_pdf([["Muster Arbeitgeber GmbH", "Arbeitszeugnis", "Ausgestellt: Juni 2023",
                                             "Erika Mustermann (synthetisch) war von 2018 bis 2023 tätig."]]),
        doctype="Zeugnis", correspondent="Muster Arbeitgeber GmbH", date="2023-06", precision="Monat",
        contains=["Arbeitszeugnis"])
    add("T08", "T08_urkunde.pdf", text_pdf([["Beispielstadt Standesamt (synthetisch)", "Urkunde", "Ausgestellt am 12.06.2020",
                                             "Dies ist eine rein synthetische Urkunde."]]),
        doctype="Urkunde", correspondent="Standesamt Beispielstadt", date="2020-06-12", precision="Tag", contains=["Urkunde"])
    add("T09", "T09_schlechter_scan.png", image_png(["Quittung (schlechter Scan)", "Beispiel Baumarkt GmbH", "Datum: 05.05.2026",
                                                     "Gartenschlauch 25 m  19,99 EUR", "Vielen Dank für Ihren Einkauf"], noisy=True),
        doctype="Rechnung", correspondent="Beispiel Baumarkt GmbH", date="2026-05-05", precision="Tag",
        contains=["Quittung"], ocr_quality="poor")
    t10_pages = [[f"Seite {i} von 6", "Prüfbericht Größenänderung Müller & Söhne (synthetisch)", "Straße, Übung, Äpfel, Öl, Maß, Fuß",
                  "Datum: 01.02.2026", f"Abschnitt {i}: Dies ist ein mehrseitiges synthetisches Dokument."] for i in range(1, 7)]
    add("T10", "T10_mehrseitig_ocr.pdf", image_pdf(t10_pages), doctype="Sonstiges Dokument", correspondent="Müller & Söhne",
        date="2026-02-01", precision="Tag", contains=["Größenänderung", "Seite 6 von 6"], pages=6, ocr_quality="good")
    add("T11", "T11_duplikat_exakt.pdf", t01, duplicate_of="T01", exact_duplicate=True)
    add("T12", "T12_zweiter_scan.png", image_png(_wage("Januar 2026", "31.01.2026", "3.000,00")), duplicate_of="T01",
        semantic_duplicate=True, contains=["Verdienstabrechnung Januar 2026"])
    t13_lines = [l.replace("Datum: 15.03.2025", "Datum: 15.03.2025 (Nachtrag vom 01.06.2025)").replace("Absatz 3:", "Absatz 3 (GEÄNDERT: Preis 120 EUR):") for l in vertrag]
    add("T13", "T13_vertrag_geaendert.pdf", text_pdf([t13_lines[:14], t13_lines[14:]]), changed_version_of="T03",
        legally_new_document=True, doctype="Vertrag", contains=["GEÄNDERT"])
    add("T13b", "T13b_vertrag_technische_fassung.pdf", text_pdf(t03_pages[::1] + [[""]]), technical_version_of="T03")
    add("T14", "T14_unbekannter_typ.pdf", text_pdf([["Gesprächsnotiz Gartenverein Beispielstadt (synthetisch)", "Thema: Zaunhöhe",
                                                     "Datum: 03.09.2025"]]), doctype=None, correspondent="Gartenverein Beispielstadt",
        date="2025-09-03", precision="Tag", contains=["Gesprächsnotiz"], unknown_type=True)
    return docs


ASSETS = {
    "logos/muster-logo.svg": b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#336"/><text x="8" y="40" fill="#fff" font-size="20">MUSTER</text></svg>\n',
    "icons/icon.png": None,  # wird aus PIL erzeugt
    "templates/vorlage-brief.txt": "Sehr geehrte Damen und Herren,\n\n<TEXT>\n\nMit freundlichen Grüßen\n(synthetische Vorlage)\n".encode(),
}


def write_all(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for fname, d in sorted(build().items()):
        (out / fname).write_bytes(d["data"])
        manifest.append({**d["meta"], "sha256": hashlib.sha256(d["data"]).hexdigest()})
    assets = out / "assets"
    for rel, data in ASSETS.items():
        p = assets / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if data is None:
            import io
            from PIL import Image
            buf = io.BytesIO(); Image.new("RGB", (32, 32), (51, 51, 102)).save(buf, "PNG"); data = buf.getvalue()
        p.write_bytes(data)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return {m["id"]: m for m in manifest}


if __name__ == "__main__":
    write_all(Path(sys.argv[1]))
    print("ok")
