# P6 自然语言一键编排与交付摘要契约

## 定位

自然语言理解由 Codex 和本 Skill 完成，确定性脚本不实现伪 NLP。Codex 把用户描述转换为 `batch-request.json`，`orchestrate_ui_delivery.py` 负责准备、检查生成输入、断点续跑、执行 Runner 和汇总交付结果。

## 状态机

```text
unprepared
→ awaiting-generation
→ ready-for-processing
→ complete | failed
```

- `unprepared`：运行目录中没有 `request.json` 和 `jobs.json`，必须提供 `--request`。
- `awaiting-generation`：Prompt、Layout Guide 和 Job 已创建，但至少一个必需生成输入缺失；这是正常暂停状态，CLI 返回成功。
- `ready-for-processing`：所有 Job 的必需生成输入就绪，编排器自动调用统一 Runner。
- `complete`：正式 Manifest、Contact Sheet、QA 和运行摘要均已生成且无 fail。
- `failed`：透明预检、切割、命名或 QA 失败；禁止把资源包报告为完成。

完整交付再次运行时直接复用现有结果，不重复处理。失败后替换生成输入即可续跑；若失败流程已经写出正式 Manifest，修正后必须显式使用 `--force-run`。

## 必需生成输入

| 透明模式 | 必需输入 |
|---|---|
| `chroma-key` | `generated/<job-id>.png` |
| `model-matte-derived` | 彩色 Sheet 和同尺寸 `-alpha-matte.png` |
| `native-alpha-required` | RGBA Sheet 和 `.provenance.json` 来源侧车 |

编排器必须按 Job 返回精确缺失路径、Prompt、参考图角色和 Matte 编辑源。不得只返回“素材不齐”一类模糊信息。

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

所有路径相对于运行目录，禁止把个人绝对路径写成唯一定位信息。

## 验收矩阵

- 首次自然语言请求能生成批量请求并进入 `awaiting-generation`。
- 同一运行目录支持补图后续跑，不重复建立 Job。
- 同一请求至少覆盖一个色键分类和一个 Matte 分类。
- 原生 Alpha Job 缺少来源侧车时保持等待，不提前进入 Runner。
- Matte 预检失败后替换输入可恢复完成。
- 完成态重复调用为幂等复用。
- `delivery-summary.json`、Markdown 摘要、Manifest、Contact Sheet 和 QA 路径一致。
