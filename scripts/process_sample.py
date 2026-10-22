"""Run the assessment sample locally and write structured CSV/JSON output."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.analyzer import analyze_message
from app.services.filtering import filter_message

INPUT = ROOT / "sample_feedback.csv"
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)

rows = []
with INPUT.open("r", encoding="utf-8-sig", newline="") as handle:
    for row in csv.DictReader(handle):
        message = (row.get("message") or "").strip()
        result = filter_message(message)
        item = {"message": message, "accepted": result.is_valid, "reason": result.reason}
        if result.is_valid:
            item.update(analyze_message(message))
        else:
            item.update({"category": None, "priority": None, "sentiment": None,
                         "product_feature": None, "suggested_reply": None})
        rows.append(item)

with (OUT_DIR / "sample_output.json").open("w", encoding="utf-8") as handle:
    json.dump(rows, handle, indent=2, ensure_ascii=False)

with (OUT_DIR / "sample_output.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    fields = ["message", "accepted", "reason", "category", "priority", "sentiment", "product_feature", "suggested_reply"]
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print(f"Processed {len(rows)} messages: {sum(r['accepted'] for r in rows)} accepted, {sum(not r['accepted'] for r in rows)} rejected")
print(f"Wrote {OUT_DIR / 'sample_output.json'} and {OUT_DIR / 'sample_output.csv'}")
