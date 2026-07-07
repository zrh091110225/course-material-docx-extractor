#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
FIELD_LABELS = "素材瞬间|为什么有潜力|待补访|可服务的主题|场景|主角|主题|标签"

PROMPT_TEMPLATE = """你是课程素材结构化抽取助手。请从一段课程素材原文中抽取字段。

必须只输出 JSON，不要输出解释、Markdown 或代码块。

字段：
id, 标题, 素材原文, 场景, 主角, 主题, 标签, 年龄段, 适合产品, 摘要

允许年龄段：
3-4岁, 4-5岁, 5-6岁, 6-7岁, 5-7岁, 7-8岁, 7-9岁, 9-11岁

允许适合产品：
线下会员新班, 抓马学习研究室, 开放日, 体验课

规则：
1. 素材原文必须完整保留输入原文，不得改写、删减或规范化标点。
2. 场景可以从原文概括，但不能编造具体课程名。
3. 主角从标题、正文高频人物、角色中提取。
4. 主题从“主题”“可服务的主题”“为什么有潜力”或正文核心冲突中提炼。
5. 标签用中文 hashtag，多选，用中文分号连接。
6. 年龄段可从年龄表达推断，例如“5 岁”可归入“5-6岁”；三年成长线可多选。
7. 适合产品只能从枚举中选择；无法判断则 manual_review。
8. 摘要用 1-2 句话概括素材价值。
9. 如果关键字段不明确，输出 status=manual_review，并说明 reason。
10. 检索文本不要输出，由程序生成。

成功输出格式：
{"status":"success","id":"...","标题":"...","素材原文":"...","场景":"...","主角":"...","主题":"...","标签":"...","年龄段":"...","适合产品":"...","摘要":"..."}

人工处理输出格式：
{"status":"manual_review","id":"...","标题":"...","reason":"...","素材原文":"..."}
"""


@dataclass
class Section:
    source_path: Path
    heading: str
    lines: list[str]
    section_kind: str
    index: int


