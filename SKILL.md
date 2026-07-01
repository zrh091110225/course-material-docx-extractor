---
name: course-material-docx-extractor
description: Extract structured Chinese course-material records from a single .docx file into CSV, with a manual-review list for ambiguous records. Use when the user has one Word document containing story cards or course-material sections and wants fields such as 标题、素材原文、场景、主角、主题、标签、年龄段、适合产品、摘要、检索文本.
---

# Course Material DOCX Extractor

## Workflow

Use `scripts/extract_course_materials.py` for deterministic extraction from one `.docx` file.

```bash
python3 scripts/extract_course_materials.py INPUT.docx --out-dir OUTPUT_DIR
```

If the age cannot be inferred from the filename, pass it explicitly:

```bash
python3 scripts/extract_course_materials.py INPUT.docx --age 4-5岁 --out-dir OUTPUT_DIR
```

The script writes:

- `course_materials_extracted.csv`: rows with all required fields.
- `course_materials_manual_review.csv`: records with unclear or missing required information.
- `course_materials_manual_review.md`: the same manual-review list in a readable format.

## Expected Input

The strongest input format is a Word document where each material starts with a numbered heading such as `01. 标题`, followed by explicit field lines:

```text
场景：...
主角：...
主题：...
...
标签：#标签1 #标签2
```

The script also detects growth-line sections starting with `A. 标题`, but those usually go to manual review because they often span multiple ages and lack one clear scene.

## Field Rules

The output CSV keeps this fixed column order:

```text
id,标题,素材原文,场景,主角,主题,标签,年龄段,适合产品,摘要,检索文本
```

Use these enumerations:

- `适合产品`: `线下会员新班`、`抓马学习研究室`、`开放日`、`体验课`
- `年龄段`: `3-4岁`、`4-5岁`、`5-6岁`、`6-7岁`、`5-7岁`、`7-8岁`、`7-9岁`、`9-11岁`

`素材原文` must keep the complete material block, including title, explicit fields, body, and tags.

`检索文本` is built by joining title, scene, main characters, theme, tags, age, product values, and summary.

## Ambiguity Policy

Do not force records into the success CSV when required fields are unclear. Put them in the manual-review files with a short reason.

Common manual-review cases:

- missing `场景`、`主角`、`主题`、or `标签`
- age cannot be inferred and `--age` was not provided
- the section spans multiple ages or multiple scenes
- product fit is too ambiguous to assign from content
