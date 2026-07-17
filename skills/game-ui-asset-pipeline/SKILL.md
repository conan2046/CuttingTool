---
name: game-ui-asset-pipeline
description: 生成、拆分、透明化、校验并打包游戏 UI 位图资源，并可导入 Unity 2022.3、配置 Sprite、推断九宫格 Border、生成 Image/Button 资源 Prefab 和最终界面 Prefab。当用户要求制作游戏UI、UI资源包、可切割Sheet、透明PNG、Unity UI导入、Sprite Editor、九宫格或可交互Prefab时使用；不用于角色动画、地图切片、普通照片抠图或从遮挡截图恢复不可见资源。
---

# Game UI Asset Pipeline

## 目标

把游戏 UI 位图资源生产拆成两个稳定层：

1. 使用 `$imagegen` 生成风格基准图和相互分离的分类资源 Sheet。
2. 使用本 Skill 的确定性脚本完成去背景、检测、切割、归一化、命名、Manifest 和 QA。

不要让图片模型承担精确像素裁切、文件命名或最终验收。

## 当前范围

处理以下静态游戏 UI 类别：

- Panel
- Button
- Icon_Nav
- Icon_Status
- Icon_General
- Icon_Item
- Icon_Equip
- Icon_Skill
- Icon_Effect 中可通过色键稳定提取的简单硬边特效
- 使用 GPT Image 2 彩色 Sheet＋灰度 Alpha Matte 推导的烟雾、玻璃、液体和柔光特效
- 具有可验证生成来源的原生 RGBA 烟雾、玻璃、液体和柔光特效
- Unity 2022.3 Sprite Single 自动导入、可验证九宫格 Border 和 Image/Button Prefab

以上九项是运行配置和验收 JSON 使用的内部类别名，必须原样返回。`01_Panel` 到 `09_Icon_Effect` 只用于文件名前缀；不要把 `09_Icon_Effect` 当成内部 `category`。

不要把以下任务强行纳入当前流程：

- 角色或宠物动画 Sprite Sheet
- 地图、Tilemap 或场景切片
- 普通照片和商品图抠图
- 视频或动态 UI
- 从元素互相遮挡的界面截图恢复底层素材
- 动态文本、本地化绑定、业务脚本和运行时数据源自动接线
- 从截图猜测无法验证的交互逻辑

## 必须读取的参考文件

根据任务阶段读取：

- 确定分类、数量和默认规格时，读取 `references/asset-categories.md`。
- 构建 GPT Image 提示词时，读取 `references/generation-contract.md`。
- 生成布局引导图或确定槽位时，读取 `references/sheet-layout-contract.md`。
- 导出文件和 Manifest 时，读取 `references/naming-contract.md`。
- 同一任务包含多个分类或需要自动拆分多张 Sheet 时，读取 `references/batch-request-contract.md`。
- 输入是未知整图、假棋盘格或需要人工修正 bbox 时，读取 `references/unknown-sheet-contract.md`。
- 色键背景存在色差、阈值需要自适应或组件出现碎片时，读取 `references/chroma-fragment-contract.md`。
- 请求原生透明、烟雾、玻璃、液体或柔光时，读取 `references/native-alpha-contract.md`。
- 用户要求一键生成、多分类完整交付、继续上次任务或查看缺少哪些生成图时，读取 `references/orchestration-contract.md`。
- 首次项目初始化、用户说参考图已放好或需要检查参考图时，读取 `references/reference-intake-contract.md`。
- 需要确认界面布局/尺寸、自动写参考说明、建立资源清单、跨界面复用或从中间阶段开始时，读取 `references/project-intake-and-reuse-contract.md`。
- 遇到明确的 WebSocket `stream disconnected before completion` 错误时，读取 `references/task-recovery-contract.md`。
- 用户要求 Unity 导入、Sprite Editor、九宫格、资源 Prefab 或最终界面 Prefab 时，读取 `references/unity-export-contract.md`。

不要一次加载无关参考文件。

## 图片生成层

所有正常视觉生成使用 `$imagegen`。在生成前读取并遵循：

```text
${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/SKILL.md
```

