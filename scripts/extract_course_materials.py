#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


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

ALLOWED_AGES = {
    "3-4岁",
    "4-5岁",
    "5-6岁",
    "6-7岁",
    "5-7岁",
    "7-8岁",
    "7-9岁",
    "9-11岁",
}

ALLOWED_PRODUCTS = {
    "线下会员新班",
    "抓马学习研究室",
    "开放日",
    "体验课",
}

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@dataclass
class Section:
    source_path: Path
    heading: str
    lines: list[str]
    section_kind: str


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
        paragraphs.append(normalize_text("".join(parts)))
    return paragraphs


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
    title = re.sub(r"^[A-Z]\.\s*", "", title)
    return normalize_text(title)


def infer_age(path: Path, explicit_age: str | None) -> str:
    if explicit_age:
        return explicit_age

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
            starts.append((idx, stripped, "numbered"))
        elif re.match(r"^[A-Z]\.\s+", stripped):
            starts.append((idx, stripped, "lettered"))

    sections: list[Section] = []
    for pos, (start_idx, heading, kind) in enumerate(starts):
        end_idx = starts[pos + 1][0] if pos + 1 < len(starts) else len(paragraphs)
        lines = clean_lines(paragraphs[start_idx:end_idx])
        if lines:
            sections.append(Section(path, heading, lines, kind))
    return sections


def extract_field(lines: list[str], field: str) -> str:
    pattern = re.compile(rf"^\s*\**{re.escape(field)}\**\s*[:：]\s*(.+?)\s*$")
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return ""


def normalize_tags(tag_line: str) -> str:
    tags = re.findall(r"#[^\s#；;，,、]+", tag_line)
    if tags:
        return "；".join(tags)
    return "；".join(part.strip() for part in re.split(r"[；;，,、\s]+", tag_line) if part.strip())


def summarize(lines: list[str], title: str) -> str:
    body_lines = [
        line
        for line in lines[1:]
        if not re.match(r"^\s*\**(场景|主角|主题|标签)\**\s*[:：]", line)
    ]
    body = " ".join(line for line in body_lines if line).strip()
    if not body:
        return ""

    sentences = re.split(r"(?<=[。！？!?])\s*", body)
    summary = "".join(sentences[:2]).strip()
    if summary:
        return summary[:180]
    return f"{title}：{body[:160]}".strip()


def infer_products(title: str, scene: str, theme: str, tags: str, summary: str) -> list[str]:
    haystack = " ".join([title, scene, theme, tags, summary])
    products: list[str] = []

    research_keywords = [
        "哲学",
        "伦理",
        "判断",
        "权力",
        "公共",
        "政治",
        "认识论",
        "复杂",
        "压抑",
        "群体",
        "身份",
        "本质",
        "成长弧线",
    ]
    trial_keywords = [
        "开场",
        "轻松",
        "暖身",
        "颜色",
        "味道",
        "巨人",
        "恐龙",
        "爸爸唱",
        "想象",
        "怪兽",
        "宫廷",
        "自由",
    ]
    open_day_keywords = [
        "金句",
        "第一次",
        "意象",
        "孤独",
        "共情",
        "分离",
        "妈妈",
        "爸爸",
        "投票",
        "看见",
        "情绪",
        "害羞",
        "被遗忘",
    ]

    if any(keyword in haystack for keyword in research_keywords):
        products.append("抓马学习研究室")
    if any(keyword in haystack for keyword in trial_keywords):
        products.append("体验课")
    if any(keyword in haystack for keyword in open_day_keywords):
        products.append("开放日")

    if "课堂" in haystack or "课" in scene:
        products.append("线下会员新班")

    deduped: list[str] = []
    for product in products:
        if product in ALLOWED_PRODUCTS and product not in deduped:
            deduped.append(product)
    return deduped


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


def section_id(age: str, section: Section, fallback_index: int) -> str:
    age_part = re.sub(r"[^0-9]", "", age) or "unknown"
    number_match = re.match(r"^(\d+)\.", section.heading)
    if number_match:
        index = int(number_match.group(1))
    else:
        index = fallback_index
    return f"course_material_{age_part}_{index:03d}"


def material_text(section: Section) -> str:
    return "\n".join(section.lines).strip()


def convert_section(section: Section, age: str, index: int) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    title = normalize_title(section.heading)
    scene = extract_field(section.lines, "场景")
    main_characters = extract_field(section.lines, "主角")
    theme = extract_field(section.lines, "主题")
    tags = normalize_tags(extract_field(section.lines, "标签"))
    summary = summarize(section.lines, title)
    products = infer_products(title, scene, theme, tags, summary)

    row = {
        "id": section_id(age, section, index),
        "标题": title,
        "素材原文": material_text(section),
        "场景": scene,
        "主角": main_characters,
        "主题": theme,
        "标签": tags,
        "年龄段": age,
        "适合产品": "；".join(products),
        "摘要": summary,
        "检索文本": "",
    }

    reasons: list[str] = []
    if section.section_kind != "numbered":
        reasons.append("非编号故事卡，可能跨越多个场景或年龄段")
    if age not in ALLOWED_AGES:
        reasons.append("年龄段缺失或不在允许枚举内")
    for field in ["标题", "素材原文", "场景", "主角", "主题", "标签", "适合产品", "摘要"]:
        if not row[field]:
            reasons.append(f"缺少或无法明确判断字段：{field}")

    if reasons:
        return None, {
            "来源文件": str(section.source_path),
            "标题": title,
            "原因": "；".join(reasons),
            "素材原文": row["素材原文"],
        }

    row["检索文本"] = build_search_text(row)
    return row, None


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
    parser = argparse.ArgumentParser(
        description="Extract structured course-material CSV records from a single .docx file."
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
        choices=sorted(ALLOWED_AGES),
        default=None,
        help="Age band to use when it cannot be inferred from the filename.",
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
    age = infer_age(input_docx, args.age)

    try:
        paragraphs = read_docx_paragraphs(input_docx)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    sections = split_sections(paragraphs, input_docx)
    rows: list[dict[str, str]] = []
    manual_rows: list[dict[str, str]] = []
    if not sections:
        manual_rows.append(
            {
                "来源文件": str(input_docx),
                "标题": input_docx.stem,
                "原因": "未找到以“01. 标题”或“A. 标题”开头的素材段",
                "素材原文": "\n".join(clean_lines(paragraphs)),
            }
        )
    else:
        for index, section in enumerate(sections, start=1):
            row, manual_row = convert_section(section, age, index)
            if row:
                rows.append(row)
            if manual_row:
                manual_rows.append(manual_row)

    out_dir.mkdir(parents=True, exist_ok=True)
    extracted_path = out_dir / "course_materials_extracted.csv"
    manual_csv_path = out_dir / "course_materials_manual_review.csv"
    manual_md_path = out_dir / "course_materials_manual_review.md"

    write_csv(extracted_path, rows, FIELDS)
    write_csv(manual_csv_path, manual_rows, MANUAL_FIELDS)
    write_manual_md(manual_md_path, manual_rows)

    print(f"extracted_rows={len(rows)}")
    print(f"manual_rows={len(manual_rows)}")
    print(extracted_path)
    print(manual_csv_path)
    print(manual_md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
