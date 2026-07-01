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

Best results come from `.docx` files where each material starts with a numbered heading:

```text
01. 标题
场景：...
主角：...
主题：...
正文...
标签：#标签1 #标签2
```

Sections that are missing required fields, span multiple ages/scenes, or cannot be assigned a clear product fit are written to the manual-review files instead of the success CSV.

## Dependencies

The extractor uses only the Python standard library. No `python-docx`, Pandoc, or platform-specific `textutil` dependency is required.
