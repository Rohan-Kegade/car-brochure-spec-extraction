"""
Extract feature grids from brochure pages with a vision model.

"""

import argparse
import base64
import csv
import json
from pathlib import Path
from typing import Literal

import pymupdf
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from render_pages import render_page

DEFAULT_LLM = "google_genai:gemini-3.5-flash-lite" 
CSV_COLUMNS = ["source_page", "category", "feature", "trim", "value", "raw"]


# ---------------------------------------------------------------------------
# The shape we ask the model to return: one row per feature, one cell per trim
# ---------------------------------------------------------------------------

class Cell(BaseModel):
    trim: str = Field(description="Trim name exactly as printed in the column header")
    availability: Literal["standard", "optional", "not_available", "value", "unclear"]
    value: str = Field(description="Printed text when availability is 'value', e.g. 'R17' or '6'. Empty string otherwise.")


class FeatureRow(BaseModel):
    category: str = Field(description="Section heading the feature is under, e.g. 'Safety'. Empty string if none.")
    feature: str = Field(description="Feature name exactly as printed")
    cells: list[Cell] = Field(description="One cell for every trim column, including trims without the feature")


class SpecGrid(BaseModel):
    page_has_spec_grid: bool
    trims: list[str] = Field(description="Trim names from the column headers, left to right")
    rows: list[FeatureRow]


PROMPT = """This image is a page from a car brochure. Extract its trim/variant feature grid.

Rules:
1. Trims are the column headers. Use each trim name exactly as printed, including suffixes like (O), AT or CVT.
2. Create one row per feature, with one cell for EVERY trim, including trims where the feature is not available.
3. Use the legend on the page to interpret symbols (ticks, dots, dashes).
4. availability:
   - "standard": included on that trim
   - "optional": available at extra cost, or as a pack or accessory
   - "not_available": not offered on that trim
   - "value": the cell shows a specification like "R17", "6" or "Dual-tone"; put that text in value
   - "unclear": you cannot read the cell with confidence
5. If one cell spans several trims, give each of those trims the same cell.
6. Record only what is printed on this page. Do not guess or use outside knowledge about the car.
7. If there is no feature grid on this page, set page_has_spec_grid to false and return empty lists."""


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def extract_page(extractor, image_png: bytes) -> SpecGrid:
    """Send one page image and get the grid back as a SpecGrid object."""
    message = HumanMessage(content=[
        {"type": "image", "base64": base64.b64encode(image_png).decode("utf-8"), "mime_type": "image/png"},
        {"type": "text", "text": PROMPT},
    ])
    result = extractor.invoke([message])

    finish = result["raw"].response_metadata.get("finish_reason")
    if str(finish).upper() in ("MAX_TOKENS", "LENGTH"):
        raise RuntimeError("Output was cut off. Raise max_tokens or crop the page into smaller parts.")
    if result["parsing_error"] is not None:
        raise RuntimeError(f"Could not parse the model's output: {result['parsing_error']}")
    return result["parsed"]


def to_records(grid: SpecGrid, page_number: int) -> list[dict]:
    """Flatten the grid into one record per (feature, trim), matching the pdfplumber CSV."""
    records = []
    for row in grid.rows:
        for cell in row.cells:
            if cell.availability == "value":
                value = cell.value.strip()
            elif cell.availability == "unclear":
                value = "unknown"
            else:
                value = cell.availability
            records.append({
                "source_page": page_number,
                "category": row.category.strip(),
                "feature": row.feature.strip(),
                "trim": cell.trim.strip(),
                "value": value,
                "raw": cell.value.strip() or cell.availability,
            })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract feature grids with a vision model.")
    parser.add_argument("pdf", type=Path, help="Path to the brochure PDF")
    parser.add_argument("--pages", type=int, nargs="+", required=True, help="1-based spec page numbers")
    parser.add_argument("--llm", default=DEFAULT_LLM, help="LangChain model id")
    parser.add_argument("--out", type=Path, help="Output CSV (default: output/extractions/<pdf>_vision.csv)")
    args = parser.parse_args()

    load_dotenv()
    out = args.out or Path("output/extractions") / f"{args.pdf.stem}_vision.csv"
    llm = init_chat_model(args.llm, max_tokens=32000)
    extractor = llm.with_structured_output(SpecGrid, include_raw=True)

    all_records, raw_output = [], {}

    with pymupdf.open(args.pdf) as doc:
        for page_number in args.pages:
            if not 1 <= page_number <= doc.page_count:
                print(f"Page {page_number}: skipped, the PDF has {doc.page_count} pages")
                continue

            print(f"Page {page_number}: sending to {args.llm}...")
            try:
                grid = extract_page(extractor, render_page(doc, page_number))
            except Exception as error:
                print(f"  failed: {error}")
                continue

            raw_output[page_number] = grid.model_dump()
            if not grid.page_has_spec_grid:
                print("  no feature grid found")
                continue

            records = to_records(grid, page_number)
            unknown = sum(r["value"] == "unknown" for r in records)
            print(f"  trims: {grid.trims}")
            print(f"  {len(grid.rows)} features, {len(records)} cells, {unknown} unknown")
            all_records.extend(records)

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_records)
    out.with_suffix(".json").write_text(json.dumps(raw_output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSaved {len(all_records)} cells to {out}")


if __name__ == "__main__":
    main()