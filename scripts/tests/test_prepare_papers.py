"""Offline behavioural tests; never access author repositories or competition code."""
import contextlib
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_papers as prep


def record():
    return {"paper_id": "CPMCM-TEST", "year": "2022", "problem": "A", "title": "test",
            "resource_kind": "external_fulltext", "download_url": "https://example.test/paper.pdf",
            "url": "https://example.test/source", "bytes": "", "sha256": "",
            "acquisition_status": "unchecked", "extraction_status": "unchecked",
            "reading_status": "unchecked", "failure_reason": "", "last_checked_at": ""}


class PreparationTests(unittest.TestCase):
    def test_no_filter_cannot_download_even_with_limit(self):
        with patch.object(sys, "argv", ["prepare", "--extract", "--limit", "1"]), \
                patch.object(prep, "urlopen") as network, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                prep.main()
            self.assertEqual(error.exception.code, 2)
            network.assert_not_called()

    def test_list_is_read_only_even_with_extract_flag(self):
        with patch.object(sys, "argv", ["prepare", "--year", "2022", "--list", "--extract", "--limit", "1"]), \
                patch.object(prep, "read_manifest", return_value=([], [record(), record()])), \
                patch.object(prep, "urlopen") as network, patch.object(prep, "save_manifest") as save, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(prep.main(), 0)
            self.assertEqual(len(output.getvalue().splitlines()), 1)
            save.assert_not_called()
            network.assert_not_called()

    def test_empty_scan_and_garbled_text_flags(self):
        self.assertIn("possible_scan", prep.page_flags("", True))
        self.assertIn("empty_text", prep.page_flags("", False))
        self.assertIn("suspected_garbled_text", prep.page_flags("\ufffd" * 50, False))
        self.assertEqual(prep.page_flags("正常的中文和English123。" * 10, False), [])

    def test_html_and_hash_mismatch_are_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "original.pdf"
            pdf.write_bytes(b"<html>Sign in</html>")
            with self.assertRaisesRegex(ValueError, "not a PDF"):
                prep.validate_pdf(pdf, record())
            pdf.write_bytes(b"%PDF-1.7\nfixture")
            row = record()
            row["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "SHA256"):
                prep.validate_pdf(pdf, row)

    def test_failed_download_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(prep, "urlopen", side_effect=OSError("offline")):
            folder = Path(tmp)
            with self.assertRaises(OSError):
                prep.acquire(record(), folder, 1, 1024)
            self.assertFalse((folder / "original.pdf").exists())
            self.assertFalse((folder / "original.pdf.part").exists())

    def test_interrupted_extraction_resumes_physical_pages(self):
        class Page(dict):
            def __init__(self, text):
                self.text = text

            def extract_text(self):
                if isinstance(self.text, BaseException):
                    raise self.text
                return self.text

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            row = record()
            with patch("pypdf.PdfReader") as reader:
                reader.return_value.is_encrypted = False
                reader.return_value.pages = [Page("Readable text " * 10), Page(KeyboardInterrupt())]
                with self.assertRaises(KeyboardInterrupt):
                    prep.extract(row, folder / "fake.pdf", "digest", folder)
                self.assertTrue((folder / "page-0001.json").exists())
                reader.return_value.pages = [Page(AssertionError("must reuse page 1")), Page("")]
                self.assertEqual(prep.extract(row, folder / "fake.pdf", "digest", folder), "needs_review")
                result = json.loads((folder / "page-0002.json").read_text(encoding="utf-8"))
                self.assertEqual(result["physical_page"], 2)
                self.assertEqual(result["paper_id"], row["paper_id"])
                self.assertTrue(result["manual_review_required"])
                self.assertEqual(row["reading_status"], "unchecked")

    def test_non_object_page_cache_is_reextracted(self):
        class Page(dict):
            def extract_text(self):
                return "Freshly extracted text " * 10

        for cached in ([], None, 42, 3.14, "invalid cache", True):
            with self.subTest(cached=cached), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                output = folder / "page-0001.json"
                output.write_text(json.dumps(cached), encoding="utf-8")
                with patch("pypdf.PdfReader") as reader, \
                        patch.object(Page, "extract_text", return_value="Freshly extracted text " * 10) as extract_text:
                    reader.return_value.is_encrypted = False
                    reader.return_value.pages = [Page()]
                    self.assertEqual(prep.extract(record(), folder / "fake.pdf", "digest", folder), "extracted")
                    extract_text.assert_called_once_with()
                result = json.loads(output.read_text(encoding="utf-8"))
                self.assertIsInstance(result, dict)
                self.assertEqual(result["physical_page"], 1)
                self.assertEqual(result["paper_id"], "CPMCM-TEST")
                self.assertEqual(result["text"], "Freshly extracted text " * 10)

    def test_manifest_external_edit_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "papers.csv"
            manifest.write_bytes(b"human edit")
            with self.assertRaisesRegex(RuntimeError, "concurrently"):
                prep.save_manifest(manifest, ["paper_id"], [{"paper_id": "x"}], b"old")
            self.assertEqual(manifest.read_bytes(), b"human edit")

    def test_failure_is_recorded_and_success_never_marks_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = folder / "papers.csv"
            row = record()
            with manifest.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
            argv = ["prepare", "--paper-id", "CPMCM-TEST", "--download", "--cache-dir", str(folder / "cache")]
            with patch.object(prep, "MANIFEST", manifest), patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                with patch.object(prep, "acquire", side_effect=OSError("test failure")):
                    self.assertEqual(prep.main(), 1)
                self.assertEqual(prep.read_manifest(manifest)[1][0]["acquisition_status"], "failed")
                with patch.object(prep, "acquire", return_value=(folder / "fake.pdf", "digest")):
                    self.assertEqual(prep.main(), 0)
            result = prep.read_manifest(manifest)[1][0]
            self.assertEqual(result["acquisition_status"], "success")
            self.assertEqual(result["reading_status"], "unchecked")
            self.assertEqual(result["failure_reason"], "")
            self.assertFalse((folder / "cache/CPMCM-TEST/failure.json").exists())
            self.assertFalse(manifest.with_suffix(".csv.lock").exists())


if __name__ == "__main__":
    unittest.main()
