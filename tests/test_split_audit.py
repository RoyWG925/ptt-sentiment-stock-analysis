"""Dependency-free fixture tests: python -m unittest tests.test_split_audit -v."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit_dataset_splits import compare, digest, load_split, normalize, summarize


class SplitAuditTests(unittest.TestCase):
    def test_normalization_detects_fullwidth_case_and_whitespace(self):
        left = [{"text": "ＡＢＣ  股票\n", "label_id": 0}]
        right = [{"text": "abc 股票", "label_id": 2}]
        self.assertEqual(compare(left, right, lambda value: value)["shared_unique_texts"], 0)
        self.assertEqual(compare(left, right, normalize)["shared_unique_texts"], 1)
        self.assertNotEqual(normalize("漲?"), normalize("漲!"))

    def test_overlap_counts_unique_texts_and_affected_rows(self):
        left = [{"text": "重複", "label_id": 0}] * 3
        right = [{"text": "重複", "label_id": 1}] * 2
        result = compare(left, right, normalize)
        self.assertEqual((result["shared_unique_texts"], result["left_affected_rows"],
                          result["right_affected_rows"]), (1, 3, 2))
        self.assertEqual(result["shared_text_sha256"], [digest("重複".encode())])

    def test_summary_flags_conflicting_labels_and_empty_text(self):
        rows = [{"text": "Ａ", "label_id": 0}, {"text": "a", "label_id": 1},
                {"text": "   ", "label_id": 2}]
        result = summarize(rows, "fixture-hash")
        self.assertEqual(result["label_counts"], {"0": 1, "1": 1, "2": 1})
        self.assertEqual(result["normalized_texts_with_conflicting_labels"], 1)
        self.assertEqual(result["normalized_duplicate_extra_rows"], 1)
        self.assertEqual(result["blank_text_rows"], 1)

    def test_load_preserves_file_bytes_and_hashes_original_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "split.json"
            raw = b'[ {"text": "sample", "label_id": 0} ]\n'
            path.write_bytes(raw)
            records, file_hash = load_split(path)
            self.assertEqual(records[0]["text"], "sample")
            self.assertEqual(file_hash, digest(raw))
            self.assertEqual(path.read_bytes(), raw)

    def test_invalid_shapes_and_labels_fail_loudly(self):
        invalid = [{}, [], [{"text": "sample", "label_id": True}],
                   [{"text": "sample", "label_id": 3}], [{"text": None, "label_id": 0}]]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "split.json"
            for value in invalid:
                with self.subTest(value=value):
                    path.write_text(json.dumps(value))
                    with self.assertRaises(ValueError):
                        load_split(path)


if __name__ == "__main__":
    unittest.main()
