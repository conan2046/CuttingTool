# CuttingTool 会话交接

> 更新时间：2026-07-21
> 工作目录：`D:\CuttingTool`  
> 仓库：`https://github.com/conan2046/CuttingTool.git`  
> 当前工作分支：`codex/v0.13-quality-nine-slice`
> 已完成功能基线：v0.13.0 QA 驱动纠错、候选评分与失败 Job 定向重生成；并包含 v0.12.6 九宫格 Panel 拉伸带与控件安全区、Scroll View、Layout Group、低 Alpha 外溢、九宫格 PPU、真实 HUD、Button 四态与 Unity Preview Scene

## 1. 新会话先做什么

按以下顺序开始，不要直接写代码：

1. 完整读取 `D:\CuttingTool\AGENTS.md`。
2. 完整读取 `D:\CuttingTool\skills\game-ui-asset-pipeline\SKILL.md`。
3. 读取本文件、`README.md` 和 `CHANGELOG.md` 最新一条。
4. 使用完整 Git 路径检查状态：

   ```powershell
   & 'C:\Program Files\Git\cmd\git.exe' status --short --branch
   & 'C:\Program Files\Git\cmd\git.exe' log -5 --oneline
   ```

5. 确认没有用户未提交修改后，再按“下一步计划”继续。

## 2. 我们在做什么

正在开发并维护 Codex Skill：

```text
game-ui-asset-pipeline
```

目标是建立不依赖图片 API Key、以 Codex 内置图片生成能力为视觉来源的游戏 UI 位图生产流水线：

```text
文字需求/参考图
→ Canonical UI Style Reference
→ 分类 Production Asset Sheet + Layout Guide
→ 本地色键/Alpha处理
→ 自动检测、切割、归一化、命名
→ Manifest、Contact Sheet、QA
→ Unity Sprite/Border 配置、资源 Prefab、界面 Prefab
```

核心原则：AI 负责视觉，Python 脚本负责确定性处理和验收。桌面 GUI 已明确降为长期最低优先级，不是当前开发目标。

## 3. 已经完成什么

### 3.0 v0.13.0：QA 驱动纠错与候选评分

- 新增 Run、Job、Asset 三级质量分；分数只排序候选，`fail` 永远硬阻断。
- Runner 失败后生成 `qa/regeneration-plan.json/md` 和单原因纠错 Prompt，Codex 只替换计划指定输入。
- 候选按必需输入 SHA-256 组合指纹去重；未替换不计新候选，替换后自动重跑。
- 默认最多 3 个候选，可配置 1–5；耗尽后保持 `failed`，不交付最佳失败候选。
- 源码与安装态全量测试各 120/120 通过；68 个正式 Skill 文件哈希一致，0 差异。
- 已用装备强化参考图完成真实 GPT Image 多候选闭环：Button 暖红漂移被自动阻断并修正；装备 Sheet 修复触边和人工语义偏差。
- 新增 `qa/style-consistency.json`：Canonical + 跨 Sheet 综合评分，漂移绑定具体 Job 并进入定向重生成。
- 真实批次：`output/xiuxian-ui-v013-enhancement`，10 pass、2 warning、0 fail，质量 82，风格 67.10；两条 warning 为 Panel 色键边框波动与装备 Sheet 轻微风格漂移，Contact Sheet 人工复核通过。
- 后续用户指出 Panel 与 Button 四边中段存在九宫格违规花纹；最终候选已把装饰限制在四角固定区，Panel 两件和 Button 四态均通过原尺寸、0.5×、1.5×、2× Sliced 视觉复核。
- QA 现对 Panel/Button 同时检查四边中间 60% 的外轮廓与内部纹理，正式总报告包含 6 条 `nine_slice_stretch_bands`；分别以 `panel-stretch-band-decoration`、`button-stretch-band-decoration` 硬阻断。
- 根因之一是实际 `build_prompt()` 未注入文档已有的 Panel 九宫格约束；另一处断点遗漏是 Runner 未转发 Button 拉伸报告。两处均已修复并有回归测试。

