#!/usr/bin/env python3
"""Select, acquire and extract papers. No analysis, OCR or competition code execution."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "Resources/PAPER_MANIFEST.csv"
WARNING = "Text only; formulas, tables, figures and layout require checking the original PDF page. No OCR or close reading performed."


def read_manifest(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def save_manifest(path: Path, fields: list[str], rows: list[dict[str, str]], expected: bytes) -> bytes:
    # Refuse to overwrite edits made since this process read the file.
    if path.read_bytes() != expected:
        raise RuntimeError("Manifest changed concurrently; cache retained, no manifest overwrite")
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)
    return path.read_bytes()


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_pdf(path: Path, row: dict[str, str]) -> str:
    with path.open("rb") as stream:
        if not stream.read(1024).lstrip().startswith(b"%PDF-"):
            raise ValueError("Response is not a PDF (login page or download error possible)")
    if row["bytes"] and path.stat().st_size != int(row["bytes"]):
        raise ValueError("PDF byte count differs from manifest")
    actual = fingerprint(path)
    if row["sha256"] and actual != row["sha256"]:
        raise ValueError("PDF SHA256 differs from manifest; source record was not modified")
    return actual


def acquire(row: dict[str, str], folder: Path, timeout: float, max_bytes: int) -> tuple[Path, str]:
    target = folder / "original.pdf"
    if target.exists():
        return target, validate_pdf(target, row)
    if row["resource_kind"] == "repository_original":
        original = (ROOT / row["local_original_path"]).resolve()
        if not original.is_relative_to(ROOT) or not original.is_file():
            raise ValueError("Repository original path is missing or outside repository")
        return original, validate_pdf(original, row)
    address = row["download_url"]
    if row["resource_kind"] == "lead_only" or not address:
        raise ValueError("Only a source lead exists; no full-text download URL")
    if not address.startswith("https://"):
        raise ValueError("Only HTTPS download URLs are supported")
    partial = folder / "original.pdf.part"
    try:
        request = Request(address, headers={"User-Agent": "CPMCM-paper-preparation/1.0"})
        with urlopen(request, timeout=timeout) as response, partial.open("wb") as output:
            if not response.geturl().startswith("https://"):
                raise ValueError("Refusing a redirect to non-HTTPS")
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("Download exceeded --max-mb; increase explicitly if appropriate")
                output.write(chunk)
        actual = validate_pdf(partial, row)
        partial.replace(target)
        return target, actual
    finally:
        partial.unlink(missing_ok=True)


def page_flags(text: str, has_images: bool) -> list[str]:
    compact = "".join(text.split())
    flags = []
    if not compact:
        flags.append("empty_text")
    if len(compact) < 40:
        flags.append("sparse_text")
        if has_images:
            flags.append("possible_scan")
    suspicious = sum(c == "\ufffd" or "\ue000" <= c <= "\uf8ff" or
                     (ord(c) < 32 and c not in "\n\r\t") for c in text)
    if suspicious / max(len(compact), 1) > 0.02 or "(cid:" in text:
        flags.append("suspected_garbled_text")
    return flags


def extract(row: dict[str, str], pdf: Path, actual_hash: str, folder: Path) -> str:
    from pypdf import PdfReader  # --list and --download need only the standard library.

    reader = PdfReader(pdf)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("Encrypted PDF requires authorized manual access")
    page_count = len(reader.pages)
    if page_count == 0:
        raise ValueError("PDF has no pages")
    flags_by_page = []
    for physical_page, page in enumerate(reader.pages, 1):
        output = folder / f"page-{physical_page:04d}.json"
        record = None
        if output.exists():
            try:
                saved = json.loads(output.read_text(encoding="utf-8"))
                if (saved.get("pdf_sha256") == actual_hash and
                        saved.get("paper_id") == row["paper_id"] and
                        saved.get("physical_page") == physical_page and
                        isinstance(saved.get("text"), str) and
                        isinstance(saved.get("flags"), list)):
                    record = saved
            except (ValueError, OSError):
                pass  # Incomplete checkpoint is safely regenerated from the PDF.
        if record is None:
            text = page.extract_text() or ""
            # XObject detection is conservative: an image/form on a sparse page may be a scan.
            resources = page.get("/Resources")
            has_images = bool(resources and resources.get_object().get("/XObject"))
            flags = page_flags(text, has_images)
            record = {"paper_id": row["paper_id"], "source_url": row["url"],
                      "download_url": row["download_url"], "pdf_sha256": actual_hash,
                      "physical_page": physical_page, "text": text, "flags": flags,
                      "manual_review_required": bool(flags), "warning": WARNING}
            atomic_text(output, json.dumps(record, ensure_ascii=False, indent=2))
        if record["flags"]:
            flags_by_page.append({"physical_page": physical_page, "flags": record["flags"]})
    status = "needs_review" if flags_by_page else "extracted"
    atomic_text(folder / "extraction.json", json.dumps({
        "paper_id": row["paper_id"], "pdf_sha256": actual_hash, "pages": page_count,
        "status": status, "flagged_pages": flags_by_page, "warning": WARNING,
    }, ensure_ascii=False, indent=2))
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", choices=[str(y) for y in range(2022, 2026)])
    parser.add_argument("--problem", choices=list("ABCDEF"))
    parser.add_argument("--paper-id", action="append", help="Stable ID; can be repeated")
    parser.add_argument("--limit", type=int, help="Maximum number of selected records")
    parser.add_argument("--list", action="store_true", help="List metadata only; no writes/network")
    parser.add_argument("--download", action="store_true", help="Fetch selected originals")
    parser.add_argument("--extract", action="store_true", help="Fetch if needed, then extract page by page")
    parser.add_argument("--cache-dir", type=Path, default=Path(tempfile.gettempdir()) / "huaweicup-paper-cache")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--max-mb", type=int, default=100)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.timeout <= 0 or args.max_mb < 1:
        parser.error("--timeout and --max-mb must be positive")
    active = (args.download or args.extract) and not args.list
    if active and not (args.year or args.problem or args.paper_id):
        parser.error("Downloading/extraction requires --year, --problem or --paper-id; --limit alone is not a filter")
    fields, rows = read_manifest(MANIFEST)
    selected = [row for row in rows if (not args.year or row["year"] == args.year)
                and (not args.problem or row["problem"] == args.problem)
                and (not args.paper_id or row["paper_id"] in args.paper_id)]
    if args.paper_id:
        missing = set(args.paper_id) - {row["paper_id"] for row in selected}
        if missing:
            parser.error("Unknown IDs or IDs excluded by filters: " + ", ".join(sorted(missing)))
    if args.limit:
        selected = selected[:args.limit]
    if not active:
        for row in selected:
            print(json.dumps({k: row[k] for k in ("paper_id", "year", "problem", "title", "resource_kind",
                                                   "acquisition_status", "extraction_status", "reading_status",
                                                   "download_url")}, ensure_ascii=False))
        return 0
    if not selected:
        parser.error("No records match")
    cache = args.cache_dir.resolve()
    if cache.is_relative_to(ROOT) and not cache.is_relative_to(ROOT / ".cache/papers"):
        parser.error("Inside the repository, only ignored .cache/papers may hold originals/text")
    if args.extract:
        try:
            import pypdf  # noqa: F401
        except ImportError:
            parser.error("Extraction requires: python -m pip install -r scripts/requirements.txt")
    cache.mkdir(parents=True, exist_ok=True)
    lock = MANIFEST.with_suffix(".csv.lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        parser.error("Another preparation may be running; inspect the manifest lock before removing a stale lock")
    os.close(descriptor)
    expected = MANIFEST.read_bytes()
    failures = 0
    try:
        # Reload under the lock, preserving edits made while the command parsed arguments.
        fields, current = read_manifest(MANIFEST)
        by_id = {row["paper_id"]: row for row in current}
        for chosen in selected:
            row = by_id[chosen["paper_id"]]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", row["paper_id"]):
                raise ValueError("Unsafe paper_id")
            folder = cache / row["paper_id"]
            folder.mkdir(exist_ok=True)
            stage = "acquisition"
            try:
                pdf, actual = acquire(row, folder, args.timeout, args.max_mb * 1024 * 1024)
                row["acquisition_status"] = "success"
                if args.extract:
                    stage = "extraction"
                    row["extraction_status"] = extract(row, pdf, actual, folder)
                row["failure_reason"] = ""
            except (Exception, KeyboardInterrupt) as error:
                failures += 1
                row[stage + "_status"] = "failed"
                if stage == "acquisition" and row["resource_kind"] == "lead_only":
                    row["acquisition_status"] = "unavailable"
                row["failure_reason"] = (type(error).__name__ + ": " + str(error))[:500]
                if isinstance(error, KeyboardInterrupt):
                    row["failure_reason"] = "Interrupted; rerun the same selection to resume cached pages"
                atomic_text(folder / "failure.json", json.dumps({"paper_id": row["paper_id"],
                            "stage": stage, "reason": row["failure_reason"]}, ensure_ascii=False))
                if isinstance(error, KeyboardInterrupt):
                    row["last_checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    expected = save_manifest(MANIFEST, fields, current, expected)
                    return 130
            row["last_checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            # reading_status is deliberately never assigned by this script.
            expected = save_manifest(MANIFEST, fields, current, expected)
            if not row["failure_reason"]:
                (folder / "failure.json").unlink(missing_ok=True)
            print(json.dumps({k: row[k] for k in ("paper_id", "acquisition_status", "extraction_status",
                                                 "reading_status", "failure_reason")}, ensure_ascii=False))
    finally:
        lock.unlink(missing_ok=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
