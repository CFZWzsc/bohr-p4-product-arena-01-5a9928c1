---
name: glossary-locked-translator
description: Use when a scientific paper must be translated with a locked glossary and auditable equivalence — build the glossary, align bilingual paragraphs, protect numbers/citations/units/math, and emit /app/output/result.json keeping case_id and all output_contract fields.
---

# 术语锁定式科研论文翻译与等价审计

## 用途与适用条件

把英文科研论文（或指定段落）转成中文译文时，保证术语一致、数字与引用不变、单位与公式不被改写，并交付可人工复核的双语对照表与审计报告。适用于方法、结果、讨论等连续正文；不适用于图表内文字、需要排版还原的 PDF 版式、以及诗歌/营销文案。

职责分工：脚本负责分段、抽取受保护片段、建立术语表与等价审计；**译文属于必须交付的成品**——调用 Agent 必须在运行时逐段翻译（遵循锁定术语与 `target_language`），把完整译文写入 `result.translation_table[].translation` 并交付双语对照表，然后再用脚本审计。若输入未提供译文，不得把整篇留作 `pending_translation`：仅对确实无法读取的段落登记该状态并说明原因，其余段落必须由 Agent 译出。

## 输入

- `/input/case.json`（可用 `--case`）：包含
  - `source_text` 或 `paragraphs[]`（`{id, text}`）——原文；
  - `translations[]`（`{id, text}`，与段落 id 对齐）或 `translation_table`——已有译文，可缺省；
  - `glossary`：`[{term, target, variants[], case_sensitive}]` 或 `{term: target}`；
  - `target_language`（默认 `zh`）、`style`（可选）。
- `task.md`：`/input/task.md` 优先，字段名与格式以它为准。

## 处理流程（对应评分维度）

1. **分段与对齐（实际效果）**：先用输入段落 id；无 id 时按空行分段并生成稳定 id `S01…`。检测译文 id 是否一一对应，缺段/多段进入 `findings`。
2. **受保护片段抽取（结果正确性、创新增益）**：识别数字+单位、百分比、范围、引用 `[12]`、`(Author et al., 2020)`、DOI/URL、行内公式 `$…$`、基因/蛋白符号、模型与试剂编号。原文与译文分别抽取，做多重集比较。
3. **术语表构建**：合并输入术语；补充 `全称 (ABC)` 形式的缩写对；每个术语记录出现次数、目标译名、变体。术语表未覆盖的高频专有名词列入 `glossary_gaps`，不擅自翻译。
4. **等价审计（实际效果、可靠体验）**：
   - 数值集合：原文每个数字必须在译文出现（允许全角/空格差异）；
   - 单位集合：单位符号必须保留；
   - 引用/公式/链接：必须逐字保留；
   - 术语：原文出现术语时译文必须使用锁定译名，出现禁用变体即报 `term_variant`；
   - 长度比：译文/原文长度比落在 [0.25, 2.5] 之外报 `length_outlier`；
   - 未译拉丁词比例 > 0.4 报 `possible_untranslated`（仅提示复核）。
5. **状态判定（可靠体验）**：每段 `verified`（全部通过）、`needs_review`（仅提示级问题）、`failed_equivalence`（数值/引用/公式丢失）、`pending_translation`（无译文）。
6. **交付（使用增益、生态贡献）**：双语表按段输出 `source`、`translation`、`protected`、`findings`、`status`；汇总 `audit_summary` 计数；所有结论附段 id 与片段证据。

## 输出契约

顶层保留 `case_id` 与原始 `output_contract` 的每个字段（未映射字段为 `null` 并写入 `contract_notes`），并包含：

- `status`：`success` / `partial` / `insufficient_input` / `failed`
- `result.translation_table[]`：`id`、`source`、`translation`、`status`、`protected`、`findings[]`
- `result.glossary[]`：`term`、`target`、`variants`、`occurrences`、`target_occurrences`
- `result.audit_summary`：各状态计数、问题类型计数、覆盖率
- `glossary_gaps`、`findings`、`uncertainty`、`limitations`、`errors`、`stats`

## 异常处理

| 情形 | 行为 |
|---|---|
| 无原文 | `status=insufficient_input`，`errors` 说明 |
| 输入未提供译文 | 调用 Agent 逐段译出并写入 `translation_table[].translation`，再运行脚本审计；只有无法读取的段落标 `pending_translation` |
| 译文 id 对不上 | 保留两方，`findings` 报 `alignment_mismatch`，不猜对应 |
| 术语表为空 | 继续，输出 `glossary_gaps` 提示 |
| 输入含 HTML/LaTeX 标记 | 原样保留在受保护片段，不剥离 |
| 输出失败 | 结构化错误，退出码 2 |

## 限制与不适用

- 脚本本身不内置机器翻译模型；译文由调用 Agent 在运行时产出并写入结果，脚本只做等价审计；不评价文风与学术表达质量。
- 不做版式还原（脚注、双栏、图表内文字）。
- 同义词替换判断仅基于提供的术语表与变体，不能发现表外语义漂移。
- 长度比阈值是提示性规则，不单独作为失败依据。

## 最小调用示例（示例）

**示例（合成数据，非官方案例）**：

```bash
python /skills/weekly-skill/scripts/run_skill.py --case /input/case.json --out /app/output/result.json
```

输入含 `paragraphs:[{"id":"P1","text":"We used 5 mg catalyst [3]."}]`、`translations:[{"id":"P1","text":"我们使用 5 mg 催化剂 [3]。"}]` 时，输出该段 `status=verified`，并保留契约字段与 `case_id`。

## 自查清单

- [ ] 段落 id、契约字段、`case_id` 全部保留。
- [ ] 数字/单位/引用/公式多重集比较结果可复现。
- [ ] 术语命中与变体均带段 id 证据。
- [ ] 无译文时未伪造译文。
- [ ] 未声称运行官方固定案例。


## 交付保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--output` 指定。
2. 再完成脚本无法自动完成的实质工作（译文、论述、图表、修订、结论等），把结果写回 `result.json` 对应字段。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 为 `completed`（仅在确实缺输入时为 `partial`）；无 `pending` 占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **调用 Agent 必须交付成品，不是流程说明**：脚本产出只是索引、核对或规格骨架；调用 Agent 必须在同一 `result.json` 中补齐本题要求的最终产物（正文/译文/审稿意见/综述/分析结论/图表源文件与导出件/幻灯片页内容与讲稿/实验方案等）。交付字段为空、只有标题骨架，或含 `pending`、`TODO` 之类占位，一律视为未完成。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。