### 3.0 v0.12.6：九宫格 Panel 拉伸带与控件安全区

- `UniversalPanelBase`、`InventorySlotFrame` 已清除四边中段独特装饰，保留四角和左上龙角；生产 Sheet 尺寸、资源位置、数量和绿色键背景不变。
- 两张 Panel 已重新完成切割、透明化、Manifest、QA 和 Unity Border 推导；30 pass、0 warning、0 fail。
- 背包底部按钮组上移 50px 并成为 InventoryPanel 子节点，底部安全距离从 9px 增加到 59px。
- Unity 重导 0 issue；实际 Sliced 渲染四角稳定、边中段连续，按钮不再压住外框。
- 固化规则：九宫格独特装饰只放四角，四边中段与中心区保持干净，控件必须位于 Panel 安全区。

### 3.0 v0.12.5：Unity Scroll View 有限区域与溢出裁剪

- 背包从单独 GridLayoutGroup 改为 `ScrollView → ScrollViewport(RectMask2D) → InventorySlotsGrid(GridLayoutGroup + ContentSizeFitter)`。
- Viewport 固定 772×632，Content 当前 772×772；静态预览显示 4 行，第 5 行被正确裁剪，内容可垂直滚动。
- Prefab 的 ScrollRect Content/Viewport 引用有效，垂直开启、横向关闭、MovementType=Clamped；Scroll View 默认透明且无可见滚动条。
- 真实 Unity 重导：30 Sprite、30 资源 Prefab、1 Screen Prefab、1 Preview Scene、1 Preview PNG、0 issue；最终回归数量以 CHANGELOG 最新记录为准。
- 源码与安装态全量 `unittest` 各 106/106 通过；63 个正式 Skill 文件 SHA-256 一致，0 差异。

### 3.0 v0.12.4：Unity Layout Group 规则布局

- Unity 布局支持 `GridLayoutGroup`、`HorizontalLayoutGroup`、`VerticalLayoutGroup`，容器与子项均保留稳定 BindingId。
- 角色界面装备位、页签、25 格背包和底部按钮已从逐项坐标改为 4 个 Layout Group 容器。
- 真实 Unity 重导：30 Sprite、30 资源 Prefab、1 Screen Prefab、1 Preview Scene、1 Preview PNG、0 issue。
- Screen Prefab 实际包含 2 个 GridLayoutGroup、2 个 HorizontalLayoutGroup；子节点数量 6、4、25、2，1980×1080 渲染视觉检查通过。
- 源码与安装态全量 `unittest` 各 104/104 通过；63 个正式 Skill 文件 SHA-256 一致，0 差异。

### 3.0 v0.12.3：低 Alpha 外溢与画布拉伸修复

- `allow_attached_glow=false` 时清理与稳定主体分离的低 Alpha 外溢，保留紧贴轮廓的抗锯齿，并记录移除数量。
- Runner 拒绝生成图与请求画布宽高比不一致的输入，禁止非等比拉伸。
- `xiuxian-ui-character-1980x1080-v3` 已重跑：30 个资源，30 pass、0 warning、0 fail；20 个 Button 均完成外溢清理。
- 跨槽碎片会按资源主组件边界距离二次纠正；`InventorySlotFrame` 左侧误入的大面板边饰已清除。
- 角色源图与 Matte 已等偏移补齐为 2048×2048，主体不缩放；Unity 等比显示后人物比例正常。
- Unity 重新导入：30 Sprite、30 资源 Prefab、1 Screen Prefab、1 Preview Scene、1 Preview PNG、0 issue。

### 3.1 v0.12.2：九宫格 PPU 联动修复

