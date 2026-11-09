import base64
from io import BytesIO
from pathlib import Path

import pdfplumber

from app.config import settings


class ExtractedPdf:
    def __init__(
        self,
        markdown: str,
        pages: int,
        tables: int,
        image_data_urls: list[str] | None = None,
    ) -> None:
        self.markdown = markdown
        self.pages = pages
        self.tables = tables
        self.image_data_urls = image_data_urls or []


def extract_pdf_markdown(
    pdf_path: Path,
    *,
    include_text: bool = True,
    include_tables: bool = True,
    include_images: bool = False,
) -> ExtractedPdf:
    parts: list[str] = []
    table_count = 0
    page_count = 0

    with pdfplumber.open(str(pdf_path)) as pdf:
        page_count = len(pdf.pages)
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text(x_tolerance=1, y_tolerance=3) or "" if include_text else ""
            tables = page.extract_tables() or [] if include_tables else []

            parts.append(f"\n\n## Pagina {page_number}\n")
            if page_text.strip():
                parts.append(page_text.strip())

            for table_index, table in enumerate(tables, start=1):
                table_count += 1
                parts.append(f"\n\n### Tabla {table_index} de la pagina {page_number}\n")
                parts.append(_table_to_markdown(table))

            if not page_text.strip() and not tables and settings.enable_ocr:
                ocr_text = _try_ocr_page(pdf_path, page_number)
                if ocr_text:
                    parts.append("\n\n### Texto OCR\n")
                    parts.append(ocr_text)

    image_data_urls = _render_pdf_pages_as_data_urls(pdf_path) if include_images else []

    return ExtractedPdf(
        markdown="\n".join(part for part in parts if part),
        pages=page_count,
        tables=table_count,
        image_data_urls=image_data_urls,
    )


def _render_pdf_pages_as_data_urls(pdf_path: Path) -> list[str]:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []

    data_urls: list[str] = []
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page_limit = min(len(pdf), settings.vision_max_pages)
        scale = settings.vision_dpi / 72
        for page_index in range(page_limit):
            page = pdf[page_index]
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=82, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            data_urls.append(f"data:image/jpeg;base64,{encoded}")
            page.close()
    finally:
        pdf.close()
    return data_urls


def extract_docx_markdown(docx_path: Path) -> ExtractedPdf:
    import docx

    document = docx.Document(str(docx_path))
    parts: list[str] = []
    table_count = 0

    for element in document.element.body.iterchildren():
        if element.tag.endswith("}p"):
            paragraph = next((p for p in document.paragraphs if p._p is element), None)
            text = (paragraph.text if paragraph else "").strip()
            if text:
                parts.append(text)
        elif element.tag.endswith("}tbl"):
            table = next((t for t in document.tables if t._tbl is element), None)
            if table is None:
                continue
            table_count += 1
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            parts.append(f"\n\n### Tabla {table_count}\n")
            parts.append(_table_to_markdown(rows))

    return ExtractedPdf(
        markdown="\n".join(part for part in parts if part),
        pages=0,
        tables=table_count,
        image_data_urls=[],
    )


def extract_doc_markdown(doc_path: Path) -> ExtractedPdf:
    """Extrae texto de un .doc antiguo convirtiendolo a .docx con Microsoft Word (COM)."""
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError(
            "No se pudo leer el archivo .doc porque el servidor no tiene Microsoft Word disponible. "
            "Guardalo como .docx o .pdf y vuelve a subirlo."
        ) from exc

    import gc

    docx_path = doc_path.with_name(doc_path.stem + "_convertido.docx")
    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0  # wdAlertsNone: nunca mostrar dialogos que puedan colgar el proceso
        document = word.Documents.Open(
            str(doc_path.resolve()),
            ReadOnly=True,
            ConfirmConversions=False,
            AddToRecentFiles=False,
        )
        try:
            document.SaveAs(str(docx_path.resolve()), FileFormat=12)  # wdFormatXMLDocument (.docx)
        finally:
            document.Close(SaveChanges=0)
    except Exception as exc:
        raise RuntimeError(
            "No se pudo convertir el archivo .doc con Microsoft Word. "
            "Guardalo como .docx o .pdf y vuelve a subirlo."
        ) from exc
    finally:
        if word is not None:
            word.Quit(SaveChanges=0)
            del word
        gc.collect()
        pythoncom.CoUninitialize()

    try:
        return extract_docx_markdown(docx_path)
    finally:
        if docx_path.exists():
            docx_path.unlink()


def _table_to_markdown(table: list[list[str | None]]) -> str:
    clean_rows = [
        [(_clean_cell(cell)) for cell in row]
        for row in table
        if row and any((cell or "").strip() for cell in row)
    ]
    if not clean_rows:
        return ""

    max_cols = max(len(row) for row in clean_rows)
    normalized = [row + [""] * (max_cols - len(row)) for row in clean_rows]
    header = normalized[0]
    separator = ["---"] * max_cols
    body = normalized[1:] if len(normalized) > 1 else []

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def _clean_cell(cell: str | None) -> str:
    return (cell or "").replace("\n", " ").replace("|", "/").strip()


def _try_ocr_page(pdf_path: Path, page_number: int) -> str:
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        return ""

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    try:
        images = convert_from_path(
            str(pdf_path),
            first_page=page_number,
            last_page=page_number,
            dpi=220,
        )
        return "\n".join(pytesseract.image_to_string(image, lang="spa") for image in images).strip()
    except Exception:
        return ""
