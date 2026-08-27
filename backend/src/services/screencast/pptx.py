"""PPTX-Verarbeitung: Text-Extraktion, AutoFit-Workaround, PPTX→PNG via LibreOffice."""

import os
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

from loguru import logger
from pptx import Presentation
from pptx.oxml.ns import qn

from src.limits import RENDER_MAX_WORKERS
from src.utils.pptx_text import (
    iter_linked_text_nodes,
    iter_slide_paragraphs,
    iter_visible_slides,
)


def extract_text_per_slide(source: bytes | str | Path) -> list[str]:
    """Text per visible slide, hidden ones stay out."""
    prs = Presentation(BytesIO(source) if isinstance(source, bytes) else source)
    slide_texts: list[str] = []
    for slide in iter_visible_slides(prs):
        texts: list[str] = []
        for paragraph in iter_slide_paragraphs(slide):
            text = paragraph.text.strip()
            if text:
                texts.append(text)
        # SmartArt and charts keep their text outside the slide XML.
        for node in iter_linked_text_nodes(slide):
            text = (node.text or "").strip()
            if text:
                texts.append(text)
        slide_texts.append("\n".join(texts))
    return slide_texts


def soffice_profile_dir() -> Path:
    """Its own LibreOffice profile per process and thread, otherwise a conversion fails."""
    key = f"{os.getpid()}-{threading.get_ident()}"
    return Path(tempfile.gettempdir()) / "kis-lo-profiles" / key


def build_soffice_cmd(pptx_path: Path, output_dir: Path) -> list[str]:
    """The LibreOffice call for PPTX to PDF, without hidden slides."""
    profile = soffice_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    pdf_filter = (
        'pdf:impress_pdf_Export:'
        '{"ExportHiddenSlides":{"type":"boolean","value":"false"}}'
    )
    return [
        "libreoffice", "--headless", "--norestore",
        f"-env:UserInstallation=file://{profile}",
        "--convert-to", pdf_filter,
        "--outdir", str(output_dir), str(pptx_path),
    ]


def _apply_autofit_for_rendering(pptx_path: Path) -> Path:
    """A temp copy with the font shrunk by 20 percent, the original stays."""
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
    # Reads the real slide dimensions so the aspect ratio is right.
    prs = Presentation(str(pptx_path))
    slide_width = prs.slide_width   # EMU (1 cm = 360000 EMU)
    slide_height = prs.slide_height
    width_cm = slide_width / 360000
    height_cm = slide_height / 360000
    slide_ratio = slide_width / slide_height
    logger.info("PPTX slide size: {:.2f}x{:.2f} cm (ratio {:.4f})", width_cm, height_cm, slide_ratio)

    render_pptx = _apply_autofit_for_rendering(pptx_path)

    try:
        cmd = build_soffice_cmd(render_pptx, output_dir)
        logger.info("Converting PPTX to PDF: {}", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    finally:
        # Clear the copy away, otherwise the folder stays behind after pre-rendering.
        render_pptx.unlink(missing_ok=True)

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

    try:
        with ThreadPoolExecutor(max_workers=RENDER_MAX_WORKERS) as executor:
            futures = {executor.submit(_render_page, p): p for p in range(1, page_count + 1)}
            for future in as_completed(futures):
                future.result()  # re-raises on error
    finally:
        pdf_path.unlink(missing_ok=True)  # Zwischenschritt, die PNGs sind das Ergebnis

    # Collect generated images (pdftoppm names them slide-1.png, slide-2.png, ...)
    images = sorted(output_dir.glob("slide-*.png"))
    if not images:
        raise RuntimeError("Keine Slide-Bilder erstellt")

    return images
