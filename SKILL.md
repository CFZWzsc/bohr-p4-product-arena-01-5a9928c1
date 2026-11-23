---
name: bohr-reading-literature-translation
description: 当需要把科研论文翻译成可核验的双语对照结果时使用。本题范围：文献翻译（术语表锁定、长文分段、双语段落对照、数字/单位/公式/引用保护、译文核验）。产出 result.json，包含运行时 output_contract 要求的全部字段，每段译文可指回原文段落与逐字短引，译不准或原文未报告的部分如实写入 uncertainty。
---

# 阅读03｜文献翻译：科研阅读：回答问题，也给出依据

## 用途

本题属于 **literature-reading（reading）** 赛道，题目是「文献翻译」。目标能力：把真实科研论文翻译成**可核验的双语对照结果**，确保术语、段落结构、数字、引用和公式在翻译后仍可回查。

重点覆盖四个问题（题面原文）：

- **术语稳**：同一术语在标题、摘要、正文、图注和结论中始终使用同一译名；术语表要被真正执行，而不是只写在提示里。
- **段落全**：长文跨页、跨栏、跨章节时不漏段、不重复、不错位，段号与原文一一对应。
- **关系准**：指代对象、否定与限定条件、因果与让步关系、数字单位、公式与文献编号与原文一致。
- **可核验**：每段译文能指回原文并说明译法依据；译不准的部分明确标注，不含混处理。

可选择术语一致性、长文分段翻译、双语对照、译文核验等方向，形成能够真实运行、独立验证的最小成果，不要求完整翻译系统。

本 Skill 在 DeepSeek Harness 中被加载到 `/skills/weekly-skill`。
Harness 会在 3 个固定科研案例上分别调用它；每个案例的输入是
`/input/case.json`（含 `task_instruction` 与 `output_contract`）、`task.md`
与同目录下的科研材料。

## 任务要求（来自题面）

1. 先识别输入材料与问题边界，确认源语言、目标语言、原文段落边界与段号。
2. **术语表驱动**：从原文抽取领域术语，建立术语表（原文术语 → 目标语译名 → 出现位置 → 依据）；全篇锁定同一译名，标题、摘要、正文、图注、结论一致。
3. **分段翻译**：按语义边界切分长文，携带上下文与已确定术语逐段翻译；跨页、跨栏、章节衔接处不漏段、不重复、不错位。
4. **双语对照**：输出原文与译文的段落级对应关系，保留段号与句子边界，支持定位回看与逐段修改。
5. **保护不译内容**：数字、单位、公式、图表编号、文献引用标记、化学式与专有标识按原文保留；必要时原样嵌入译文。
6. **译文核验**：检查数字、单位、公式、图表编号、文献引用、否定关系和限定条件是否保留；列出需要人工确认的清单。
7. 原文残缺、语言混杂、无文字层或术语无通行译名时，标注为待确认，不擅自补全。

本题可预知的契约键（来自题面「Skill 运行后的输出要求」，另有部分键按**同赛道兄弟题的公开接口推断**；**实际以运行时 `/input/case.json` 为准**，下表仅供预热）：

- `case_id`
- `case_identifiers`
- `translation_result`
- `translated_segments`
- `glossary`
- `findings`
- `evidence`
- `coverage`
- `status`
- `uncertainties`

题面没有规定固定的 JSON 键名；因此**不要硬编码**，按运行时契约键名语义填充。

## 交付物

result.json（契约齐全：译文、段落对照、术语表、核验发现、证据、不确定性）、run-review.md（证据索引 + 术语与核验记录）、anomaly-report.json（异常自报，输入提供 `target-fields.json` 时）。

交付物的**内容契约**由运行时 `output_contract` 决定（见下）；下面「交付物落盘
要求」给出的是必须真实存在的**文件**。

## 执行方式

入口脚本：`scripts/sk_entry.py`。它会读取 `/input`，产出 `/app/output/result.json`。

```bash
# 在案例环境中执行（Harbor 会自动调用；手动复现同一条命令）
python /skills/weekly-skill/scripts/sk_entry.py \
  --input /input --work /app/work --out /app/output
```

执行结束后必须存在且可解析：

- `/app/output/result.json` —— 契约字段齐全的最终结果
- `/app/output/run-review.md` —— 人类可读的证据索引与不确定性清单（复核用）

### 两阶段工作流（重要：脚本只做取证，判断由你做）

脚本是**确定性**的：它读材料、切段落、建证据索引、按契约键名填字段。它**不做**
领域判断 —— 术语该译成什么、长句怎么切分、译法依据是什么，这些必须由你
（执行 Agent）来做。所以本 Skill 的完整用法是**跑两次**：

```bash
# 阶段 A：脚本取证，产出结果骨架 + 任务单
python /skills/weekly-skill/scripts/sk_entry.py \
  --input /input --work /app/work --out /app/output

# 阶段 B：你读 /app/work/agent_tasks.json，写 /app/work/agent_judgement.json

# 阶段 C：脚本再跑一次，把你的判断校验后合并进 result.json
python /skills/weekly-skill/scripts/sk_entry.py \
  --input /input --work /app/work --out /app/output
```

