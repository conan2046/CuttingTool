# CuttingTool

游戏 UI 位图资源生产与拆分工具。当前实现 `game-ui-asset-pipeline` Skill 的批量可执行核心链路：

```text
多分类任务规格
→ 自动拆分 Sheet 与 Layout Guide
→ GPT Image 资源 Sheet
→ 一键识别 Alpha/色键并切割
→ 尺寸归一化与总 Manifest
→ Contact Sheet、严格 QA、运行摘要
```

项目制作标准见 [AGENTS.md](AGENTS.md)，每次正式功能提交见 [CHANGELOG.md](CHANGELOG.md)。

## 当前能力

- 创建资源任务运行目录。
- 同一请求编排多个资源分类。
- 超过分类容量时自动拆分多张 Sheet，并保持按钮状态组不跨 Sheet。
- 生成确定性 Layout Guide 和 JSON 槽位坐标。
- 生成 GPT Image 2 资源 Sheet 提示词。
- 纯色色键转真实 Alpha。
- 根据边框色差分布自适应诊断并安全采用色键阈值。
- 软 Alpha 边缘和色键污染清理；除软遮罩过渡带外，背景邻域中符合色键—前景混合模型或存在色键通道优势的像素也会进行局部前景重建，无法安全重建的残边会透明化并计数。
- 在已知布局槽位内独立检测和切割资源。
- 智能合并近邻碎片；Panel、Button、128 图标、Skill 和 Effect 使用真实生产校准后的分类级比例与像素上限，避免大面板阈值失控。
- 远离碎片默认 warning；可通过显式 `fragment_policy` 接受受双重尺寸限制的小组件，组件仍保留并记录，不静默删除。
- 保留面板、边框和图标内部透明孔洞。
- 自动识别空槽、槽位边缘接触和额外组件。
- 按目标尺寸、留白和对齐方式归一化；RGBA 缩放使用预乘 Alpha，避免低 Alpha 色键像素在缩小时重新显色。
- 导出稳定命名的透明 PNG。
- 生成 Manifest、Contact Sheet 和 QA 报告。
- QA 同时检查近纯色键残留和连续色键通道偏色，避免只靠欧氏距离漏掉肉眼可见的绿边、品红边或青边。
- QA 检查整个可见主体的强色键通道优势；主体内部被模型画入色键反射时要求重生成，不用全图去色破坏纹理。
- 支持带稳定不透明核心的硬边部分透明光带；近色主体缺少稳定核心时继续安全失败。
- 组件检测统一使用最低可见 Alpha `16`，并显式拦截跨两个槽位中心的噪声桥接组件。
- 一键处理所有已生成 Sheet，自动输出总 Manifest 和 `run-summary.json`。
- 诊断没有布局信息的未知整图，识别真实 Alpha、纯色背景、假棋盘格和无法解析的混合背景。
- 输出可编辑 bbox JSON 和标注预览；候选框带编号、问题类型和严重级别，JSON 带字段级错误路径和阈值建议。
- 使用批准后的 bbox 直接生成透明资源包、Manifest、Contact Sheet 和 QA。
- 应用前拦截越界、重叠、可见前景裁断和编号错误；失败不写正式 Manifest，并生成修正前后差异预览。
- 九类标准资源均有静态 eval 和真实 Codex 新任务触发验收。

碎片策略真实校准样本位于 `output/p2-fragment-calibration`：面板、按钮、装备、技能共 16 件，包含尖角、链条、悬挂件、独立符文和硬边火花。

暂未实现：

- Unity 自动导入。
- 自动九宫格推断。
- 原生透明复杂特效链路（烟雾、玻璃、液体、柔光）；已提升为下一阶段最高优先级。
- 复杂混合展示图的自动语义分类和遮挡内容恢复。

## 路线优先级

1. P5 原生透明特效生成链路：烟雾、玻璃、液体、柔光四类真实 Alpha 生成、保真处理与端到端验收。
2. 完善 Codex 自然语言一键编排和稳定交付。
3. 根据真实生产任务继续优化色键诊断、碎片合并、JSON 修正、bbox 标注预览和 Contact Sheet。
4. 扩充复杂失败样本和跨风格回归矩阵。
5. 桌面 GUI：长期最低优先级。只有前述流程稳定完成，且高频人工操作无法通过现有轻量方式解决时才重新评估。

桌面 GUI 不是当前待开发功能，也不会作为核心流水线完成条件。

## Skill 源码

```text
D:\CuttingTool\skills\game-ui-asset-pipeline
```

完成验证后安装到：

```text
C:\Users\Admin\.codex\skills\game-ui-asset-pipeline
```

## Python 环境

使用 Codex 工作区捆绑 Python，不使用裸 `python`：

```powershell
$PYTHON = 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

当前依赖：

- Pillow
- NumPy

## 推荐：批量运行

请求格式见 [batch-request-contract.md](skills/game-ui-asset-pipeline/references/batch-request-contract.md)。

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\prepare_ui_batch.py `
  --request .\batch-request.json `
  --output-dir .\output\dark-fantasy-ui
```

按照 `output/dark-fantasy-ui/jobs.json` 逐张使用内置 `image_gen` 生成图片，并保存到各 Job 的 `generated_output`。全部图片就绪后运行：

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\run_ui_pipeline.py `
  --run-dir .\output\dark-fantasy-ui
```

Runner 输出：

```text
final/manifest.json
qa/contact-sheet.png
qa/qa-report.json
qa/run-summary.json
```

## 未知整图诊断与修正

