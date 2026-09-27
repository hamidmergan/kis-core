"""PDFs aus mehreren Fäden zugleich lesen, ohne dass der Prozess abstürzt.

pdfium ist nicht threadsicher. Seit das Lesen außerhalb der Ereignisschleife läuft, lasen
mehrere Fäden eines Backend-Prozesses gleichzeitig, und der Prozess starb mit einem
Speicherzugriffsfehler (Lauf 4 des Lasttests am 26.09., nachgestellt mit Exit 139).
"""

import subprocess
import sys
import textwrap


def _pdf(pfad, seiten=6):
    """A small valid PDF with text on every page, offsets computed by hand."""
    objekte = ["<< /Type /Catalog /Pages 2 0 R >>", None,
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kinder = []
    for i in range(seiten):
        inhalt = f"BT /F1 12 Tf 72 712 Td (Seite {i + 1} Projektmanagement Ziele Zeit Kosten) Tj ET"
        objekte.append(f"<< /Length {len(inhalt)} >>\nstream\n{inhalt}\nendstream")
        inhalt_nr = len(objekte)
        objekte.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 3 0 R >> >> /Contents {inhalt_nr} 0 R >>")
        kinder.append(f"{len(objekte)} 0 R")
    objekte[1] = f"<< /Type /Pages /Kids [{' '.join(kinder)}] /Count {seiten} >>"
    daten = b"%PDF-1.4\n"
    stellen = []
    for nr, obj in enumerate(objekte, 1):
        stellen.append(len(daten))
        daten += f"{nr} 0 obj\n{obj}\nendobj\n".encode()
    xref = len(daten)
    daten += f"xref\n0 {len(objekte) + 1}\n0000000000 65535 f \n".encode()
    for s in stellen:
        daten += f"{s:010d} 00000 n \n".encode()
    daten += f"trailer\n<< /Size {len(objekte) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    pfad.write_bytes(daten)


def test_viele_faeden_lesen_pdfs_gleichzeitig(tmp_path):
    pdf = tmp_path / "t.pdf"
    _pdf(pdf)
    code = textwrap.dedent(f"""
        import concurrent.futures as cf
        from loguru import logger
        logger.remove()
        from src.services.source_reading import read_file
        from src.utils.file_validation import pages_or_raise

        def lesen(i):
            if i % 2:
                pages_or_raise(".pdf", {str(pdf)!r}, "de")
                return 1
            return len(read_file({str(pdf)!r}, "t.pdf").text)

        for _ in range(4):
            with cf.ThreadPoolExecutor(8) as ex:
                assert all(list(ex.map(lesen, range(32))))
    """)
    # In its own process: a crash here shows as an exit code instead of taking pytest down.
    lauf = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert lauf.returncode == 0, lauf.stderr[-2000:]
