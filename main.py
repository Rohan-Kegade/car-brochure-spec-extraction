"""
Step 1: Render brochure pages as images.

"""

import argparse
from pathlib import Path

import pymupdf

MAX_IMAGE_EDGE = 1568  # vision APIs downscale larger images anyway


def render_page(doc: pymupdf.Document, page_number: int) -> bytes:
    """Render a 1-based page number as PNG bytes."""
    page = doc[page_number - 1]
    zoom = MAX_IMAGE_EDGE / max(page.rect.width, page.rect.height)
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render brochure pages as PNG images.")
    parser.add_argument("pdf", type=Path, help="Path to the brochure PDF")
    parser.add_argument("--pages", type=int, nargs="+", help="1-based page numbers (default: all pages)")
    parser.add_argument("--out", type=Path, default=Path("output/pages"), help="Folder for the images")
    args = parser.parse_args()

    doc = pymupdf.open(args.pdf)
    pages = args.pages or range(1, doc.page_count + 1)
    args.out.mkdir(parents=True, exist_ok=True)

    for page_number in pages:
        if not 1 <= page_number <= doc.page_count:
            print(f"Skipping page {page_number}: the PDF has {doc.page_count} pages")
            continue
        image_path = args.out / f"{args.pdf.stem}_page_{page_number}.png"
        image_path.write_bytes(render_page(doc, page_number))
        print(f"Saved {image_path}")


if __name__ == "__main__":
    main()