> **重跑前先移走阶段 A 的 `result.json`**（例如
> `mv /app/output/result.json /app/work/phase-a-result.json`）。脚本会优先采纳
> 旧 `result.json` 里已有的契约键；若不先移走，你通过 `contract_fields` 写入的
> 领域内容会被阶段 A 的骨架覆盖。

**阶段 A 之后**，`/app/work/agent_tasks.json` 会告诉你：

| 字段 | 内容 |
|---|---|
| `contract_keys` / `contract_semantics` | 本案例的契约键，以及每个键该装什么 |
| `evidence_anchors` | 全部段落 id + 原文短引（你的证据只能从这里取） |
| `draft_claims` / `open_questions` | 脚本机械抽到的候选论断与待答问题 |
| `what_to_judge` | 本题需要你判断的四件事 |
| `how_to_write_the_judgement` | 判断文件的结构与规则 |

**阶段 B** —— 有两种写法，**任选其一**：

**(a) 写判断文件**（推荐，校验最严格）—— `/app/work/agent_judgement.json`：

```json
{
  "case_id": "必须与 case.json 一致",
  "claims": [
    {"text": "你判断为结论的陈述",
     "evidence": [{"paragraph_id": "P002", "quote": "原文里逐字出现的片段"}]}
  ],
  "answers": [
    {"question": "被问的问题", "answer": "你的回答",
     "evidence": [{"paragraph_id": "P002", "quote": "原文里逐字出现的片段"}]}
  ],
  "deliverable": "本题最终交付物的正文",
  "contract_fields": {"契约键名": "该键的内容（可选，直接填契约键）"},
  "uncertainties": [
    {"kind": "machine_readable_category", "item": "具体对象",
     "detail": "客观描述", "resolution": "你做了什么或为何无法继续"}
  ]
}
```

**(b) 直接写 `/app/output/result.json`** —— 也支持，脚本会把你写进去的契约键
**取出来**（先留底，再合并），同样过引文校验。你的 `result.json` 不会被覆盖。

> 两种写法都会被采纳；**不要**两个都不做 —— 那就只剩机械抽取，`status` 停在 `partial`。

**阶段 C 的校验闸门（脚本强制执行）**：

- 每条 `quote` 必须能在材料原文里**逐字找回**（允许空白差异）—— 找不到就**退回**，
  并把退回理由写进 `uncertainty`；
- 每条 claim / answer 必须至少有一个证据锚点 —— 没有锚点的条目被退回；
- `contract_fields` 的值不能是 `null` 或空容器 —— 空值被退回；
- 被退回的条目**不会**进入最终结果，脚本保留自己的确定性抽取作为兜底。

> 判断可以自由，**证据不可以自由**。这条闸门是本 Skill 的可信度基础。

只有完成阶段 B，脚本才会把 `status` 从 `partial` 升到 `answered`；否则结果里的
`uncertainty` 会保留一条 `judgement_pending`，如实说明"只做了机械抽取，尚未判断"。

### 脚本职责

| 脚本 | 职责 |
|---|---|
| `scripts/sk_entry.py` | 入口：定位输入、发现材料、执行 `topic.run()`、装配 `result.json`、自检并写复核产物 |
| `scripts/sk_base.py` | 公共库：契约解析、材料发现、证据构造、结果装配、自检工具 |
| `scripts/topic.py` | 题目逻辑：读材料 → 建证据索引 → 按契约键名语义产出字段 → 校验并合并你的判断 |
| `scripts/specialize.py` | reading / writing 引擎：逐 `field_id` 抽取（四态状态）；可编辑稿件 + 改动记录 + 来源映射 |
| `scripts/artifacts.py` | graphics 引擎：实体—连接—步骤 IR → 分层 SVG → 渲染 PNG + 来源记录 |
| `scripts/pptxgen.py` | slides 引擎：stdlib-only 真实 PPTX + 逐页 SVG/PNG + 独立讲稿备注 |

**这些引擎会真的写文件。** 每条赛道具体落盘哪些文件、每个文件里有什么、
如何回挂到契约键，见 `references/artifact-pipeline.md`。

### 运行时契约是唯一权威

`output_contract` **只在运行时可见**（`/input/case.json`）。
不要硬编码任何字段名，也不要凭题面示例臆造字段：

1. 读取 `/input/case.json` 的 `output_contract`；
2. 对每个契约键，按**键名语义**判断它应该承载什么（证据 / 结论 / 不确定性 /
   交付物 / 覆盖度 / 变更记录 …）；
3. 产出对应内容，**不允许**留下 `null` 或"未产出"占位；
4. 若该键确实无法从材料得出，填入结构化的"无法判断"条目（带 `kind`、`item`、
   `detail`、`resolution`），而不是留空。

## 交付物落盘要求

除 `result.json` 外，**可编辑的交付物源文件与其渲染预览必须真实存在**：