def read_docx_paragraphs(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as docx:
            xml_bytes = docx.read("word/document.xml")
    except KeyError as exc:
        raise ValueError(f"{path} is not a valid .docx file: missing word/document.xml") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{path} is not a valid .docx zip package") from exc

    root = ET.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:body/w:p", WORD_NS):
        parts: list[str] = []
        for node in paragraph.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "t" and node.text:
                parts.append(node.text)
            elif tag == "tab":
                parts.append("\t")
            elif tag in {"br", "cr"}:
                parts.append("\n")
        paragraphs.extend(split_embedded_fields(normalize_text("".join(parts))))
    return paragraphs


def split_embedded_fields(text: str) -> list[str]:
    if not text:
        return [text]
    text = re.sub(rf"\s+({FIELD_LABELS})\s*[:：]", r"\n\1:", text)
    return [part.strip() for part in text.split("\n")]


def normalize_text(text: str) -> str:
    return (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("------", "——")
        .replace("----", "——")
        .replace("“", '"')
        .replace("”", '"')
        .strip()
    )


def clean_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        text = normalize_text(line)
        if not text:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(text)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return cleaned


def normalize_title(heading: str) -> str:
    title = re.sub(r"^\d+\.\s*", "", heading.strip())
    title = re.sub(r"^P\d+\.\s*", "", title)
    title = re.sub(r"^[A-Z]\.\s*", "", title)
    return normalize_text(title)


def infer_age_hint(path: Path, explicit_age: str | None) -> str:
    if explicit_age:
        return explicit_age.strip()

    candidates = [
        r"(\d-\d)岁",
        r"(\d-\d)\s*岁",
        r"(\d-\d)",
    ]
    for pattern in candidates:
        match = re.search(pattern, path.name)
        if match:
            return f"{match.group(1)}岁"
    return ""


def split_sections(paragraphs: list[str], path: Path) -> list[Section]:
    starts: list[tuple[int, str, str]] = []
    for idx, paragraph in enumerate(paragraphs):
        stripped = paragraph.strip()
        if re.match(r"^\d+\.\s+", stripped):
            starts.append((idx, stripped, "numbered_card"))
        elif re.match(r"^P\d+\.\s+", stripped):
            starts.append((idx, stripped, "potential"))
        elif re.match(r"^[A-Z]\.\s+", stripped):
            starts.append((idx, stripped, "lettered_growth"))

    sections: list[Section] = []
    for pos, (start_idx, heading, kind) in enumerate(starts):
        end_idx = starts[pos + 1][0] if pos + 1 < len(starts) else len(paragraphs)
        lines = clean_lines(paragraphs[start_idx:end_idx])
        if lines:
            sections.append(Section(path, heading, lines, kind, pos + 1))
    return sections


def material_text(section: Section) -> str:
    return "\n".join(section.lines).strip()


def task_id(section: Section) -> str:
    number_match = re.match(r"^(\d+)\.", section.heading)
    potential_match = re.match(r"^P(\d+)\.", section.heading)
    letter_match = re.match(r"^([A-Z])\.", section.heading)
    if number_match:
        suffix = f"{int(number_match.group(1)):03d}"
    elif potential_match:
        suffix = f"{int(potential_match.group(1)):03d}"
    elif letter_match:
        suffix = letter_match.group(1).lower()
    else:
        suffix = f"{section.index:03d}"
    return f"{section.section_kind}_{suffix}"


def make_task(section: Section, age_hint: str) -> dict[str, str]:
    source_text = material_text(section)
    stable_id = task_id(section)
    prompt_input = {
        "task_id": stable_id,
        "结构类型": section.section_kind,
        "年龄段提示": age_hint,
        "标题提示": normalize_title(section.heading),
        "素材原文": source_text,
    }
    return {
        "task_id": stable_id,
        "source_file": str(section.source_path),
        "section_kind": section.section_kind,
        "heading": section.heading,
        "title_hint": normalize_title(section.heading),
        "age_hint": age_hint,
        "material_text": source_text,
        "prompt": PROMPT_TEMPLATE + "\n\n输入：\n" + json.dumps(prompt_input, ensure_ascii=False, indent=2),
    }


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split one .docx file into LLM extraction tasks for course-material CSV generation."
    )
    parser.add_argument("input_docx", type=Path, help="Path to one .docx file")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to <input-stem>_course_materials next to the input file.",
    )
    parser.add_argument(
        "--age",
        default=None,
        help="Optional age hint passed to the LLM, e.g. 5-6岁 or '3-4岁；4-5岁；5-6岁'.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    input_docx = args.input_docx.expanduser().resolve()
    if not input_docx.exists():
        print(f"input file does not exist: {input_docx}", file=sys.stderr)
        return 2
    if input_docx.suffix.lower() != ".docx":
        print(f"input file must be a .docx file: {input_docx}", file=sys.stderr)
        return 2

    out_dir = args.out_dir or input_docx.with_name(f"{input_docx.stem}_course_materials")
    age_hint = infer_age_hint(input_docx, args.age)

    try:
        paragraphs = read_docx_paragraphs(input_docx)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    sections = split_sections(paragraphs, input_docx)
    if not sections:
        print("no material sections found; expected headings like '01. 标题', 'P1. 标题', or 'A. 标题'", file=sys.stderr)
        return 1

    tasks = [make_task(section, age_hint) for section in sections]
    sections_rows = [
        {
            "task_id": row["task_id"],
            "source_file": row["source_file"],
            "section_kind": row["section_kind"],
            "heading": row["heading"],
            "title_hint": row["title_hint"],
            "age_hint": row["age_hint"],
            "material_text": row["material_text"],
        }
        for row in tasks
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "llm_tasks.jsonl"
    sections_path = out_dir / "sections.jsonl"
    prompt_path = out_dir / "llm_prompt.md"
    results_path = out_dir / "llm_results.jsonl"

    write_jsonl(tasks_path, tasks)
    write_jsonl(sections_path, sections_rows)
    prompt_path.write_text(PROMPT_TEMPLATE, encoding="utf-8")
    if not results_path.exists():
        results_path.write_text("", encoding="utf-8")

    print(f"tasks={len(tasks)}")
    print(tasks_path)
    print(sections_path)
    print(prompt_path)
    print(f"fill results here: {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