默认使用内置图片生成路径。复杂烟雾、玻璃、液体或柔光优先使用 `model-matte-derived`：先生成纯黑底彩色 Sheet，再把该图作为编辑目标生成像素对齐且画布尺寸完全一致的灰度 Alpha Matte；尺寸不一致必须失败，不得自动缩放后继续交付。不要把 Matte 推导结果称为模型原生 Alpha。只有用户明确要求源文件原生 Alpha 时，才按 `$imagegen` 的 CLI 回退规则确认授权。

## 输入判断

### 首次项目初始化

在收集参考图或资源清单前先确定项目名，因为项目名决定本地输入目录和后续 `project_id`：

1. 如果用户已经明确提供项目名，直接使用，不要重复询问。
2. 如果当前任务没有项目名，且不是继续一个已知运行目录，只问一句并暂停：`请输入项目名（建议使用英文、数字和短横线，例如 xianxia-bag-ui）。`
3. 获得项目名后立即运行：

   ```powershell
   & $PYTHON scripts/initialize_ui_project.py `
     --workspace-root D:\CuttingTool `
     --project-name <项目名>
   ```

4. 确认已创建 `input/<project-id>/references/reference-notes.md`，把参考图目录的绝对路径返回给用户，明确要求用户把图片放好后回复“已放好”，然后暂停本轮。用户无需填写 Markdown。
5. 用户回复“已放好”后运行：

   ```powershell
   & $PYTHON scripts/validate_ui_references.py `
     --references-dir D:\CuttingTool\input\<project-id>\references `
     --json-out D:\CuttingTool\input\<project-id>\reference-validation.json
   ```

6. 自动检查通过后，使用 `view_image` 逐张检查并自动判断清晰度、完整性、污染、主参考代表性、辅助图职责和风格冲突；不合格时要求替换并暂停。
7. 全部通过后，把每个界面的布局参考、UI 元素是否与主参考一致（不一致时写清差异）和目标像素尺寸合并为一次确认。用户确认后自动运行 `compile_ui_project_intake.py`，更新 `reference-notes.md`、生成 `ui-resource-inventory.md` 与批量请求，然后连续执行到正式资源交付。

初始化脚本必须幂等复用已有目录。自动分析只替换 Markdown 的自动维护区，保留区外人工文字。

把最终目标设为“产出用户需求的美术资源”。除项目名、用户尚未放置参考图、一次性界面确认、参考图不合格替换和重大歧义外，不停在说明文件、资源清单、`awaiting-generation` 或缺图摘要。

### 项目复用与阶段入口

项目首个界面全部产出；后续界面按 `category + semantic_name + state` 复用，忽略尺寸，并在清单记录引用资源。使用项目级 `ui-asset-catalog.json` 保存已交付资源。

如果用户已有请求 JSON、Sheet、透明资源、Manifest 或运行目录，从 `generation`、`processing`、`unknown-sheet`、`qa-only` 或 `resume` 等最靠后的安全阶段开始；不要强迫重新走首次初始化。具体路由读取 `project-intake-and-reuse-contract.md`。

如果用户正在处理一张已提供的未知整图，或明确给出已有运行目录并要求续跑，不需要强制新建项目输入目录。

先把请求归为以下一种或多种模式：

### A. 风格基准图

用户需要先确定整体 UI 视觉语言。输出只用于风格确认，不用于正式切割。

### B. 分类资源 Sheet

用户已有风格方向，需要生成可自动拆分的面板、按钮或图标 Sheet。

### C. 已有 Sheet 拆分

用户提供一张资源整图，需要识别、透明化并导出独立 PNG。

### D. 混合展示图诊断

输入同时包含界面预览、标题、分隔线、假棋盘格或相互遮挡元素。先诊断可提取范围；不要承诺无损恢复所有资源。

未知整图先运行：

```bash
"$PYTHON" scripts/diagnose_ui_sheet.py \
  --input input/ui-sheet.png \
  --category Icon_Item \
  --json-out output/run/qa/input-diagnosis.json \
  --corrections-out output/run/qa/bbox-corrections.json \
  --preview-out output/run/qa/bbox-preview.png
```

