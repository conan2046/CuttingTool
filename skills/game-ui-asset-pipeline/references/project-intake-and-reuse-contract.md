# 项目界面确认、资源清单与复用契约

## 目标

把参考图分析、一次性用户确认、资源清单、跨界面复用和批量请求连成连续流程。最终目标始终是产出用户需求的美术资源，不把 Markdown、JSON 或中间状态当作交付终点。

## 唯一必要确认

参考图自动检查和逐图视觉分析通过后，Codex 汇总一次询问并等待用户确认：

- 每个界面的布局参考图与布局是否确认。
- UI 元素造型是否与主参考一致。
- 不一致时的明确差异与仍需继承的视觉部分。
- 每个完整 UI 界面的目标像素尺寸，例如 `1920×1080`。

不要拆成多轮逐项追问。用户已在需求中明确的内容直接带入确认摘要，不重复询问。

## 自动回写

用户确认后，由 Codex 生成结构化分析 JSON，并运行：

```powershell
& $PYTHON scripts/compile_ui_project_intake.py `
  --project-dir D:\CuttingTool\input\<project-id> `
  --analysis D:\CuttingTool\input\<project-id>\reference-analysis.json
```

脚本自动更新：

- `references/reference-notes.md`
- `ui-resource-inventory.md`
- `ui-resource-inventory.json`
- `batch-request.json`

`reference-notes.md` 的自动维护区由 Codex更新；已有人工文字保留在自动区外。不得让用户填写模板或要求用户再次发出“请完善说明文件”。

## 跨界面复用

- 项目的第一个 UI 界面列出的资源全部进入生成清单。
- 后续界面按 `category + semantic_name + state` 判定是否已有资源。
- 目标尺寸不参与复用判定；Unity 可在导入后缩放。
- 已有资源标记为 `reuse`，从本次前序界面或 `ui-asset-catalog.json` 记录 `reuse_asset_id`、`reuse_output` 和 `reuse_source_run`。
- 未命中的资源标记为 `generate`。
- 同一新资源在多个后续界面出现时只生成一次，其余界面引用本次待生成资源。
- 语义不确定或状态不同不得强行复用；宁可生成新资源，也不要仅凭外观相似误判。

完成 Runner 且 QA 无 fail 后，`orchestrate_ui_delivery.py` 自动把正式 Manifest 合并到：

```text
input/<project-id>/ui-asset-catalog.json
```

## 自动续行

`compile_ui_project_intake.py` 成功后立即读取 `batch-request.json`：

- `all_assets_reused=true`：跳过生成，直接交付引用清单。
- 存在待生成资源：立即运行编排器，按缺图清单调用内置图片生成，保存到精确路径，再次运行编排器直到 `complete` 或出现真实失败。

除了项目名、参考图放置、上述一次性界面确认、参考图不合格替换和不可安全推断的重大歧义，不向用户停顿。

## 分阶段入口

根据用户已有输入从最靠后的安全阶段开始，不强制回到第一步：

| 用户已有内容 | 起点 | 执行 |
|---|---|---|
| 只有需求/参考图 | `intake` | 参考图分析、确认、清单、生成与交付 |
| 已有批准清单或批量请求 | `generation` | 编排器准备 Job，图片生成，Runner |
| 已有带 Layout Guide 的 Sheet | `processing` | 直接 Runner |
| 已有未知整图 | `unknown-sheet` | 诊断、bbox 修正、导出 |
| 已有透明 PNG 和 Manifest | `qa-only` | Contact Sheet 与严格 QA |
| 已有运行目录 | `resume` | 编排器断点续跑 |

从后段进入仍必须执行该阶段之后的全部 QA，不得因跳过前段而跳过正式验收。
