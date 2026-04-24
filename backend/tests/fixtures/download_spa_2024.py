"""
Run once to download Spa 2024 Race fixture data from LiveF1.
Saves JSON files to tests/fixtures/spa_2024/.
Also prints column schemas to schema.md.

Usage: python tests/fixtures/download_spa_2024.py
"""
import json
import sys
from pathlib import Path

import livef1
import pandas as pd

OUT_DIR = Path(__file__).parent / "spa_2024"
OUT_DIR.mkdir(exist_ok=True)

DATA_TYPES = [
    "TimingData",
    "Position.z",
    "RaceControlMessages",
    "WeatherData",
    "TimingAppData",
    "SessionData",
    "DriverList",
]


def df_to_json_safe(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def main():
    print("Fetching 2024 Belgian GP Race from LiveF1...")
    session = livef1.get_session(
        season=2024,
        meeting_identifier="Spa",
        session_identifier="Race",
    )

    print("Loading session data...")
    session.load_session_data()

    schema_lines = ["# Spa 2024 Race — DataFrame Schemas\n"]

    for data_name in DATA_TYPES:
        print(f"  Loading {data_name}...")
        try:
            df = session.get_data(dataNames=data_name)
            if df is None or (hasattr(df, "empty") and df.empty):
                print(f"    {data_name}: empty, skipping")
                continue

            # Save JSON
            safe_name = data_name.replace(".", "_").lower()
            out_path = OUT_DIR / f"{safe_name}.json"
            records = df_to_json_safe(df) if isinstance(df, pd.DataFrame) else df
            out_path.write_text(json.dumps(records, indent=2))
            print(f"    Saved {len(records)} rows → {out_path.name}")

            # Record schema
            if isinstance(df, pd.DataFrame):
                schema_lines.append(f"\n## {data_name}\n")
                schema_lines.append(f"Rows: {len(df)}\n")
                schema_lines.append("```\n")
                schema_lines.append(str(df.dtypes) + "\n")
                schema_lines.append("```\n")
                schema_lines.append(f"\nHead (3 rows):\n```\n{df.head(3)}\n```\n")

        except Exception as e:
            print(f"    ERROR loading {data_name}: {e}", file=sys.stderr)

    (OUT_DIR / "schema.md").write_text("".join(schema_lines))
    print(f"\nDone. Schema written to {OUT_DIR / 'schema.md'}")


if __name__ == "__main__":
    main()