- Panel/Button 根据源图与全部布局目标的最小缩放比自动推导 PPU，避免固定 Border 在矮控件中被比例压缩。
- 预检验证 Border 换算后的 Unity 显示尺寸；左右或上下固定区超过任一目标控件时阻断。
- 支持 `pixels_per_unit_overrides` 人工覆写，并记录 `layout-derived`、`manual-override` 或 `default` 来源。
- `QuestRowFrame` 已在真实 Unity 中写入 Border `[180,95,180,95]`、PPU `447.8261`；重新渲染后无压扁变形。
- 源码与安装态全量测试各 99/99；63 个正式 Skill 文件哈希一致。

### 3.1 v0.12.1：真实 HUD 与视觉验收

- `xiuxian-ui-1980x1080-v1` 已导入 86 Sprite 并生成 86 资源 Prefab。
- `XiuxianMainHUD` 含 47 个 BindingId、9 个 SpriteSwap Button。
- 自动生成 `XiuxianMainHUD-Preview.unity` 和 1980×1080 Unity 渲染 PNG。
- Unity report：1 Screen Prefab / 1 Preview Scene / 1 Preview PNG / 0 issue。
- 源码与安装态全量测试各 97/97；63 个正式 Skill 文件哈希一致。

### 3.1 v0.12.0：Unity 交付链路

- 目标样板项目：`D:\CodeProjects\UIText`，Unity `2022.3.62f3c1`，UGUI。
- `export_unity_ui.py` 统一完成预检、嵌入包安装、资源复制和 Unity batchmode。
- 自动配置 Sprite Single、Alpha、PPU、Pivot、Border；Panel/Button 低置信九宫格必须人工覆写。
- 从 schema v1 显式布局生成 Image/Button 资源 Prefab 和界面 Prefab，元素附稳定 BindingId。
- 所有生成内容限定在 `Assets/_Generated/GameUI/<project-id>`，并输出回滚清单。

### 3.1 v0.11.0：自动接收与跨界面复用

- 参考图通过后由 Codex 自动维护 `reference-notes.md`，不再要求用户填写模板。
- 布局、UI 元素与主参考一致性、差异说明和界面像素尺寸合并为一次确认。
- `compile_ui_project_intake.py` 自动生成资源清单和批量请求；确认后连续执行到最终资源交付。
- 首个界面全产出；后续界面按类别、语义名和状态复用，忽略尺寸并记录来源。
- 完成态自动更新项目 `ui-asset-catalog.json`。
- 支持从 intake、generation、processing、unknown-sheet、qa-only、resume 独立进入。
- 断线恢复协议已落文档；全自动新建任务仍依赖 Codex 桌面断线回调。
- 源码与安装态全量 `unittest` 各 86/86 通过；51 个正式文件 SHA-256 一致。

### 3.2 V1 确定性核心链路

- 建立 Skill 标准目录、`SKILL.md`、参考契约、脚本、测试和安装副本。
- 支持九类静态资源：`Panel`、`Button`、`Icon_Nav`、`Icon_Status`、`Icon_General`、`Icon_Item`、`Icon_Equip`、`Icon_Skill`、`Icon_Effect`。
- 支持 Layout Guide、纯色色键转真实 Alpha、连通域检测、切割、归一化、稳定命名和 Manifest。
- 支持 Contact Sheet 和严格 QA。
- 当前依赖只有 Pillow 和 NumPy，不依赖 OpenCV。

### 3.3 批量分类与统一 Runner

- `prepare_ui_batch.py` 支持多分类请求和超容量自动拆 Sheet。
- 同一语义按钮状态组不会跨 Sheet。
- `run_ui_pipeline.py` 统一处理模型 Matte、原生 Alpha 和色键 Sheet。
- 自动汇总总 Manifest、Contact Sheet、QA 和 `run-summary.json`。
- 分类编号跨 Sheet 连续。

### 3.4 未知 UI 整图诊断

- `diagnose_ui_sheet.py` 能识别真实 Alpha、可靠纯色背景、RGB 假棋盘格和无法解析的混合背景。
- 输出 `input-diagnosis.json`、`bbox-corrections.json` 和 `bbox-preview.png`。
- `apply_bbox_corrections.py` 使用人工批准的 bbox 生成正式透明资源包。
- 未批准修正、假棋盘格、未解析背景、bbox 重叠/越界/裁断时禁止交付。

