---
name: course-material-docx-extractor
description: Extract structured Chinese course-material records from a single .docx file using an LLM-assisted, validation-first workflow. Use when the user has one Word document containing story cards, potential material, or growth-line course-material sections and wants CSV fields such as 标题、素材原文、场景、主角、主题、标签、年龄段、适合产品、摘要、检索文本.
---

# Course Material DOCX Extractor

## Workflow

Use a two-step flow. The scripts do not call any model or require API keys.

Step 1: split the `.docx` into LLM tasks.

```bash
python3 scripts/extract_course_materials.py INPUT.docx --out-dir OUTPUT_DIR
```

This writes:

- `llm_tasks.jsonl`: one task per source material block, including a ready-to-send prompt.
- `sections.jsonl`: raw section manifest for audit.
- `llm_prompt.md`: reusable prompt template.
- `llm_results.jsonl`: empty file to fill with LLM results.

Step 2: have the agent/LLM process every task and write `llm_results.jsonl`.

Each result line may use either shape:

```json
{"task_id":"numbered_card_001","result":{"status":"success","id":"numbered_card_001","标题":"...","素材原文":"...","场景":"...","主角":"...","主题":"...","标签":"...","年龄段":"3-4岁","适合产品":"线下会员新班；开放日","摘要":"..."}}
```

```json
{"task_id":"potential_001","result":{"status":"manual_review","标题":"...","reason":"适合产品无法明确判断","素材原文":"..."}}
```

Step 3: validate LLM output and write CSV files.

```bash
python3 scripts/validate_llm_results.py \
  --tasks OUTPUT_DIR/llm_tasks.jsonl \
  --results OUTPUT_DIR/llm_results.jsonl \
  --out-dir OUTPUT_DIR
```

This writes:

- `course_materials_extracted.csv`
- `course_materials_manual_review.csv`
- `course_materials_manual_review.md`

## Supported Structures

The splitter recognizes these headings:

- Structure 1: `A. 年糕这三年——...` as `lettered_growth`
- Structure 2: `P1. 跳跳和他的恐龙——...` as `potential`
- Structure 3: `01. 鸭妈妈的向日葵` as `numbered_card`

The LLM receives the structure type, title hint, age hint, and verbatim source material.

## LLM Rules

The prompt in `llm_tasks.jsonl` instructs the LLM to:

- output JSON only
- preserve `素材原文` exactly
- extract or infer `场景`、`主角`、`主题`、`标签`、`年龄段`、`适合产品`、`摘要`
- output `manual_review` when key information is unclear
- avoid generating `检索文本`; the validator builds it

Allowed `年龄段` values:

```text
3-4岁, 4-5岁, 5-6岁, 6-7岁, 5-7岁, 7-8岁, 7-9岁, 9-11岁
```

Allowed `适合产品` values:

```text
线下会员新班, 抓马学习研究室, 开放日, 体验课
```

## Validation Rules

`validate_llm_results.py` is the trust boundary. It rejects successful rows when:

- required fields are empty
- `素材原文` does not exactly match the original task material
- `年龄段` contains values outside the allowed list
- `适合产品` contains values outside the allowed list
- the LLM result is missing, malformed, or marked `manual_review`

Rejected rows go to the manual-review outputs with a reason.
