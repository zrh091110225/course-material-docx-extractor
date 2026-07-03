# Course Material DOCX Extractor

Codex skill for extracting structured Chinese course-material records from one `.docx` file with an LLM-assisted, validation-first workflow.

The safest flow is:

1. Split the `.docx` into LLM tasks.
2. Let an agent/LLM fill structured JSON results.
3. Validate the LLM output and generate CSV files.

The scripts do not call any model directly, so the skill does not depend on an SDK, API key, network access, or a specific model name.

## Install For Codex

Clone this repository into the Codex skills directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/zrh091110225/course-material-docx-extractor.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/course-material-docx-extractor"
```

Restart Codex or start a new thread so the skill list reloads.

## Verify Installation

```bash
test -f "${CODEX_HOME:-$HOME/.codex}/skills/course-material-docx-extractor/SKILL.md"
```

Optional validation:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py \
  "${CODEX_HOME:-$HOME/.codex}/skills/course-material-docx-extractor"
```

## Step 1: Generate LLM Tasks

```bash
cd "${CODEX_HOME:-$HOME/.codex}/skills/course-material-docx-extractor"
python3 scripts/extract_course_materials.py INPUT.docx --out-dir OUTPUT_DIR
```

If the filename does not contain an age hint, pass one:

```bash
python3 scripts/extract_course_materials.py INPUT.docx --age 5-6岁 --out-dir OUTPUT_DIR
```

This writes:

- `llm_tasks.jsonl`: one task per material block, with a ready-to-send prompt.
- `sections.jsonl`: raw section manifest for audit/debugging.
- `llm_prompt.md`: reusable prompt template.
- `llm_results.jsonl`: empty file to fill with LLM results.

If a material section ends with a Coze disclosure line such as `本内容由 Coze AI 生成...`, the splitter removes that line before writing tasks. The LLM should preserve the cleaned `素材原文` exactly.

## Step 2: Fill LLM Results

For each line in `llm_tasks.jsonl`, send the `prompt` value to an LLM.

Write one JSON object per line to `llm_results.jsonl`.

Success example:

```json
{"task_id":"numbered_card_001","result":{"status":"success","id":"numbered_card_001","标题":"鸭妈妈的向日葵","素材原文":"...","场景":"3-4 岁课堂,《丑小鸭》延伸课。","主角":"小番茄、鸭妈妈(老师扮演)","主题":"3 岁的孩子能不能听懂大人不想说的那种孤独","标签":"#共情早发生；#儿童反向照顾大人；#花的意象","年龄段":"3-4岁","适合产品":"线下会员新班；开放日","摘要":"..."}}
```

Manual-review example:

```json
{"task_id":"potential_001","result":{"status":"manual_review","标题":"跳跳和他的恐龙","reason":"适合产品无法明确判断","素材原文":"..."}}
```

The validator also accepts a direct result object as long as it contains `task_id`.

## Step 3: Validate And Write CSV

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

## Supported Source Structures

The splitter recognizes three heading styles:

### Structure 1: Growth Line

```text
A. 年糕这三年——一个孩子怎么慢慢学会"判断"
主题:5 岁的伦理学
...
可服务的主题:儿童伦理判断力的发展 / ...
标签:#年糕弧线 #判断力 #儿童哲学 #伦理学
```

### Structure 2: Potential Material

```text
P1. 跳跳和他的恐龙——"你是想听我的想法,还是恐龙的想法?"
素材瞬间:
...
为什么有潜力:...
待补访:...
可服务的主题:5 岁男孩的内心世界 / 过渡客体 / 玩具如何替孩子发声
```

### Structure 3: Story Card

```text
01. 鸭妈妈的向日葵
场景：3-4 岁课堂,《丑小鸭》延伸课。
主角：小番茄、鸭妈妈(老师扮演)
主题：3 岁的孩子能不能听懂大人不想说的那种孤独
...
标签：#共情早发生 #儿童反向照顾大人 #花的意象
```

## Validation Boundary

`validate_llm_results.py` does not trust the LLM blindly.

Successful rows are rejected into manual review when:

- required fields are empty
- `素材原文` is not an exact match for the cleaned task text
- `年龄段` contains values outside the allowed list
- `适合产品` contains values outside the allowed list
- the result is malformed, missing, or marked `manual_review`

The validator builds `检索文本` itself from the approved fields.

Allowed age bands:

```text
3-4岁, 4-5岁, 5-6岁, 6-7岁, 5-7岁, 7-8岁, 7-9岁, 9-11岁
```

Allowed products:

```text
线下会员新班, 抓马学习研究室, 开放日, 体验课
```

## Dependencies

The extractor and validator use only the Python standard library. No `python-docx`, Pandoc, OpenAI SDK, or platform-specific `textutil` dependency is required.