### 3.4 v0.3.0：本会话完成

- 新增自适应色键阈值诊断：边框色差分位数、建议透明/不透明阈值、置信度、近色主体风险、`auto_apply`。
- Runner 默认只在安全时采用建议阈值；低置信度、近色主体风险和过宽阈值会阻止自动处理。
- 新增 `--fixed-chroma-thresholds`，仅用于人工确认或复现旧固定阈值。
- 净边算法改为使用邻近稳定前景色反推抗锯齿 Alpha 与边缘 RGB。
- 新增近邻碎片智能合并，并区分：
  - `merged_component_count`
  - `detached_component_count`
  - `major_detached_count`
- 远离碎片报告 `detached-components`；显著第二主体追加 `multiple-major-components`；不静默删除。
- 建立金色/白色/深色抗锯齿通过矩阵，以及偏移色键、近色主体、污染边框失败矩阵。
- 九个标准类别均有静态 eval 和独立 Codex 新任务触发验收。
- 严格触发结果：9/9 通过。
- 项目版本已升至 `0.3.0`。

### 3.5 验证状态

当前已验证：

| 项目 | 结果 |
|---|---:|
| 源码 `unittest` | 72/72 通过 |
| 安装态 `unittest` | 72/72 通过 |
| P6 混合编排端到端 | 4 pass / 0 warning / 0 fail |
| P6 静态编排触发评测 | 1/1 通过 |
| 九类独立 Codex 新任务触发 | 9/9 通过 |
| Skill 源码/安装副本 | 42 个正式文件哈希一致，0 差异 |

关键证据：

- `D:\CuttingTool\skills\game-ui-asset-pipeline\evals\trigger-acceptance-2026-07-16.json`
- `D:\CuttingTool\output\adaptive-chroma-v03\qa\contact-sheet.png`
- `D:\CuttingTool\output\adaptive-chroma-v03\qa\qa-report.json`
- `D:\CuttingTool\output\dark-metal-regression-a\qa\contact-sheet.png`
- `D:\CuttingTool\output\dark-metal-regression-a\qa\qa-report.json`
- `D:\CuttingTool\output\bright-cartoon-regression-b\qa\contact-sheet.png`
- `D:\CuttingTool\output\bright-cartoon-regression-b\qa\qa-report.json`
- `D:\CuttingTool\output\lowlight-dark-regression-c\qa\contact-sheet.png`
- `D:\CuttingTool\output\lowlight-dark-regression-c\qa\qa-report.json`
- `D:\CuttingTool\CHANGELOG.md`
- `D:\CuttingTool\output\p6-orchestration-e2e\qa\delivery-summary.json`
- `D:\CuttingTool\output\p6-orchestration-e2e\qa\delivery-summary.md`
- `D:\CuttingTool\output\p6-orchestration-e2e\qa\contact-sheet.png`

### 3.6 v0.4.0：三风格真实生产回归

- 使用内置 `imagegen` 完成 12 件 `Icon_Equip`、4×3、绿色色键真实生产 Sheet。
- 完成 12 件明亮卡通 `Icon_Item`、4×3、品红色键真实生产 Sheet。
- 完成 12 件低明度深色 `Icon_Skill`、4×3、青色第三色键真实生产 Sheet。
- 首轮 Runner 暴露确定前景被局部投影漂白，以及低 Alpha 色键像素在归一化缩放后重新显色。
- 局部前景投影覆盖软遮罩过渡带，以及背景邻域中符合线性混合模型或具有色键通道优势的互补色边缘；远离背景的确定前景保持原始 RGB/Alpha。
- 无法安全重建的部分 Alpha 近色残边会透明化，并记录 `discarded_unresolved_chroma_edge_pixels`。
- 归一化改为预乘 Alpha 缩放，阻止色键 RGB 在缩小时复活。
- QA 新增 `visible-chroma-spill`，拦截不接近纯色键但形成连续绿/品红/青色轮廓的可见偏色。
- 三组回归合计：36 pass、0 warning、0 fail；三份 Contact Sheet 已人工检查。
- 回归产物：`output/dark-metal-regression-a`、`output/bright-cartoon-regression-b`、`output/lowlight-dark-regression-c`。