| 赛道 | 必须落到 `/app/output` 的文件 |
|---|---|
| reading | `result.json`（契约齐全的结构化结果） |
| reading | `run-review.md`（证据索引 + 不确定性清单） |
| reading | `answers[]` / `target_fields[]`：若输入提供 `target-fields.json`，则逐 `field_id` 一项，状态取 `reported` / `not_reported` / `source_conflict` / `extraction_failed` |
| reading | `anomaly-report.json` —— 异常自报：各状态计数、逐条异常原因、正文与表格取值冲突、每个取值的表格行列定位 |

平台提供的 `office-renderer` / `pdf-render-tool` / `latex-compiler` 可用来渲染预览。
**只有规格描述、没有真实文件，等于没交付** —— 评审要打开文件看。

### 导出前合规检查（pre-export compliance）

导出件落盘后，本 Skill 会**自动核对**并在 `*-export-checks.json` 里留档，
让评审不必逐个打开文件猜：

| 检查维度 | 记什么 |
|---|---|
| 目标格式 | 期望的 SVG / PNG / PDF 是否齐全、各自字节数、是否是**真矢量** |
| 画布与分辨率 | 像素尺寸 → pt → mm 换算，实测 dpi，目标 dpi |
| 字体 | 字体清单、嵌入情况、中文回退策略、是否存在方框/缺字风险 |
| 色彩空间 | 色彩空间标注（sRGB 等）与是否有嵌入配置 |
| 线宽 / 分层 | 线宽是否过细、图层是否可拆、图层清单 |
| 数据一致性 | 图上出现的数值与源数据表的比对结果 |
| 讲稿隔离 | 备注文字是否混进页面文字（逐页最大重叠片段） |
| 人工确认 | 需人眼确认的项一律标 `pending_human_review`，**不代签** |

失败的检查项会**原样保留为 fail**，不会被改写成通过；不可用的工具（如运行时
没有矢量转换器或 LibreOffice）也如实记为 `unavailable`，不做假成功。

## 质量红线

- **术语锁定**：术语表里的术语全篇使用同一译名；标题、摘要、正文、图注、结论逐处核对，出现变体必须修正或标注。
- **段落一一对应**：每个原文段落都有译文，段号稳定；不漏段、不重复、不合并相邻段落。
- **保护不译项**：数字、单位、公式、图表编号、文献引用标记、化学式按原文保留；不得改写或四舍五入。
- **关系保真**：否定、限定条件、因果与让步关系与原文一致；指代对象明确，不张冠李戴。
- **译法可核验**：每段译文能指回原文段号 + 逐字短引，并说明术语或难句的译法依据。
- **不擅补**：原文未报告的内容不补译；无通行译名的术语保留原文并标注 `pending_human_review`。
- 每条 claim 都有 paragraph_id + 原文 quote。

通用红线（违反即失分）：

- **不编造**：材料没有的数字、引用、图表、方法、结论，一律不写。写不出来就进
  `uncertainty`，并在 `status_reason` 里说明。
- **可回溯**：每条结论必须能指回原文的段落 id 与短引；引文必须是原文片段，
  不做改写、不做拼接。
- **不提前交卷**：材料可能读不全。若只读到部分文件，`status` 应为 `partial`，
  并在 `coverage.not_read` 写明未读的部分。
- **不自评**：不要在结果里写"质量良好""得分很高"这类自评语句。

## 失败与边界

| 情况 | 正确处理 |
|---|---|
| 材料是扫描件、无文本层 | 用 `scripts/sk_base.py` 的 PDF 解析；仍无文本则 `status=unsupported` 并在 `uncertainty` 写明"无文本层" |
| 材料是图片/图表 | 用平台提供的 `pdf-render-tool` / `ocr-tool`；OCR 结果标注为推断 |
| 材料格式未知 | 记录文件路径与可读性，不猜测内容 |
| 契约键无法解读 | 产出该键的结构化说明而非空值，并记录在 `uncertainty` |

详见 `references/failure-modes.md` 与 `references/evidence-discipline.md`。

## 自检

`result.json` 写完后由 `scripts/sk_entry.py` 自动自检（结构、契约覆盖、
证据完整性）。自检失败时以 `partial` 提交并在 `status_reason` 写明原因，
不要伪造 `answered`。

除自动自检外，人工复核以下各项：术语表译名是否全篇一致；段落数是否与原文
一致且无重复；数字/单位/公式/引用是否原样保留；否定与限定条件是否保留；
每段译文是否都能指回原文；未译或待确认项是否进入 `uncertainties`。

```bash
python /skills/weekly-skill/scripts/sk_selftest.py --input /input
```

## 参考

- `references/evidence-discipline.md` —— 证据与不确定性纪律
- `references/contract-handling.md` —— 运行时契约的读法与字段语义表
- `references/two-phase-workflow.md` —— 两阶段工作流协议与校验闸门
- `references/failure-modes.md` —— 常见失败模式与正确退路
- `references/artifact-pipeline.md` —— 每条赛道真实落盘哪些文件、怎么回挂契约键
- `assets/result-schema.md` —— `result.json` 的字段说明
- `assets/policy.json` —— 不编造承诺与来源声明
- `examples/demo-case/` —— 一个可离线复现的最小案例