标注预览必须显示候选编号、问题类型和严重级别。修正 JSON 的候选项包含原始检测框、字段级错误位置和阈值建议；查看预览并编辑语义、bbox、启用状态和编号。只有背景可安全透明化、bbox 完整且语义命名确认后，才设置 `approved=true`，然后运行：

```bash
"$PYTHON" scripts/apply_bbox_corrections.py \
  --input input/ui-sheet.png \
  --corrections output/run/qa/bbox-corrections.json \
  --run-dir output/run \
  --project-id unknown-ui-pack
```

假棋盘格是烘焙进 RGB 的展示背景，不是真实 Alpha。允许输出诊断和候选框，但禁止把它直接转换成正式透明资源；要求重新生成纯色色键图或提供真实 Alpha。

应用修正前必须完成结构化预检。越界、重叠、可见前景裁断和分类编号不连续时，写出 `qa/correction-validation.json` 与 `qa/bbox-diff-preview.png`，但不得写正式 Manifest。裁断检查默认只统计 `alpha >= 16` 的可见像素，避免亚可见色键清理残留误报；修正成功时同样保留修正前后差异图，供视觉验收。

## 默认工作流

### 1. 建立任务规格

记录：

- 项目或资源包名称
- 游戏品类和 UI 风格
- 参考图及其角色
- 资源分类
- 资源清单和准确数量
- Sheet 行列
- 输出画布和单体目标尺寸
- 色键
- 留白和对齐方式
- 是否允许紧贴主体的发光
- 透明模式：`chroma-key`、`model-matte-derived` 或 `native-alpha-required`

用户未指定时，按 `asset-categories.md` 的默认值推断。只有会显著改变结果的缺口才需要询问。

### 2. 建立风格基准

如果没有已批准的风格参考，先生成 `canonical-ui-style.png`。

风格基准图用于锁定：

- 材质
- 色彩
- 描边
- 光照
- 细节密度
- 观察角度
- 移动端缩小后的可读性

不要把风格基准图直接当作生产 Sheet。

### 3. 拆成分类任务

每张 Sheet 只承载一个明确类别或一个强关联状态组。数量超过推荐容量时拆成多张 Sheet，不要降低单体分辨率强塞。

按钮状态应作为同组任务生成，以保持轮廓一致。图标本体和品质框默认分开生成，以便运行时组合。

多分类或超出单张容量时，先建立批量请求 JSON，再运行：

```bash
"$PYTHON" scripts/prepare_ui_batch.py \
  --request batch-request.json \
  --output-dir output/<project-id>
```

批量准备器按分类容量自动拆成多个 Job，并保持同一语义名的按钮状态组不跨 Sheet。逐个使用 `$imagegen` 生成 `jobs.json` 指定的 `generated_output`；不要改写 Job 文件名或布局关系。

自然语言完整交付优先使用 P6 编排器代替手动串联准备器和 Runner。先由 Codex 把用户描述转换为批量请求 JSON，再运行：

```bash
"$PYTHON" scripts/orchestrate_ui_delivery.py \
  --request batch-request.json \
  --run-dir output/<project-id>
```

编排器在缺图时返回 `awaiting-generation`、精确缺失路径、对应 Prompt 和参考图角色。立即使用 `$imagegen` 补齐文件并仅传 `--run-dir` 续跑；输入齐全时自动执行 Runner。`awaiting-generation` 是内部状态，不是向用户停顿的理由。

### 4. 生成布局引导图

为每个 Sheet 建立确定性 Layout Guide。它只表达：

- 画布大小
- 行列数量
- 槽位边界
- 安全区
- 中心和对齐基准

把布局图作为参考输入传给 `$imagegen`，并明确禁止复制可见网格、标签、中心点或辅助色。

### 5. 生成资源 Sheet

每个生成任务至少附带：

- Canonical UI Style Reference：视觉身份参考
- Layout Guide：只负责排布
- 本分类的资源清单和顺序