### 3.7 v0.5.0：P2 碎片策略真实校准

- 使用内置 `imagegen` 生成 Panel、Button、Icon_Equip、Icon_Skill 共 4 张真实校准 Sheet、16 件资源。
- 样本覆盖尖角、链条、悬挂件、独立符文和硬边火花。
- 统一 `15%` 合并比例改为分类级比例与像素上限，避免大面板按比例放宽到约 170–195px。
- Panel `0.06/64px`、Button `0.06/48px`、常规128图标 `0.12/48px`、Skill `0.15/96px`、Effect `0.18/128px`。
- 远离组件默认继续 warning；显式 `allow-small` 只接受绝对像素与锚点面积比例双重限制内的小组件，保留像素并记录，不接受显著第二主体。
- P2 真实回归 16 pass / 0 warning / 0 fail；旧三风格回归 36 pass / 0 warning / 0 fail。
- 产物：`output/p2-fragment-calibration`。

### 3.8 v0.6.0：P3 轻量人工校正体验

- bbox 预览显示候选编号、问题类型、严重级别和全局背景失败原因。
- 修正 JSON 保存 `detected_bbox`、候选级 review、字段级错误路径和组件/留白/背景/最低可见 Alpha 阈值建议。
- 应用前结构化拦截越界、重叠、可见前景裁断和非连续编号；失败不写正式 Manifest。
- 成功和失败均生成 `correction-validation.json` 与 `bbox-diff-preview.png`。
- 使用真实 12 件品红色键未知整图完成诊断、人工修正、透明导出和视觉验收：12 pass / 0 warning / 0 fail。
- 源码测试：49/49 通过；真实验收产物：`output/p3-unknown-sheet-real`。

### 3.9 v0.7.0：P4 失败矩阵扩充

- 新增 6 组矩阵：硬边部分透明光带、白金高光/深色描边、绿/品红近色主体、大画布逐像素漂移、跨槽噪声桥接、多合法远离装饰。
- 近色风险新增稳定不透明核心支持比例；有可靠核心的硬边光带可恢复，近色主体继续阻断。
- 大画布局部前景搜索扩到最多 32px；只处理背景邻域，禁止全图投影破坏确定前景。
- QA 扩展到主体内部强色键通道优势；发现模型色键反射时拒绝并重生成。
- 组件检测最低 Alpha 统一为 16；跨多个槽位中心的连通组件显式失败。
- 修复 `prepare_ui_run.py` 缺少 Runner 所需 `layout_json` 的单分类 Job schema Bug。
- 真实 12 件复杂 `Icon_Effect`：首版拒绝，二版 12 pass / 0 warning / 0 fail；产物 `output/p4-failure-matrix-real`。
- 源码测试：56/56 通过。

### 3.10 v0.10.0：P6 自然语言一键编排

- 新增 `orchestrate_ui_delivery.py`，统一首次准备、必需输入检查、断点续跑、Runner 和交付摘要。
- 缺图时返回 `awaiting-generation`，按 Job 列出精确输出路径、Prompt、参考图角色和 Matte 编辑源。
- 支持色键＋Matte 混合任务；原生 Alpha 任务额外等待来源侧车。
- Matte 预检失败后替换输入可直接恢复；完成态重复调用幂等复用。
- 每次调用写出 `qa/delivery-summary.json` 和 `qa/delivery-summary.md`。

## 4. 当前卡在哪

