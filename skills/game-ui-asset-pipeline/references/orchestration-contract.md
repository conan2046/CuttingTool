# P6 自然语言一键编排与交付摘要契约

## 定位

自然语言理解由 Codex 和本 Skill 完成，确定性脚本不实现伪 NLP。Codex 把用户描述转换为 `batch-request.json`，`orchestrate_ui_delivery.py` 负责准备、检查生成输入、断点续跑、执行 Runner 和汇总交付结果。

## 状态机

```text
unprepared
→ awaiting-generation
→ ready-for-processing
→ complete | awaiting-regeneration | failed
```

- `unprepared`：运行目录中没有 `request.json` 和 `jobs.json`，必须提供 `--request`。
- `awaiting-generation`：Prompt、Layout Guide 和 Job 已创建，但至少一个必需生成输入缺失；这是编排器内部待办状态，CLI 返回成功。Codex 应立即调用内置图片生成补齐，不向用户暂停。
- `ready-for-processing`：所有 Job 的必需生成输入就绪，编排器自动调用统一 Runner。
- `complete`：正式 Manifest、Contact Sheet、QA 和运行摘要均已生成且无 fail。
- `awaiting-regeneration`：V0.13 已把失败 Job 的最高优先级单一缺陷转换为纠错 Prompt 和替换路径；Codex 必须按计划重生成后自动续跑。
- `failed`：透明预检、切割、命名或 QA 失败；禁止把资源包报告为完成。

完整交付再次运行时直接复用现有结果，不重复处理。V0.13 计划内替代候选会自动覆盖失败运行；计划外人工覆盖已有正式 Manifest 时才必须显式使用 `--force-run`。

V0.13 为每个候选计算 SHA-256 指纹。同一失败候选重复调用不得增加次数；只有计划要求的输入发生变化才视为新候选。编排器检测到替代候选后自动覆盖失败运行，不要求用户手工添加 `--force-run`。

## V0.13 质量评分与定向重生成

- QA 同时输出 Run、Job、Asset 三级 `quality`，范围 `0–100`。
- 分数只用于候选排序；任一 `fail` 都是硬阻断，高分不得覆盖。
- 默认最多评估 3 个候选，可通过顶层 `retry_policy.max_attempts` 设置为 `1–5`。
- 每轮只选择一个最高优先级失败原因，禁止同时改变风格、布局和资源清单。
- 失败后写出 `qa/regeneration-plan.json/md` 和 `prompts/<job-id>-retry-<NN>.md`。
- 至少两个生产 Job 且存在 Canonical 时写出 `qa/style-consistency.json`，并在交付摘要记录跨 Sheet 风格分。
- 风格漂移按具体 Job 进入单原因重生成；自动分数不能替代 Contact Sheet 人工语义检查。
- 计划精确声明需要替换的生产 Sheet、Alpha Matte 或原生 Alpha 来源侧车。
- 候选耗尽后状态必须为 `failed`，不得交付最佳失败候选。

## 必需生成输入

| 透明模式 | 必需输入 |
|---|---|
| `chroma-key` | `generated/<job-id>.png` |
| `model-matte-derived` | 彩色 Sheet 和同尺寸 `-alpha-matte.png` |
| `native-alpha-required` | RGBA Sheet 和 `.provenance.json` 来源侧车 |

编排器必须按 Job 返回精确缺失路径、Prompt、参考图角色和 Matte 编辑源。Codex 逐项生成并按精确路径保存，然后自动续跑；不得只返回“素材不齐”或让用户手工续跑。

## 命令

首次准备：

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\orchestrate_ui_delivery.py `
  --request .\batch-request.json `
  --run-dir .\output\<project-id>
```

补齐生成图后续跑：

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\orchestrate_ui_delivery.py `
  --run-dir .\output\<project-id>
```

只有明确修正并需要覆盖已有正式结果时使用 `--force-run`。

## 交付摘要

每次调用都更新：

```text
qa/delivery-summary.json
qa/delivery-summary.md
```

摘要至少包含：

- 当前状态和生成方式。
- Job 总数、已就绪数和待处理数。
- 必需输入总数、就绪数和精确缺失路径。
- 预期、导出、pass、warning、fail 数量。
- 正式资源目录、Manifest、Contact Sheet、QA 和运行摘要路径。
- 人工处理项与下一步动作。
- 质量分、硬阻断数、Job 候选历史和定向重生成计划。

所有路径相对于运行目录，禁止把个人绝对路径写成唯一定位信息。

## 验收矩阵

- 首次自然语言请求能生成批量请求并进入 `awaiting-generation`。
- 同一运行目录支持补图后续跑，不重复建立 Job。
- 同一请求至少覆盖一个色键分类和一个 Matte 分类。
- 原生 Alpha Job 缺少来源侧车时保持等待，不提前进入 Runner。
- Matte 预检失败后替换输入可恢复完成。
- 完成态重复调用为幂等复用。
- 失败候选能生成单原因纠错 Prompt；原文件未变化时保持等待且不重复计次。
- 替换计划指定输入后自动重跑；候选耗尽后保持硬失败。
- 质量分不能覆盖 `fail`，Run、Job、Asset 分值均可追溯。
- `delivery-summary.json`、Markdown 摘要、Manifest、Contact Sheet 和 QA 路径一致。
