# Course Material DOCX Extractor

Codex skill for extracting structured Chinese course-material records from one `.docx` file into CSV.

It produces:

- `course_materials_extracted.csv`: records with all required fields.
- `course_materials_manual_review.csv`: ambiguous records for human handling.
- `course_materials_manual_review.md`: readable manual-review list.

## Install For Codex

Clone this repository into the Codex skills directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/zrh091110225/course-material-docx-extractor.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/course-material-docx-extractor"
```

Restart Codex or start a new thread so the skill list reloads.

## Verify Installation

The skill is installed correctly when this file exists:

```bash
test -f "${CODEX_HOME:-$HOME/.codex}/skills/course-material-docx-extractor/SKILL.md"
```

Optional validation:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py \
  "${CODEX_HOME:-$HOME/.codex}/skills/course-material-docx-extractor"
```

## Use The Skill

In Codex, ask for:

```text
Use $course-material-docx-extractor to extract a course-material CSV from this .docx file.
```

Direct script usage:

```bash
cd "${CODEX_HOME:-$HOME/.codex}/skills/course-material-docx-extractor"
python3 scripts/extract_course_materials.py INPUT.docx --out-dir OUTPUT_DIR
```

If the age band cannot be inferred from the filename, pass it explicitly:

```bash
python3 scripts/extract_course_materials.py INPUT.docx --age 4-5岁 --out-dir OUTPUT_DIR
```

Allowed age bands:

```text
3-4岁, 4-5岁, 5-6岁, 6-7岁, 5-7岁, 7-8岁, 7-9岁, 9-11岁
```

## Expected DOCX Format

The extractor supports three structures.

### Structure 1: Growth Line

```text
A. 年糕这三年——一个孩子怎么慢慢学会"判断"
主题:5 岁的伦理学
...
可服务的主题:儿童伦理判断力的发展 / ...
标签:#年糕弧线 #判断力 #儿童哲学 #伦理学
```

This structure is treated as a multi-year arc. The extractor can infer multiple age bands such as `3-4岁；4-5岁；5-6岁`.

### Structure 2: Potential Material

```text
P1. 跳跳和他的恐龙——"你是想听我的想法,还是恐龙的想法?"
素材瞬间:
...
为什么有潜力:...
待补访:...
可服务的主题:5 岁男孩的内心世界 / 过渡客体 / 玩具如何替孩子发声
```

This structure is treated as a promising material draft. The extractor derives scene, main character, theme, tags, age band, product fit, and summary from the labeled sections.

### Structure 3: Story Card

```text
01. 标题
场景：...
主角：...
主题：...
正文...
标签：#标签1 #标签2
```

Sections that are missing required fields, span multiple ages/scenes, or cannot be assigned a clear product fit are written to the manual-review files instead of the success CSV.

## LLM Refinement

Agents may use LLM judgment after script extraction to refine semantic fields, especially for Structure 1 and Structure 2.

Good LLM refinement targets:

- `场景`: summarize into a concise factual scene, without inventing a lesson name.
- `主角`: infer from the title and repeated named subjects.
- `主题`: use `主题` or `可服务的主题`.
- `标签`: derive from explicit tags or service themes.
- `摘要`: write a concise factual summary from the original material.
- `适合产品`: choose only from `线下会员新班`、`抓马学习研究室`、`开放日`、`体验课`.

Do not let the LLM rewrite `素材原文`; keep it verbatim.

## Dependencies

The extractor uses only the Python standard library. No `python-docx`, Pandoc, or platform-specific `textutil` dependency is required.