当前没有代码、测试、图片生成或 API 权限阻塞。P6 已完成代码与定向测试，最终验证数量以 CHANGELOG 最新记录为准。

已知环境限制：WindowsApps 内的 `codex.exe` 从 PowerShell 直接执行会报“拒绝访问”，所以不能用 `codex exec` 做新任务触发验收。此前已改用 Codex 桌面的独立任务接口完成 9 类验收，不要再浪费时间重复尝试 WindowsApps CLI。

当前尚未完成：

- Unity 业务事件、本地化、数据源和动画状态机自动接线。
- 模型原生 Alpha 仍为可选严格来源；只有用户明确要求源图直接携带 Alpha 时才需要外部授权。
- 混合展示图的全自动语义分类和遮挡内容恢复。
- 桌面 GUI。

## 5. 下一步计划

### P6：自然语言一键编排（已完成）

- 自然语言由 Codex 转为批量请求，确定性脚本不实现伪 NLP。
- 首次准备、缺图清单、补图续跑、Runner 和交付摘要已统一。
- 下一维护项为 P6.1 跨风格 Matte 回归。

### P7/P8：Unity 自动导入与九宫格（已实现）

- Unity 2022.3 + UGUI 作为正式兼容基线。
- 九宫格先生成带置信度的 Border 元数据，再由 batchmode 写入 SpriteImporter；低置信阻断，支持人工覆写。
- 界面 Prefab 由明确布局生成，不从截图猜业务交互。

### P5：复杂半透明特效生成链路（已完成）

完成内容：

1. 已完成：内置链路实测输出 RGB 烘焙棋盘格，无 Alpha；样本已固化。
2. 已完成：新增 `model-matte-derived` 双图 Job、Runner 分流、来源哈希、Alpha 保真和预乘 Alpha 缩放。
3. 已完成：使用内置 GPT Image 2 生成烟雾、玻璃、液体、柔光彩色 Sheet 与同图编辑 Matte。
4. 已完成：灰度/黑边/层次/背景/对齐预检、RGBA 合成、切割、Manifest、Contact Sheet、QA 和运行摘要。
5. 已完成：同步 Skill、协议、测试、README、AGENTS、CHANGELOG 和安装副本。

完成结果：四类真实样本 4 pass / 0 warning / 0 fail；来源明确记录为 `gpt-image-2-matte-derived`，不表述为模型原生 Alpha。

以下为已完成阶段：

### P1：真实生产样本回归（已完成）

- 暗黑金属、明亮卡通、低明度深色三套完成。
- 绿色、品红、青色第三色键均完成 Runner、Manifest、Contact Sheet、QA 和阈值诊断。
- 真实发现的漂白、缩放残色和互补色边缘偏色均已转成持久测试。

### P2：碎片策略真实校准（已完成）

- 已完成真实资源、分类参数、远离小碎片策略、测试、契约和文档同步。

### P3：轻量人工校正体验（已完成）

1. 已完成 JSON bbox 修正、标注预览、结构化预检和差异预览。
2. 已补齐越界、重叠、裁断、编号错误矩阵。
3. 保持 Codex 可操作的轻量方式，未开发桌面 GUI。

### P4：扩充失败矩阵（已完成）

- 半透明硬边光效。
- 白色高光叠加金属边。
- 深色主体贴近深色描边。
- 主体颜色接近绿色/品红色键。
- 大画布背景逐像素漂移。
- 两个槽位因噪声桥接。
- 同一资源多个合法远离装饰件。

### 最低优先级

- 桌面 GUI。只有核心流程长期稳定，且真实生产持续出现 JSON/预览无法解决的高频人工操作时，才重新评估；新增 GUI 技术栈仍需用户明确授权。

## 6. 绝对不要再踩的坑

### 6.1 不要只信自动 QA，必须看 Contact Sheet

本会话第一次抗锯齿测试显示 35/35 通过，但视觉检查发现：

- 白色主体有明显品红边。
- 金色和深色主体有绿色边。

