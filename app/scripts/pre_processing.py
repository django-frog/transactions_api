from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


TIMESTAMP_COL = "timestamp"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"
DELIMITER = ','

def sort_transactions_csv(
    source: Path,
    target: Path,
) -> None:
    with source.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=DELIMITER)

        rows = list(reader)

    def parse_ts(row: dict) -> datetime:
        return datetime.strptime(row[TIMESTAMP_COL], TIMESTAMP_FORMAT)

    rows.sort(key=parse_ts)

    with target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=reader.fieldnames,
            delimiter=DELIMITER,
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    src = Path("./app/transactions_1_month.csv")
    dst = Path("./app/sorted_transactions_1_month.csv")

    sort_transactions_csv(src, dst)
