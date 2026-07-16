# CuttingTool

游戏 UI 位图资源生产与拆分工具。当前实现 `game-ui-asset-pipeline` Skill 的第一套可执行核心链路：

```text
任务规格
→ Layout Guide
→ GPT Image 资源 Sheet
→ 色键转 Alpha
→ 已知槽位切割
→ 尺寸归一化
→ Contact Sheet
→ 严格 QA
```

项目制作标准见 [AGENTS.md](AGENTS.md)。

## 当前能力

- 创建资源任务运行目录。
- 生成确定性 Layout Guide 和 JSON 槽位坐标。
- 生成 GPT Image 2 资源 Sheet 提示词。
- 纯色色键转真实 Alpha。
- 软 Alpha 边缘和色键污染清理。
- 在已知布局槽位内独立检测和切割资源。
- 保留面板、边框和图标内部透明孔洞。
- 自动识别空槽、槽位边缘接触和额外组件。
- 按目标尺寸、留白和对齐方式归一化。
- 导出稳定命名的透明 PNG。
- 生成 Manifest、Contact Sheet 和 QA 报告。

暂未实现：

- 桌面 GUI。
- Unity 自动导入。
- 自动九宫格推断。
- 复杂半透明特效的完全自动处理。
- 混合展示图的智能区域分类。

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

## 1. 创建运行目录

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

## 2. 生成资源 Sheet

读取 `prompts/<sheet>.md`，将 Canonical Style Reference 和 Layout Guide 作为角色明确的参考图传给内置 `$imagegen`。

将选中的结果复制到：

```text
generated/<sheet>.png
```

## 3. 色键转 Alpha

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\remove_chroma_key.py `
  --input .\output\dark-fantasy-ui\generated\icon-item-sheet-01.png `
  --output .\output\dark-fantasy-ui\extracted\icon-item-sheet-01-alpha.png `
  --chroma-key '#00FF00' `
  --json-out .\output\dark-fantasy-ui\qa\chroma.json
```

## 4. 按槽位切割

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\extract_sheet_assets.py `
  --input .\output\dark-fantasy-ui\extracted\icon-item-sheet-01-alpha.png `
  --layout-json .\output\dark-fantasy-ui\references\layout-guides\icon-item-sheet-01.json `
  --request .\output\dark-fantasy-ui\request.json `
  --output-dir .\output\dark-fantasy-ui\extracted\assets `
  --manifest-out .\output\dark-fantasy-ui\extracted\manifest.json `
  --qa-out .\output\dark-fantasy-ui\qa\extract.json
```

## 5. 归一化

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\normalize_assets.py `
  --manifest .\output\dark-fantasy-ui\extracted\manifest.json `
  --request .\output\dark-fantasy-ui\request.json `
  --input-dir .\output\dark-fantasy-ui\extracted\assets `
  --output-dir .\output\dark-fantasy-ui\final\Icon_Item `
  --manifest-out .\output\dark-fantasy-ui\final\manifest.json
```

## 6. Contact Sheet 与 QA

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
