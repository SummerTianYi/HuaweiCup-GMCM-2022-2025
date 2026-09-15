#!/usr/bin/env python3
"""Offline structure, link, identity and derived-statistics checks. No external requests."""
import argparse
import csv
import io
from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def rows(name):
    with (ROOT / "Resources" / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def snapshot():
    papers = rows("PAPER_MANIFEST.csv")
    codes = rows("CODE_DATA_SOURCES.csv")
    problems = rows("PROBLEM_MANIFEST.csv")
    coverage = rows("COVERAGE.csv")
    for item in coverage:
        key = item["year"], item["problem"]
        subset = [p for p in papers if (p["year"], p["problem"]) == key]
        full = [p for p in subset if p["resource_kind"] != "lead_only"]
        item["nf1"] = str(sum(p["award"] == "NF1" for p in full))
        item["participant"] = str(sum(p["award"].startswith("Participant") for p in full))
        item["excellent_leads"] = str(sum(p["resource_kind"] == "lead_only" for p in subset))
        item["code_sources"] = str(sum((p["year"], p["problem"]) == key for p in codes))
        item["problem_available"] = str(any((p["year"], p["problem"]) == key for p in problems))
    original = sum(p["resource_kind"] == "repository_original" for p in papers)
    external = sum(p["resource_kind"] == "external_fulltext" for p in papers)
    leads = sum(p["resource_kind"] == "lead_only" for p in papers)
    nf1 = sum(p["award"] == "NF1" and p["resource_kind"] != "lead_only" for p in papers)
    participants = sum(p["award"].startswith("Participant") and p["resource_kind"] != "lead_only" for p in papers)
    acquired = sum(p["acquisition_status"] == "success" for p in papers)
    extracted = sum(p["extraction_status"] in ("extracted", "needs_review") for p in papers)
    reviewed = sum(p["extraction_status"] == "needs_review" for p in papers)
    read = sum(p["reading_status"] == "close_read" for p in papers)
    block = (f"<!-- manifest-stats:start -->\n"
             f"- 论文记录：库内原件 **{original}**，外部全文 **{external}**（NF1 {nf1}、Participant {participants}），仅线索 **{leads}**。线索不计全文。\n"
             f"- 题目入口 **{len(coverage)}**；代码来源包 **{len(codes)}**，覆盖 **{len(set((p['year'], p['problem']) for p in codes))}** 题；数据含原始/派生/外部线索，详见各题。\n"
             f"- 状态记录：曾获取成功 **{acquired}**；逐页提取完成 **{extracted}**（其中 **{reviewed}** 待人工检查）；已精读 **{read}**。成功记录不保证临时缓存仍在。\n"
             f"<!-- manifest-stats:end -->")
    return papers, codes, problems, coverage, block


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Regenerate existing COVERAGE.csv and README statistics")
    args = parser.parse_args()
    papers, codes, problems, coverage, block = snapshot()
    errors = []
    keys = {(str(y), q) for y in range(2022, 2026) for q in "ABCDEF"}
    if len(coverage) != 24 or {(r["year"], r["problem"]) for r in coverage} != keys:
        errors.append("COVERAGE must contain 24 unique year/problem keys")
    ids = [p["paper_id"] for p in papers]
    if len(ids) != len(set(ids)) or not all(re.fullmatch(r"[A-Za-z0-9_-]+", value) for value in ids):
        errors.append("paper_id values must be unique, nonempty and path-safe")
    teams = [p["team_id"] for p in papers if p["team_id"]]
    if len(teams) != len(set(teams)):
        errors.append("Duplicate team_id; inspect paper versions before merging")
    for p in papers:
        key = p["year"], p["problem"]
        if key not in keys:
            errors.append(f"Invalid paper key: {p['paper_id']}")
        if p["team_id"] and not re.fullmatch(p["problem"] + p["year"][2:] + r"\d{9}", p["team_id"]):
            errors.append(f"Invalid or fabricated team_id: {p['paper_id']}")
        if p["resource_kind"] not in {"repository_original", "external_fulltext", "lead_only"}:
            errors.append(f"Invalid resource kind: {p['paper_id']}")
        if p["resource_kind"] == "external_fulltext" and not p["download_url"].startswith("https://"):
            errors.append(f"Missing direct download: {p['paper_id']}")
        if p["resource_kind"] == "lead_only" and (p["download_url"] or p["local_original_path"]):
            errors.append(f"Lead incorrectly claims original: {p['paper_id']}")
        if p["resource_kind"] == "repository_original":
            local = (ROOT / p["local_original_path"]).resolve()
            if not p["local_original_path"] or not local.is_relative_to(ROOT) or not local.is_file():
                errors.append(f"Missing library original: {p['paper_id']}")
        for field, allowed in {
            "acquisition_status": {"unchecked", "success", "failed", "unavailable"},
            "extraction_status": {"unchecked", "extracted", "needs_review", "failed"},
            "reading_status": {"unchecked", "close_read"},
            "code_relationship_status": {"unverified", "author_declared", "verified_same_file"},
        }.items():
            if p[field] not in allowed:
                errors.append(f"Invalid {field}: {p['paper_id']}")
        if p["reading_status"] == "close_read" and not p["reading_evidence"]:
            errors.append(f"Reading requires independently recorded evidence: {p['paper_id']}")
        for repo in filter(None, p["related_code_repos"].split(";")):
            if not any((c["year"], c["problem"], c["repo"]) == (*key, repo) for c in codes):
                errors.append(f"Unknown related code repo: {p['paper_id']} / {repo}")
        if not any((r["year"], r["problem"]) == key for r in problems):
            errors.append(f"No problem manifest join: {p['paper_id']}")
    for name in ["PROBLEM_MANIFEST.csv", "CODE_DATA_SOURCES.csv", "RESOURCE_MANIFEST.csv"]:
        for record in rows(name):
            key = record["year"], record["problem"]
            if key not in keys and not (record["year"] in {"2022", "2023", "2024", "2025"} and record["problem"] == "annual"):
                errors.append(f"Invalid resource join: {name} {key}")
    for year, problem in keys:
        for suffix in ["README.md", "Problem/README.md", "Excellent-Papers/README.md"]:
            if not (ROOT / year / problem / suffix).is_file():
                errors.append(f"Missing {year}/{problem}/{suffix}")
    internal_links = 0
    for path in ROOT.rglob("*.md"):
        if any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            continue
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if re.match(r"[a-zA-Z]+:", target) or target.startswith("#"):
                continue
            internal_links += 1
            if not (path.parent / unquote(target.split("#")[0])).exists():
                errors.append(f"Broken link: {path.relative_to(ROOT)} -> {target}")
    root_readme = ROOT / "README.md"
    text = root_readme.read_text(encoding="utf-8")
    pattern = r"<!-- manifest-stats:start -->.*?<!-- manifest-stats:end -->"
    found = re.search(pattern, text, re.S)
    if not found:
        errors.append("Missing generated-statistics markers")
    if args.refresh and not errors:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(coverage[0]))
        writer.writeheader()
        writer.writerows(coverage)
        (ROOT / "Resources/COVERAGE.csv").write_text(stream.getvalue(), encoding="utf-8", newline="")
        root_readme.write_text(re.sub(pattern, lambda _: block, text, flags=re.S), encoding="utf-8")
    else:
        if found and found.group() != block:
            errors.append("README statistics differ; run --refresh")
        if coverage != rows("COVERAGE.csv"):
            errors.append("COVERAGE differs from source manifests; run --refresh")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: {len(keys)} questions; {len(ids)} unique paper IDs; {internal_links} internal links; joins and statistics consistent. Offline only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
