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

The extractor supports three source structures.

### Structure 1: Growth Line

```text
A. 年糕这三年——一个孩子怎么慢慢学会"判断"
主题:5 岁的伦理学
...
可服务的主题:儿童伦理判断力的发展 / ...
标签:#年糕弧线 #判断力 #儿童哲学 #伦理学
```

Use this for multi-year child or group development arcs. The script infers a growth-arc scene, extracts the main character from the title/content, and can assign multiple age bands such as `3-4岁；4-5岁；5-6岁`.

### Structure 2: Potential Material

```text
P1. 跳跳和他的恐龙——"你是想听我的想法,还是恐龙的想法?"
素材瞬间:
...
为什么有潜力:...
待补访:...
可服务的主题:5 岁男孩的内心世界 / 过渡客体 / 玩具如何替孩子发声
```

Use this for promising but not fully formalized material. The script derives scene, main character, theme, tags, age band, product fit, and summary from the labeled sections.

### Structure 3: Story Card

```text
01. 鸭妈妈的向日葵
场景：3-4 岁课堂,《丑小鸭》延伸课。
主角：小番茄、鸭妈妈(老师扮演)
主题：3 岁的孩子能不能听懂大人不想说的那种孤独
...
标签：#共情早发生 #儿童反向照顾大人 #花的意象
```

Use this for the most reliable extraction. Explicit `场景`、`主角`、`主题`、`标签` values are preferred over inferred values.

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

## LLM Refinement

After running the script, an agent may use LLM judgment to refine semantic fields for Structures 1 and 2:

- refine `场景` into one concise sentence without inventing a specific lesson name
- refine `主角` from the title and repeated named subjects
- refine `主题` from `主题` or `可服务的主题`
- derive `标签` from `标签` or `可服务的主题`
- write `摘要` from the source material, keeping it factual and concise
- choose `适合产品` only from the allowed enumeration

Do not let the LLM change `素材原文`. Keep it verbatim.

## Ambiguity Policy

Do not force records into the success CSV when required fields are unclear. Put them in the manual-review files with a short reason.

Common manual-review cases:

- missing `场景`、`主角`、`主题`、or `标签`
- age cannot be inferred and `--age` was not provided
- the section spans multiple ages or multiple scenes
- product fit is too ambiguous to assign from content