没有 Layout Guide 的整图先运行：

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\diagnose_ui_sheet.py `
  --input .\input\ui-sheet.png `
  --category Icon_Item `
  --json-out .\output\unknown-ui\qa\input-diagnosis.json `
  --corrections-out .\output\unknown-ui\qa\bbox-corrections.json `
  --preview-out .\output\unknown-ui\qa\bbox-preview.png
```

检查候选编号、问题类型、严重级别和 JSON 中的字段定位/阈值建议，修改语义名、分类、状态、bbox 和启用状态；确认后设置 `approved=true`：

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\apply_bbox_corrections.py `
  --input .\input\ui-sheet.png `
  --corrections .\output\unknown-ui\qa\bbox-corrections.json `
  --run-dir .\output\unknown-ui `
  --project-id unknown-ui
```

详细规则见 [unknown-sheet-contract.md](skills/game-ui-asset-pipeline/references/unknown-sheet-contract.md)。假棋盘格只允许诊断，不允许冒充真实透明资源导出。

应用后额外输出：

```text
qa/correction-validation.json
qa/bbox-diff-preview.png
```

真实未知整图验收样本位于 `output/p3-unknown-sheet-real`：以一张没有 Layout Guide 的 12 件品红色键道具整图完成诊断、人工语义/bbox 修正、差异预览、透明导出和视觉 QA。

P4 真实复杂边缘回归位于 `output/p4-failure-matrix-real`：12 件 `Icon_Effect` 覆盖白金高光、黑紫深描边、硬边光带、环形孔洞和分离碎片。首版因主体内部绿色反射与低 Alpha 跨槽桥接被拒绝；重生成后 12 pass / 0 warning / 0 fail。

## 单分类调试流程

### 1. 创建运行目录

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\prepare_ui_run.py `
  --project-id 'Dark Fantasy UI' `
  --category Icon_Item `
  --asset 'HealthPotion|Default|small red health potion' `
  --asset 'ManaPotion|Default|small blue mana potion' `
  --asset 'FireCrystal|Default|orange fire crystal' `
  --asset 'TreasureChest|Default|dark iron and gold chest' `
  --grid 2x2 `
  --style-notes 'Dark medieval fantasy mobile ARPG UI' `
  --output-dir .\output\dark-fantasy-ui
```

生成：

```text
request.json
jobs.json
prompts/<sheet>.md
references/layout-guides/<sheet>.png
references/layout-guides/<sheet>.json
```

### 2. 生成资源 Sheet

读取 `prompts/<sheet>.md`，将 Canonical Style Reference 和 Layout Guide 作为角色明确的参考图传给内置 `$imagegen`。

将选中的结果复制到：

```text
generated/<sheet>.png
```

### 3. 色键转 Alpha

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\remove_chroma_key.py `
  --input .\output\dark-fantasy-ui\generated\icon-item-sheet-01.png `
  --output .\output\dark-fantasy-ui\extracted\icon-item-sheet-01-alpha.png `
  --chroma-key '#00FF00' `
  --adaptive-thresholds `
  --json-out .\output\dark-fantasy-ui\qa\chroma.json
```

统一 Runner 默认自动诊断阈值；低置信度或近色主体风险会阻止自动处理。只有人工已确认固定阈值时才使用 `--fixed-chroma-thresholds`。

### 4. 按槽位切割

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\extract_sheet_assets.py `
  --input .\output\dark-fantasy-ui\extracted\icon-item-sheet-01-alpha.png `
  --layout-json .\output\dark-fantasy-ui\references\layout-guides\icon-item-sheet-01.json `
  --request .\output\dark-fantasy-ui\request.json `
  --output-dir .\output\dark-fantasy-ui\extracted\assets `
  --manifest-out .\output\dark-fantasy-ui\extracted\manifest.json `
  --qa-out .\output\dark-fantasy-ui\qa\extract.json
```

### 5. 归一化

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\normalize_assets.py `
  --manifest .\output\dark-fantasy-ui\extracted\manifest.json `
  --request .\output\dark-fantasy-ui\request.json `
  --input-dir .\output\dark-fantasy-ui\extracted\assets `
  --output-dir .\output\dark-fantasy-ui\final\Icon_Item `
  --manifest-out .\output\dark-fantasy-ui\final\manifest.json
```

### 6. Contact Sheet 与 QA

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\make_contact_sheet.py `
  --manifest .\output\dark-fantasy-ui\final\manifest.json `
  --asset-root .\output\dark-fantasy-ui\final\Icon_Item `
  --output .\output\dark-fantasy-ui\qa\contact-sheet.png

& $PYTHON .\skills\game-ui-asset-pipeline\scripts\validate_asset_pack.py `
  --manifest .\output\dark-fantasy-ui\final\manifest.json `
  --asset-root .\output\dark-fantasy-ui\final\Icon_Item `
  --request .\output\dark-fantasy-ui\request.json `
  --json-out .\output\dark-fantasy-ui\qa\qa-report.json `
  --strict-files
```

## 测试

```powershell
& $PYTHON -m unittest discover `
  -s .\skills\game-ui-asset-pipeline\tests `
  -v
```

当前端到端合成样本：

```text
D:\CuttingTool\output\synthetic-e2e
```

该样本验证4个资源完整通过：透明化、切割、128×128归一化、命名、Manifest、Contact Sheet和严格QA。

金色/绿色色键、白色/品红色键、绿色/品红色键、深色/绿色色键抗锯齿矩阵，以及偏移色键、近色主体、污染边框、复杂纹理前景保持矩阵由 `test_chroma_antialias_matrix.py` 固定回归。交付 QA 额外覆盖连续色键通道偏色，归一化测试覆盖低 Alpha 色键像素不可在缩放后复活。九类 Skill 触发覆盖由 `evals/evals.json` 和 `test_skill_evals.py` 校验。
