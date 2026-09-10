import pymupdf

MAX_IMAGE_EDGE = 1568

def render_page(doc: pymupdf.Document, page_number: int) -> bytes:
    """Render a 1-based page number as PNG bytes."""
    page = doc[page_number - 1]
    zoom = MAX_IMAGE_EDGE / max(page.rect.width, page.rect.height)
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png")
