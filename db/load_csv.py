"""
Load an extraction CSV into SQLite.

 """

import argparse
import csv
import sqlite3
from pathlib import Path

DB_PATH = Path("data/cars.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
KNOWN_VALUES = {"standard", "optional", "not_available", "unknown"}


def kind_of(value: str) -> str:
    """Printed values like 'R17' are specs; everything else is already a category."""
    return value if value in KNOWN_VALUES else "spec"


def main() -> None:
    parser = argparse.ArgumentParser(description="Load an extraction CSV into SQLite.")
    parser.add_argument("csv_file", type=Path, help="Extraction CSV to load")
    parser.add_argument("--make", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--year", type=int)
    parser.add_argument("--market")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()

    with open(args.csv_file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{args.csv_file} has no records")

    args.db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.db) as conn:
        conn.executescript(SCHEMA_PATH.read_text())

        # Remove any earlier load of this file, then insert fresh
        old = conn.execute("SELECT brochure_id FROM brochures WHERE source_file = ?", (args.csv_file.name,)).fetchone()
        if old:
            conn.execute("DELETE FROM features WHERE brochure_id = ?", old)
            conn.execute("DELETE FROM brochures WHERE brochure_id = ?", old)

        cursor = conn.execute(
            "INSERT INTO brochures (source_file, make, model, model_year, market) VALUES (?, ?, ?, ?, ?)",
            (args.csv_file.name, args.make, args.model, args.year, args.market),
        )
        brochure_id = cursor.lastrowid

        conn.executemany(
            """INSERT INTO features (brochure_id, source_page, category, feature, trim, value, kind)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (brochure_id, int(r["source_page"]), r["category"], r["feature"], r["trim"], r["value"], kind_of(r["value"]))
                for r in rows
            ],
        )

        trims = [t for (t,) in conn.execute(
            "SELECT DISTINCT trim FROM features WHERE brochure_id = ? ORDER BY feature_id", (brochure_id,))]
        feature_count = conn.execute(
            "SELECT COUNT(DISTINCT feature) FROM features WHERE brochure_id = ?", (brochure_id,)).fetchone()[0]

    print(f"Loaded {len(rows)} cells into {args.db}")
    print(f"  {args.make} {args.model}: {feature_count} features, trims: {trims}")


if __name__ == "__main__":
    main()