原因是旧 QA 只检查“像素是否接近色键”，没有检查边缘 RGB 是否接近真实前景色。后来改成邻近稳定前景投影，并增加边缘色偏断言才真正通过。以后凡是 Alpha/净边算法变化，都必须生成 Contact Sheet 并视觉检查，脚本返回 `ok=true` 不代表可交付。

### 6.2 不要盲目扩大色键阈值

背景有色差时必须先看边框分布、置信度和近色主体风险。低置信度或 `near-key-subject-risk` 时禁止自动采用。不能为了让资源数量“看起来正确”而吞掉主体颜色。

### 6.2.1 不要把前景投影应用到确定前景

真实暗黑金属回归曾把局部前景估算应用到整个装备内部，导致黑铁和金边大面积漂白。投影只能作用于软遮罩过渡带；确定前景必须保留原始 RGB/Alpha。

### 6.2.2 不要直接缩放直通道 RGBA

低 Alpha 的色键边缘像素经直通道 Lanczos 缩放后可能重新达到 `alpha >= 16`，形成可见绿边。归一化必须先转预乘 Alpha 再缩放，并对最终 Contact Sheet 做视觉检查。

### 6.3 不要把 Layout Guide 当硬裁切框

槽位用于稳定归属和排序，不是主体的硬边界。合法尖角或轮廓可以进入纯背景 gutter，只要不触碰相邻主体、画布边缘或禁止安全区。

### 6.4 不要静默删除碎片或第二主体

近邻碎片可合并；远离碎片必须记录 warning；显著第二主体必须单独标记。不能因为“主图看起来差不多”就丢弃无法解释的组件。

### 6.5 不要混淆内部类别和文件名前缀

- 内部类别：`Icon_Effect`
- 文件名前缀：`09_Icon_Effect`

首次特效新任务验收返回了 `09_Icon_Effect`，严格格式失败。已在 Skill 和 AGENTS 中明确。Manifest、运行配置和触发验收必须使用无数字前缀的内部类别名。

### 6.6 不要把假棋盘格当透明通道

RGB 中烘焙的棋盘格只能用于展示。必须阻止正式透明导出，并要求纯色色键图或真实 Alpha。

### 6.7 不要只改安装目录

源码位置：

```text
D:\CuttingTool\skills\game-ui-asset-pipeline
```

安装位置：

```text
C:\Users\Admin\.codex\skills\game-ui-asset-pipeline
```

始终先改项目源码，再同步安装副本，最后比较逐文件哈希。

### 6.8 不要使用错误测试入口

唯一规定测试入口是标准库 `unittest`，不要尝试、探测或安装 `pytest`：

```powershell
$PYTHON = 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $PYTHON -m unittest discover `
  -s .\skills\game-ui-asset-pipeline\tests `
  -p 'test_*.py' `
  -v
```

不要假设裸 `python` 指向正确运行环境。

### 6.9 不要引入未经批准的范围

当前用户只有 Codex，没有 API Key。不要切到付费 Image API，不要引入 OpenCV，也不要启动桌面 GUI 技术栈。Unity 自动导入只允许写入用户明确授权的目标项目和生成根目录。

### 6.10 不要漏更新规范和变更说明

新增功能、优化算法或发现通用失败模式时，必须在同一任务内同步：

- 代码
- 测试
- `SKILL.md`
- 相关 `references/`
- `README.md`
- `AGENTS.md`
- `CHANGELOG.md`
- 安装副本

每次正式功能提交都必须有能看懂的变更记录，不能只写 Git commit message。

## 7. 常用路径和命令

### Git

```powershell
$GIT = 'C:\Program Files\Git\cmd\git.exe'
& $GIT status --short --branch
& $GIT log -5 --oneline
```

### 源码测试

```powershell
$PYTHON = 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $PYTHON -m unittest discover `
  -s .\skills\game-ui-asset-pipeline\tests `
  -p 'test_*.py' `
  -v
```

### 安装态测试

