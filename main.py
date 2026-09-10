import argparse
import base64
from pathlib import Path

import pymupdf
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

from render_pages import render_page

DEFAULT_LLM = "google_genai:gemini-3.5-flash-lite"  

PROMPT = """
    This image is a page from a car brochure.
    1. List the trim names shown in the column headers of the feature grid, left to right.
    2. For the first 5 feature rows, give the value for each trim
    (for example: standard, optional, not available, or a printed value like R17).
    If there is no feature grid on this page, say so.
"""


def ask_about_page(llm, image_png: bytes, prompt: str):
    """Send one page image plus a text prompt to the model."""
    message = HumanMessage(content=[
        {"type": "image", "base64": base64.b64encode(image_png).decode("utf-8"), "mime_type": "image/png"},
        {"type": "text", "text": prompt},
    ])
    return llm.invoke([message])


def main() -> None:
    parser = argparse.ArgumentParser(description="Test a vision model on one brochure page.")
    parser.add_argument("pdf", type=Path, help="Path to the brochure PDF")
    parser.add_argument("--page", type=int, required=True, help="1-based page number of a feature grid")
    parser.add_argument("--llm", default=DEFAULT_LLM, help="LangChain model id, e.g. google_genai:gemini-3.7-flash")
    args = parser.parse_args()

    load_dotenv() 
    llm = init_chat_model(args.llm, max_tokens=2000)

    with pymupdf.open(args.pdf) as doc:
        if not 1 <= args.page <= doc.page_count:
            raise SystemExit(f"--page must be between 1 and {doc.page_count}")
        image_png = render_page(doc, args.page)

    print(f"Sending page {args.page} to {args.llm}...\n")
    response = ask_about_page(llm, image_png, PROMPT)

    print(response.text)
    usage = response.usage_metadata or {}
    print(f"\nTokens: {usage.get('input_tokens')} in, {usage.get('output_tokens')} out")


if __name__ == "__main__":
    main()