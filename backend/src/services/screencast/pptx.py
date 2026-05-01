"""PPTX-Verarbeitung: Text-Extraktion, AutoFit-Workaround, PPTX→PNG via LibreOffice."""

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

from loguru import logger
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

from src.limits import RENDER_MAX_WORKERS

_A_T = '{http://schemas.openxmlformats.org/drawingml/2006/main}t'


def extract_text_per_slide(pptx_bytes: bytes) -> list[str]:
    """Extract text from each slide of a PPTX, returning a list of strings (one per slide)."""
    prs = Presentation(BytesIO(pptx_bytes))
    slide_texts: list[str] = []
    for slide in prs.slides:
        texts: list[str] = []
        for shape in slide.shapes:
            _collect_shape_text(shape, texts)
        slide_texts.append("\n".join(texts))
    return slide_texts


def _collect_shape_text(shape, texts: list[str]) -> None:
    if shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            text = paragraph.text.strip()
            if text:
                texts.append(text)
    elif shape.has_table:
        for row in shape.table.rows:
            for cell in row.cells:
                for paragraph in cell.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        texts.append(text)
    elif shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for subshape in shape.shapes:
            _collect_shape_text(subshape, texts)
    else:
        # Fallback for SmartArt, graphic frames, and other non-standard shapes:
        # scan raw XML for any <a:t> text runs not already captured above.
        try:
            for t_elem in shape.element.iter(_A_T):
                text = (t_elem.text or "").strip()
                if text:
                    texts.append(text)
        except Exception:
            pass


def _apply_autofit_for_rendering(pptx_path: Path) -> Path:
    """Return a temp copy of the PPTX with AutoFit text shrunk by 20%.
    Works at XML level so inherited/theme font sizes are also captured.
    The original file is never modified."""
    prs = Presentation(str(pptx_path))
    changed = False
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            tf = shape.text_frame
            body_pr = tf._txBody.find(qn('a:bodyPr'))
            if body_pr is None:
                continue
            has_autofit = (
                body_pr.find(qn('a:normAutofit')) is not None or
                body_pr.find(qn('a:spAutoFit')) is not None
            )
            if not has_autofit:
                continue
            # Work directly on XML - shrink sz on all <a:rPr> elements
            for r_pr in tf._txBody.iter(qn('a:rPr')):
                sz = r_pr.get('sz')
                if sz:
                    r_pr.set('sz', str(int(int(sz) * 0.80)))
                else:
                    # No explicit size - set one based on default 1800 (18pt)
                    r_pr.set('sz', str(int(1800 * 0.80)))
                changed = True
            # Also shrink defRPr inside <a:pPr> (paragraph-level default)
            for p_pr in tf._txBody.iter(qn('a:pPr')):
                def_r_pr = p_pr.find(qn('a:defRPr'))
                if def_r_pr is not None:
                    sz = def_r_pr.get('sz')
                    if sz:
                        def_r_pr.set('sz', str(int(int(sz) * 0.80)))
                        changed = True

    render_path = pptx_path.parent / f"_render_{pptx_path.name}"
    prs.save(str(render_path))
    logger.info("AutoFit XML-level applied: changed={}", changed)
    return render_path


def pptx_to_images(pptx_path: Path, output_dir: Path, dpi: int = 100) -> list[Path]:
    """Convert PPTX slides to PNG images using LibreOffice."""
    # Read actual slide dimensions so we can detect non-standard sizes and
    # pass the correct aspect ratio to the post-processing step.
    prs = Presentation(str(pptx_path))
    slide_width = prs.slide_width   # EMU (1 cm = 360000 EMU)
    slide_height = prs.slide_height
    width_cm = slide_width / 360000
    height_cm = slide_height / 360000
    slide_ratio = slide_width / slide_height
    logger.info("PPTX slide size: {:.2f}x{:.2f} cm (ratio {:.4f})", width_cm, height_cm, slide_ratio)

    render_pptx = _apply_autofit_for_rendering(pptx_path)

    cmd = [
        "libreoffice", "--headless", "--norestore",
        "--convert-to", "pdf",
        "--outdir", str(output_dir), str(render_pptx),
    ]
    logger.info("Converting PPTX to PDF: {}", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    pdf_path = output_dir / f"{render_pptx.stem}.pdf"
    if not pdf_path.exists():
        # PDF was not created - this is a real failure regardless of exit code
        logger.error("LibreOffice conversion failed (rc={}): {}", result.returncode, result.stderr[:300])
        raise RuntimeError(f"LibreOffice Konvertierung fehlgeschlagen: {result.stderr[:200]}")
    if result.returncode != 0:
        # PDF exists despite non-zero exit - treat javaldx / Java warnings as non-fatal
        logger.warning("LibreOffice exited with rc={} but PDF was created (non-fatal): {}", result.returncode, result.stderr[:200])

    # Get page count via pdfinfo
    pdfinfo_result = subprocess.run(
        ["pdfinfo", str(pdf_path)], capture_output=True, text=True, timeout=30
    )
    page_count = 1
    for line in pdfinfo_result.stdout.splitlines():
        if line.startswith("Pages:"):
            page_count = int(line.split(":")[1].strip())
            break
    logger.info("PDF has {} pages, rendering in parallel", page_count)

    # Convert PDF pages to PNG in parallel - one pdftoppm process per page.
    slide_prefix = str(output_dir / "slide")

    def _render_page(page: int) -> None:
        cmd = [
            "pdftoppm", "-png", "-r", str(dpi),
            "-f", str(page), "-l", str(page),
            str(pdf_path), slide_prefix,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Seite {page} fehlgeschlagen: {result.stderr[:200]}")

    with ThreadPoolExecutor(max_workers=RENDER_MAX_WORKERS) as executor:
        futures = {executor.submit(_render_page, p): p for p in range(1, page_count + 1)}
        for future in as_completed(futures):
            future.result()  # re-raises on error

    # Collect generated images (pdftoppm names them slide-1.png, slide-2.png, ...)
    images = sorted(output_dir.glob("slide-*.png"))
    if not images:
        raise RuntimeError("Keine Slide-Bilder erstellt")

    return images