```powershell
& $PYTHON -m unittest discover `
  -s 'C:\Users\Admin\.codex\skills\game-ui-asset-pipeline\tests' `
  -p 'test_*.py' `
  -v
```

### 统一 Runner

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\run_ui_pipeline.py `
  --run-dir .\output\<project-id>
```

### P6 一键编排

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\orchestrate_ui_delivery.py `
  --request .\batch-request.json `
  --run-dir .\output\<project-id>
```

### Unity 导出

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\export_unity_ui.py `
  --run-dir .\output\<project-id> `
  --unity-project D:\CodeProjects\UIText `
  --unity-editor E:\UnityPro\2022.3.62f3c1\Editor\Unity.exe `
  --layout .\output\<project-id>\unity\unity-layout.json
```

## 8. 最终状态

- `xiuxian-ui-1980x1080-v1` 的参考对齐 HUD 已补齐独立仙侠场景背景与专用女性玩家头像，不再使用深色占位背景，也不再复用底栏 `FunctionCharacter` 作为资料头像。
- 正式 Manifest 当前为 88 件：85 pass / 3 warning / 0 fail。3 条 warning 为 2 个既有 Panel 远离碎片提示，以及整屏不透明背景预期产生的 `no-transparent-padding`。
- Unity 2022.3.62f3c1 最终导出：88 Sprite / 88 资源 Prefab / 1 Screen Prefab / 1 Preview Scene / 1 Preview PNG / 0 issue；日志包含 `GameUIImportComplete`。
- 最终视觉证据：`output/xiuxian-ui-1980x1080-v1/unity/previews/XiuxianMainHUDReferenceAligned-final.png`。
- 当前开发分支：`main`。
- v0.10.3 新增参考图接收关卡：初始化后暂停等待用户放图，用户确认后执行自动检查和逐图视觉检查；不合格时要求替换，全部通过前不进入资源清单和生成。
- v0.10.2 新增首次项目初始化：缺少项目名时先询问，获得后自动创建 `input/<project-id>/references/reference-notes.md`，重复调用不覆盖用户内容。
- v0.10.1 P6.1 已完成暗黑幻想、明亮卡通、科幻全息三套真实 GPT Image 2 RGB＋Matte 回归；每套覆盖 Smoke、Glass、Liquid、SoftGlow，合计 12 pass / 0 warning / 0 fail。
- 三套 Contact Sheet 已人工检查；Matte 均为同图编辑、画布一致且未缩放，`alpha_origin=gpt-image-2-matte-derived`。
- P7/P8 已进入 v0.12.0；下一阶段优先用真实商业 UI 页面回归 Border 和布局 Prefab，再评估更多显式组件类型。
- GUI 继续保持最低优先级。

## 9. 下个新窗口优先验收

在独立新窗口中触发 `game-ui-asset-pipeline`，验证真实首次使用行为：

1. 发送一个没有项目名的 UI 资源制作需求；预期 Skill 只询问项目名并暂停。
2. 回复英文项目名，例如 `onboarding-test-ui`；预期自动创建 `input/onboarding-test-ui/references/reference-notes.md`，返回绝对目录并暂停等待放图。
3. 检查 Markdown 是否自带填写注释、可见示例和占位表格，且第二次初始化不会覆盖手工修改。
4. 不放图片直接回复“已放好”；预期自动检查返回 `no-reference-images`，要求放图并继续暂停，不进入资源清单或生成。
5. 放入一张不合格图验证阻断，例如错误命名或小于 `256×256`；预期返回具体文件、原因和替换要求。
6. 替换为合格参考图后回复“已重新放好”；预期重新执行完整自动检查并逐张视觉检查，全部通过后才进入资源清单。

本轮源码与安装态全量测试均为 95/95 通过；Skill 源码与安装副本 63 个正式文件哈希一致。真实 Unity batchmode 返回码 0，2 Sprite / 2 资源 Prefab / 1 界面 Prefab / 0 issue。
