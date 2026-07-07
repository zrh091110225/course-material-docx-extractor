#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


FIELDS = [
    "id",
    "标题",
    "素材原文",
    "场景",
    "主角",
    "主题",
    "标签",
    "年龄段",
    "适合产品",
    "摘要",
    "检索文本",
]

MANUAL_FIELDS = ["来源文件", "标题", "原因", "素材原文"]

AGE_ORDER = ["3-4岁", "4-5岁", "5-6岁", "6-7岁", "5-7岁", "7-8岁", "7-9岁", "9-11岁"]
ALLOWED_AGES = set(AGE_ORDER)
PRODUCT_ORDER = ["线下会员新班", "抓马学习研究室", "开放日", "体验课"]
ALLOWED_PRODUCTS = set(PRODUCT_ORDER)


class StrictCsvError(ValueError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            rows.append(value)
    return rows


def extract_result(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    task_id = str(row.get("task_id") or row.get("id") or "").strip()
    result = row.get("result", row)
    if isinstance(result, str):
        result = parse_json_from_text(result)
    if not isinstance(result, dict):
        result = {}
    if not task_id:
        task_id = str(result.get("task_id") or result.get("id") or "").strip()
    return task_id, result


def parse_json_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def normalize_multivalue(value: Any, allowed: set[str], order: list[str]) -> str:
    if isinstance(value, list):
        raw_parts = [str(item).strip() for item in value]
    else:
        raw_parts = [part.strip() for part in re.split(r"[；;/,，、\s]+", str(value or "")) if part.strip()]
    unique_parts = list(dict.fromkeys(raw_parts))
    ordered = [item for item in order if item in unique_parts]
    ordered.extend(item for item in unique_parts if item not in ordered)
    return "；".join(item for item in ordered if item in allowed)


def split_multivalue(value: str) -> list[str]:
    return [part for part in value.split("；") if part]


def build_search_text(row: dict[str, str]) -> str:
    parts = [
        row["标题"],
        row["场景"],
        row["主角"],
        row["主题"],
        row["标签"],
        row["年龄段"],
        row["适合产品"],
        row["摘要"],
    ]
    return " ".join(part for part in parts if part)


def make_manual(source: dict[str, Any], title: str, reason: str, material_text: str) -> dict[str, str]:
    return {
        "来源文件": str(source.get("source_file", "")),
        "标题": title or str(source.get("title_hint", "")),
        "原因": reason,
        "素材原文": material_text or str(source.get("material_text", "")),
    }


def validate_result(task_id: str, result: dict[str, Any], source: dict[str, Any]) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    material_text = str(source.get("material_text", ""))
    status = str(result.get("status", "")).strip().lower()
    title = str(result.get("标题") or result.get("title") or source.get("title_hint", "")).strip()

    if status == "manual_review":
        reason = str(result.get("reason") or "LLM 标记为人工处理").strip()
        return None, make_manual(source, title, reason, material_text)

    row = {
        "id": str(result.get("id") or task_id).strip(),
        "标题": title,
        "素材原文": str(result.get("素材原文") or ""),
        "场景": str(result.get("场景") or "").strip(),
        "主角": str(result.get("主角") or "").strip(),
        "主题": str(result.get("主题") or "").strip(),
        "标签": str(result.get("标签") or "").strip(),
        "年龄段": normalize_multivalue(result.get("年龄段"), ALLOWED_AGES, AGE_ORDER),
        "适合产品": normalize_multivalue(result.get("适合产品"), ALLOWED_PRODUCTS, PRODUCT_ORDER),
        "摘要": str(result.get("摘要") or "").strip(),
        "检索文本": "",
    }

    reasons: list[str] = []
    if status and status != "success":
        reasons.append(f"未知 status：{status}")
    for field in ["id", "标题", "素材原文", "场景", "主角", "主题", "标签", "年龄段", "适合产品", "摘要"]:
        if not row[field]:
            reasons.append(f"缺少或无法明确判断字段：{field}")
    if row["素材原文"] != material_text:
        reasons.append("素材原文与任务原文不完全一致")
    if not split_multivalue(row["年龄段"]) or any(age not in ALLOWED_AGES for age in split_multivalue(row["年龄段"])):
        reasons.append("年龄段不在允许枚举内")
    if not split_multivalue(row["适合产品"]) or any(product not in ALLOWED_PRODUCTS for product in split_multivalue(row["适合产品"])):
        reasons.append("适合产品不在允许枚举内")

    if reasons:
        return None, make_manual(source, title, "；".join(reasons), material_text)

    row["检索文本"] = build_search_text(row)
    return row, None


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)


def check_strict_csv(path: Path, fieldnames: list[str]) -> None:
    raw = path.read_text(encoding="utf-8-sig")
    errors: list[str] = []
    in_quotes = False
    at_field_start = True
    record = 1
    line = 1
    col = 0
    index = 0

    while index < len(raw):
        char = raw[index]
        if char == "\n":
            line += 1
            col = 0
        else:
            col += 1

        if in_quotes:
            if char == '"':
                if index + 1 < len(raw) and raw[index + 1] == '"':
                    index += 1
                    col += 1
                else:
                    in_quotes = False
            index += 1
            continue

        if char == '"':
            if at_field_start:
                in_quotes = True
            else:
                errors.append(f"record {record}, line {line}, column {col}: bare quote in non-quoted field")
            at_field_start = False
            index += 1
            continue

        if char == ",":
            at_field_start = True
            index += 1
            continue
        if char in "\r\n":
            record += 1
            at_field_start = True
            index += 1
            continue
        at_field_start = False
        index += 1

    if in_quotes:
        errors.append("unterminated quoted field")

    with path.open(encoding="utf-8-sig", newline="") as input_file:
        reader = csv.reader(input_file, strict=True)
        try:
            rows = list(reader)
        except csv.Error as exc:
            errors.append(f"csv parser error: {exc}")
            rows = []

    if rows:
        if rows[0] != fieldnames:
            errors.append(f"CSV header mismatch: {rows[0]!r}")
        expected_width = len(fieldnames)
        for idx, row in enumerate(rows[1:], start=2):
            if len(row) != expected_width:
                errors.append(f"line {idx}: expected {expected_width} columns, got {len(row)}")

    if errors:
        raise StrictCsvError(f"{path} is not strict CSV: " + "; ".join(errors[:5]))


def write_manual_md(path: Path, rows: list[dict[str, str]]) -> None:
    lines = ["# 课程素材人工处理清单", "", f"共 {len(rows)} 条。", ""]
    for idx, row in enumerate(rows, start=1):
        lines.extend(
            [
                f"## {idx}. {row['标题']}",
                "",
                f"- 来源文件：{row['来源文件']}",
                f"- 原因：{row['原因']}",
                "",
                "### 素材原文",
                "",
                row["素材原文"],
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate LLM extraction JSONL and write final CSV outputs.")
    parser.add_argument("--tasks", type=Path, required=True, help="Path to llm_tasks.jsonl generated by extract_course_materials.py")
    parser.add_argument("--results", type=Path, required=True, help="Path to llm_results.jsonl filled by an agent/LLM")
    parser.add_argument("--out-dir", type=Path, default=None, help="Output directory. Defaults to the results file directory.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    out_dir = args.out_dir or args.results.parent

    try:
        task_rows = read_jsonl(args.tasks)
        result_rows = read_jsonl(args.results)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    sources = {str(row.get("task_id", "")): row for row in task_rows}
    results_by_task: dict[str, dict[str, Any]] = {}
    result_errors: list[dict[str, str]] = []
    for result_row in result_rows:
        task_id, result = extract_result(result_row)
        if not task_id:
            result_errors.append(make_manual({}, "", "LLM 结果缺少 task_id", ""))
            continue
        results_by_task[task_id] = result

    rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    manual_rows: list[dict[str, str]] = result_errors
    for task_id, source in sources.items():
        result = results_by_task.get(task_id)
        if result is None:
            manual_rows.append(make_manual(source, str(source.get("title_hint", "")), "缺少对应 LLM 结果", str(source.get("material_text", ""))))
            continue
        row, manual_row = validate_result(task_id, result, source)
        if row:
            if row["id"] in seen_ids:
                manual_rows.append(make_manual(source, row["标题"], f"id 重复：{row['id']}", str(source.get("material_text", ""))))
            else:
                seen_ids.add(row["id"])
                rows.append(row)
        if manual_row:
            manual_rows.append(manual_row)

    extracted_csv = out_dir / "course_materials_extracted.csv"
    manual_csv = out_dir / "course_materials_manual_review.csv"
    write_csv(extracted_csv, rows, FIELDS)
    write_csv(manual_csv, manual_rows, MANUAL_FIELDS)
    try:
        check_strict_csv(extracted_csv, FIELDS)
        check_strict_csv(manual_csv, MANUAL_FIELDS)
    except StrictCsvError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    write_manual_md(out_dir / "course_materials_manual_review.md", manual_rows)

    print(f"validated_tasks={len(sources)}")
    print(f"extracted_rows={len(rows)}")
    print(f"manual_rows={len(manual_rows)}")
    print(f"strict_csv=passed")
    print(extracted_csv)
    print(manual_csv)
    print(out_dir / "course_materials_manual_review.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