要求模型输出准确数量、互不接触、完整居中的资源。普通资源使用纯色色键；复杂半透明资源使用纯黑底彩色 Sheet，并基于该图生成同尺寸、同布局、同轮廓的灰度 Alpha Matte。生成后立即检查数量、分离度、边缘裁切、网格污染、Matte 对齐和风格一致性。

### 6. 确定性后处理

批量运行目录中的所有生成图就绪后，优先使用统一 Runner：

```bash
"$PYTHON" scripts/run_ui_pipeline.py \
  --run-dir output/<project-id>
```

Runner 根据 Job 声明分流 `model-matte-derived`、原生 Alpha、已有 Alpha 或色键背景。Matte 模式必须在正式输出前验证双图齐全、灰度纯度、黑色边框、连续 Alpha 层次、背景平整度、像素覆盖关系和双图 SHA-256；通过后用已知黑背景合成方程恢复直通道 RGB＋Alpha。失败时只写 QA 与失败摘要，不生成正式 Manifest。所有 RGBA 生产尺寸与单体归一化均使用预乘 Alpha。默认拒绝覆盖已有正式 Manifest；明确重跑时使用 `--force`。

P6 编排器每次调用都写出 `qa/delivery-summary.json` 和 `qa/delivery-summary.md`。完成态重复调用必须直接复用正式结果；失败后替换生成输入可继续执行，只有已有正式 Manifest 时才允许显式 `--force-run`。

内置 `imagegen` 当前不能直接用于 `native-alpha-required`，但可以用于 `model-matte-derived`，不需要 API Key。原生模式仍需用户明确确认外部透明生成回退，并保存 `generated/<job-id>.provenance.json`；来源侧车中的模型与生成方式都必须为非空值。

以下分步命令保留用于单 Sheet 调试和人工校正：

按输入条件选择：

1. 已有 Alpha：Alpha 连通域。
2. 纯色色键：色差阈值和背景移除。
3. 已知网格：槽位内检测。
4. 自动识别失败：生成待校正包围框并报告，不擅自丢弃元素。

后处理顺序固定为：

```text
背景识别
→ Alpha Matte 校验与双图合成（如适用）
→ 色键转 Alpha
→ 组件检测与合并
→ 包围框裁切
→ 最终一次边缘净化
→ 透明空白裁切
→ 留白、缩放和对齐
→ 导出
```

不要多次反复羽化或净边，避免轮廓缩水。

局部前景颜色投影默认处理色键软遮罩过渡带；对空间上仍处于背景邻域、且符合“色键—局部前景”线性混合模型或存在明显色键通道优势的像素，可以跨越固定欧氏距离阈值继续重建。远离背景的确定前景必须保留原始 RGB/Alpha。无法获得可靠前景估计、且仍接近色键或具有色键通道偏色的部分 Alpha 像素应透明化，并在背景报告记录 `discarded_unresolved_chroma_edge_pixels`；此前必须通过近色主体风险检查。

硬边部分透明光带只有在稳定不透明核心不少于含糊过渡像素时允许自动处理；否则继续判 `near-key-subject-risk`。大画布允许把局部前景搜索半径扩大到 `32px`，但投影仍只作用于背景邻域。最终 QA 必须检查整个可见主体的强色键通道优势；模型把色键反射画进主体内部时应拒绝源图并重生成，禁止全图强制去色。

当前色键处理脚本：

```bash
"$PYTHON" scripts/remove_chroma_key.py \
  --input generated/<sheet>.png \
  --output extracted/<sheet>-alpha.png \
  --chroma-key "#00FF00" \
  --adaptive-thresholds \
  --json-out qa/<sheet>-chroma.json
```

统一 Runner 默认启用自适应诊断。它根据边框色差分布给出透明/不透明阈值、置信度和近色主体风险；只有 `auto_apply=true` 才采用建议值。低置信度、近色主体风险或不安全阈值必须失败并转人工检查。只在复现旧行为或人工已经确认固定阈值时使用 `run_ui_pipeline.py --fixed-chroma-thresholds`。

运行图片脚本前先调用工作区依赖定位工具，并使用返回的精确 Python 路径。不要假设裸 `python` 指向正确环境。

