# 未知整图诊断与 bbox 修正契约

## 适用场景

用户提供一张没有 Layout Guide、没有可靠切片坐标的 UI 整图时，先诊断，再决定能否透明化和切割。不要直接猜测切片边界。

## 分类结果

| `classification` | 含义 | 可否直接进入修正导出 |
|---|---|---|
| `alpha-sheet` | 图片具有真实 Alpha | 可以 |
| `flat-background-sheet` | 边框和主体外区域为稳定纯色 | 可以，使用记录的色键参数 |
| `checkerboard-presentation` | 棋盘格已经烘焙进 RGB | 不可以；只能诊断候选，必须重新生成或提供真实 Alpha |
| `opaque-mixed-image` | 背景不稳定，可能含预览、文字、渐变或场景 | 不可以；需要更换输入或人工明确背景方案 |

假棋盘格检测失败必须返回非零退出码，但仍应写出诊断 JSON、候选 bbox 和标注预览，供 Codex 说明问题。

## 诊断命令

```powershell
& $PYTHON scripts/diagnose_ui_sheet.py `
  --input input/ui-sheet.png `
  --category Icon_Item `
  --json-out output/run/qa/input-diagnosis.json `
  --corrections-out output/run/qa/bbox-corrections.json `
  --preview-out output/run/qa/bbox-preview.png
```

诊断输出：

- `input-diagnosis.json`：背景类型、候选数量、问题和是否可导出。
- `bbox-corrections.json`：Codex 可直接编辑的修正模板。
- `bbox-preview.png`：候选编号和边界标注图。

## 修正文件规则

首次生成时 `approved` 必须为 `false`。Codex 或用户完成以下检查后才能改为 `true`：

- 候选数量正确。
- 每个 bbox 完整包住一个资源，且包含透明或色键安全留白。
- 没有两个启用 bbox 相互重叠。
- `semantic_name`、`category`、`state` 和 `category_index` 正确。
- 不需要的候选设置为 `enabled: false`，不得直接从文件中无说明删除。
- 分类内编号连续。
- 背景为 `alpha` 或已确认安全的 `flat-color`。

每个资源可以覆盖全局归一化配置：

```json
{
  "target_size": [128, 128],
  "padding": 8,
  "alignment": "center",
  "allow_upscale": false
}
```

## 应用修正

```powershell
& $PYTHON scripts/apply_bbox_corrections.py `
  --input input/ui-sheet.png `
  --corrections output/run/qa/bbox-corrections.json `
  --run-dir output/run `
  --project-id unknown-ui-pack
```

脚本必须拒绝：未批准修正、假棋盘格、未解析背景、bbox 越界或重叠、bbox 切断前景、空资源、文件重名、分类编号不连续、Manifest 不一致和可见色键残留。

通过后输出正式透明 PNG、`final/manifest.json`、Contact Sheet、QA 报告和运行摘要。该流程使用 JSON 和标注图完成修正，不依赖桌面 GUI。
