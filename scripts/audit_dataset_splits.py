"""Audit published split files without importing ML packages or changing the data.

This is a data-integrity check, not a reproduction of model accuracy or F1.
Run from the repository root: python scripts/audit_dataset_splits.py --output docs/split-audit.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from itertools import combinations
import json
from pathlib import Path
import subprocess
import sys
import unicodedata


SPLITS = {
    "v1_train": "ptt_raw_consensus/train.json",
    "v1_validation": "ptt_raw_consensus/validation.json",
    "v1_test": "ptt_raw_consensus/test.json",
    "push_train": "ptt_raw_consensus_push_only/train.json",
    "push_validation": "ptt_raw_consensus_push_only/validation.json",
    "push_test": "ptt_raw_consensus_push_only/test.json",
    "gold_test": "ptt_gold_standard/test.json",
}
COMPARISONS = (
    list(combinations(("v1_train", "v1_validation", "v1_test"), 2))
    + list(combinations(("push_train", "push_validation", "push_test"), 2))
    + [("v1_train", "gold_test"), ("v1_validation", "gold_test")]
)


def normalize(text):
    """NFKC, case folding and collapsed whitespace; retain punctuation."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_split(path):
    raw = path.read_bytes()
    records = json.loads(raw)
    if not isinstance(records, list) or not records:
        raise ValueError(f"{path}: expected a nonempty JSON array")
    for index, row in enumerate(records):
        if (not isinstance(row, dict) or not isinstance(row.get("text"), str)
                or type(row.get("label_id")) is not int
                or row["label_id"] not in (0, 1, 2)):
            raise ValueError(f"{path}: invalid text/label_id at row {index}")
    return records, digest(raw)


def summarize(records, file_hash):
    exact = Counter(row["text"] for row in records)
    normalized = Counter(normalize(row["text"]) for row in records)
    labels_by_text = {}
    for row in records:
        labels_by_text.setdefault(normalize(row["text"]), set()).add(row["label_id"])
    return {
        "sha256": file_hash,
        "rows": len(records),
        "label_counts": {str(label): sum(row["label_id"] == label for row in records)
                         for label in (0, 1, 2)},
        "blank_text_rows": sum(not normalize(row["text"]) for row in records),
        "exact_duplicate_extra_rows": sum(count - 1 for count in exact.values()),
        "normalized_duplicate_extra_rows": sum(count - 1 for count in normalized.values()),
        "normalized_texts_with_conflicting_labels": sum(len(labels) > 1 for labels in labels_by_text.values()),
    }


def compare(left, right, normalizer):
    """Count shared unique texts and affected rows on both sides, not just row pairs."""
    left_counts = Counter(normalizer(row["text"]) for row in left)
    right_counts = Counter(normalizer(row["text"]) for row in right)
    shared = sorted(left_counts.keys() & right_counts.keys())
    return {
        "shared_unique_texts": len(shared),
        "left_affected_rows": sum(left_counts[text] for text in shared),
        "right_affected_rows": sum(right_counts[text] for text in shared),
        "shared_text_sha256": [digest(text.encode("utf-8")) for text in shared],
    }


def build_report(root):
    rows, summaries = {}, {}
    for name, relative_path in SPLITS.items():
        records, file_hash = load_split(root / relative_path)
        rows[name] = records
        summaries[name] = {"path": relative_path, **summarize(records, file_hash)}
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
            stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        revision = None
    pairs = []
    for left, right in COMPARISONS:
        pairs.append({"left": left, "right": right,
                      "exact": compare(rows[left], rows[right], lambda text: text),
                      "normalized": compare(rows[left], rows[right], normalize)})
    return {
        "schema_version": 1,
        "source_commit": revision,
        "scope": "Published JSON split integrity only; model F1 was not rerun.",
        "normalization": "Unicode NFKC + casefold + collapse whitespace; punctuation retained",
        "splits": summaries,
        "comparisons": pairs,
        "limitations": [
            "V2 training/validation master tables are not published; V2 disjointness cannot be verified.",
            "V2 starts from V1 weights, so independence must include V1 training exposure.",
            "Text matches flag review candidates; repeated generic phrases do not establish score inflation.",
            "JSON exports omit post/user/timestamp identifiers; grouped and temporal leakage cannot be audited.",
            "Gold test is balanced (70 per class), which does not estimate natural deployment class prevalence.",
            "Raw-consensus test and gold-standard test are distinct evaluation populations.",
        ],
    }


def has_overlap(report):
    return any(pair["normalized"]["shared_unique_texts"] for pair in report["comparisons"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true", help="Exit 1 when cross-split overlap is found")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.root)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Split audit failed: {exc}\n")
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"Wrote split integrity report: {args.output}")
    else:
        print(payload, end="")
    if has_overlap(report):
        print("Cross-split text overlap found; inspect the report. Model F1 was not evaluated.", file=sys.stderr)
    return 1 if args.strict and has_overlap(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