色键转换通过后，按布局引导 JSON 切割：

```bash
"$PYTHON" scripts/extract_sheet_assets.py \
  --input extracted/<sheet>-alpha.png \
  --layout-json references/layout-guides/<sheet>.json \
  --request request.json \
  --output-dir extracted/assets \
  --manifest-out extracted/manifest.json \
  --qa-out qa/<sheet>-extract.json
```

切割脚本先在整张 Alpha Sheet 上检测连通域，再按最近槽位中心稳定归属。Layout Guide 的槽位用于排序和归属，不作为硬裁切边界；这样可保留伸入槽间纯背景留白、但没有与相邻资源接触的完整轮廓。距离主体足够近的小碎片按分类默认比例和像素上限合并；大面板/按钮使用更严格上限，技能和简单特效允许更大的合法硬边碎片间距。远离碎片默认记录 `detached-components`，远离且面积显著的第二主体追加 `multiple-major-components`。只有请求明确设置 `fragment_policy.detached_action=allow-small` 且同时满足绝对像素与锚点面积比例限制时，才允许保留该小组件但不产生 warning；仍须记录 `accepted_detached_count`。空槽、主体跨槽合并、画布边缘接触和数量不符属于失败；不要静默删除无法解释的组件。

组件检测默认使用 `alpha >= 16`，与最低可见 Alpha QA 一致。单一连通组件同时跨过两个或更多槽位中心时必须报告 `cross-slot-connected-component` 并失败；不得仅依赖后续空槽间接推断。

如果色键转换后所有槽位同时出现边缘接触或大量多组件警告，先检查背景色差分布。图片模型可能把指定色键生成成近似纯色而非逐像素完全一致；在确认主体不使用该色键后，提高 `--transparent-threshold` 并同步提高 `--opaque-threshold`，直到背景连通噪声消失，再重新切割。不要用放宽槽位裁切或忽略失败来绕过色键残留。

按请求中的目标尺寸、留白和对齐规则归一化：

```bash
"$PYTHON" scripts/normalize_assets.py \
  --manifest extracted/manifest.json \
  --request request.json \
  --input-dir extracted/assets \
  --output-dir final/<Category> \
  --manifest-out final/manifest.json
```

RGBA 资源缩放必须使用预乘 Alpha 插值，再转换回直通道 RGBA。禁止直接缩放直通道 RGBA，否则低 Alpha 色键 RGB 可能被插值成可见绿边或品红边。

默认不放大小尺寸原图，避免无意义插值；超出目标安全区时只缩放一次。图标使用中心对齐，需要底边稳定的资源使用 `bottom-center`。

生成正式 QA 总览并验证资源包：

```bash
"$PYTHON" scripts/make_contact_sheet.py \
  --manifest final/manifest.json \
  --asset-root final/<Category> \
  --output qa/contact-sheet.png

"$PYTHON" scripts/validate_asset_pack.py \
  --manifest final/manifest.json \
  --asset-root final/<Category> \
  --request request.json \
  --json-out qa/qa-report.json \
  --strict-files
```

Contact Sheet 中的棋盘格只用于人工查看透明边缘，不得回写到正式资源。验证器必须检查数量、文件名、RGBA、空图、隐藏 RGB、尺寸、色键残留、连续色键通道偏色和 Manifest 对应关系。色键残留只统计达到最低可见 Alpha 阈值的像素；缩放插值产生的 `alpha < 16` 亚可见边缘像素不应误判为残色，但达到阈值的近色键像素仍必须失败。对于不接近纯色键、但在任意可见主体区域形成连续绿/品红/青色偏的像素，使用 `visible-chroma-spill` 单独判定，不能只依赖 RGB 欧氏距离或仅检查透明边缘。

### 7. 命名和清单

按照 `naming-contract.md` 生成稳定文件名和 `manifest.json`。排序使用从上到下、从左到右，不能依赖文件系统顺序。

### 8. QA

至少验证：

- 请求数量与导出数量一致
- 每个资源非空
- 没有跨槽位合并
- 没有明显裁边
- 输出为 RGBA PNG
- 背景区域透明
- 色键残留低于阈值
- 内部没有意外透明条带或孔洞
- 命名唯一且编号连续
- Manifest 与实际文件一致
- Contact Sheet 可读且风格一致

任何 `fail` 未处理时，不得报告资源包完成。

### 9. Unity 导出与可交互 Prefab

只有正式 Manifest 和 QA 均通过后才进入 Unity。先从已确认的界面布局生成 `unity-layout.json`；不要让确定性脚本从截图猜坐标或交互语义。

读取 `unity-export-contract.md`，验证目标 Unity 项目、2022.3 版本、导入根目录和回滚范围，然后运行：

```powershell
& $PYTHON scripts/export_unity_ui.py `
  --run-dir output/<project-id> `
  --unity-project D:\CodeProjects\UIText `
  --unity-editor E:\UnityPro\2022.3.62f3c1\Editor\Unity.exe `
  --layout output/<project-id>/unity/unity-layout.json
```

脚本把可追溯 PNG 导入 `Assets/_Generated/GameUI/<project-id>`，配置 Sprite Single、Alpha、PPU、Pivot 和 Border，生成独立资源 Prefab、界面 Prefab、可直接运行的 Preview Scene，并由 Unity 渲染像素尺寸一致的预览 PNG。Panel/Button 自动分析九宫格，并按源图到全部布局目标的最小缩放比推导 PPU；只有 Border 置信度、中心拉伸区及换算后的显示尺寸全部有效时才写入，否则预检失败并要求在布局 JSON 的 `nine_slice_overrides` 或 `pixels_per_unit_overrides` 中明确覆写。

界面元素当前正式支持 `Image` 和 `Button`。每个对象附带稳定 `GameUIElementBinding.BindingId`；Button 自动配置 `Image`、`Button.targetGraphic`、Raycast，并在布局提供状态资源时使用真实 Hover/Pressed/Disabled SpriteSwap。无 Sprite 的 Image 可通过 RGBA `color` 作为确定性底色。文字、本地化、业务事件和运行时数据绑定属于项目代码，不得伪造完成。

Unity 导出失败时读取 `unity/unity-preflight.json`、`unity/unity-import-report.json` 和 `unity/unity-batch.log`。需要回滚本次生成目录时运行 `rollback_unity_export.py`；默认保留共享嵌入包，只有明确需要完全移除时才加 `--remove-package`。

## 色键策略

默认：

- 主体不含绿色：`#00FF00`
- 主体含绿色：`#FF00FF`
- 主体同时包含绿色和品红：选择冲突更小的色键或拆分任务

不要要求 GPT Image 2 生成假棋盘格透明背景。不要把 RGB PNG 描述为已有真实 Alpha。

## 输出结构

每次运行使用独立目录：

```text
output/<project-id>-<timestamp>/
├─ request.json
├─ jobs.json
├─ references/
├─ requests/
├─ prompts/
├─ generated/
├─ extracted/
├─ normalized/
├─ final/
│  ├─ Panel/
│  ├─ Button/
│  ├─ Icon_Nav/
│  ├─ Icon_Status/
│  ├─ Icon_General/
│  ├─ Icon_Item/
│  ├─ Icon_Equip/
│  ├─ Icon_Skill/
│  └─ Icon_Effect/
└─ qa/
   ├─ contact-sheet.png
   ├─ qa-report.json
   ├─ run-summary.json
   ├─ delivery-summary.json
   └─ delivery-summary.md
```

## 交付要求

最终回复必须包含：

- 最终资源目录
- Manifest 路径
- Contact Sheet 路径
- QA 报告路径
- 使用的图片生成方式
- 通过、警告、失败数量
- 尚需人工处理的资源编号
- 如执行 Unity 阶段：Unity 预检、导入报告、Prefab、Preview Scene、Unity 渲染预览和回滚清单

## 项目规范同步

在 `D:\CuttingTool` 开发或修复本 Skill 时，遵守项目根目录 `AGENTS.md`。新增功能、优化流程或修复通用 Bug 后，同一任务内同步更新相关制作标准；如果无需修改，也要在交付说明中明确已检查。
