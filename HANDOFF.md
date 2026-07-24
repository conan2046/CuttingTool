# CuttingTool 会话交接

> 更新时间：2026-07-24
> 工作目录：`D:\CuttingTool`  
> 仓库：`https://github.com/conan2046/CuttingTool.git`  
> 当前工作分支：`main`
> 已完成功能基线：v0.15.0 P0/P1/P2 生成可靠性优化、v0.14.8 Panel 默认 Border 50、v0.14.7 Panel 单资源复用与 200×200 紧凑源、五界面 Unity 交付、自适应生图、快速源门禁、QA 纠错、TMP 文本及 `_Project` 目录规范

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
→ Unity Sprite/Border 配置、界面 Prefab（不生成单资源 Prefab）
```

核心原则：AI 负责视觉，Python 脚本负责确定性处理和验收。桌面 GUI 已明确降为长期最低优先级，不是当前开发目标。

## 3. 已经完成什么

### 3.0 v0.15.0：P0/P1/P2 生成可靠性优化

- 风险波次先生成 Panel、Button、Icon_Status；通过快速源门禁后再解锁普通图标。
- 快速源门禁缓存绑定图片、Job 请求、Layout Guide、透明模式和门禁版本；Panel/Button 在完整 Runner 前检查九宫格中间 60%。
- 自动色键使用 `subject_colors` / `subject_uses_*` 从绿、品红、青色中避冲突选择；显式冲突在生图前失败。
- 默认额外预算按 Panel、Button、色键风险图标组预留，并增加全局兜底，最高 5；显式总额优先。
- 新运行目录隔离为 `generated/current/`、`.local/backups/`、`reused-staging/` 和 `final/`；污染时写 `qa/run-preflight.json` 并阻断。
- `qa/pipeline-state.json` 保存恢复阶段和输入 SHA-256；`qa/operation-heartbeat.json` 标记 Runner 长操作状态。
- Unity layout schema 在生图前校验；连续重复同类生成故障不会重复降级并发。
- 源码与 Codex 安装态全量 `unittest` 均为 157/157；74 个正式 Skill 文件 SHA-256 差异 0。

### 3.0 v0.14.8：Panel 默认 Border 50

- Panel 未显式覆写时固定使用 Unity Border `[left,bottom,right,top] = [50,50,50,50]`，来源为 `panel-default-50`。
- `nine_slice_overrides` 优先；Button 继续自动推断，低置信仍阻断。
- Panel 源图宽或高不大于 `100px` 时预检失败，避免空中心拉伸区。
- 真实五界面重导中两张 Panel 均为四边 50；Unity 报告 `ok=true`、49 Sprite、5 Screen、0 issue。Editor 写出 `GameUIImportComplete` 后退出残留，已终止该完成态进程。
- 源码与 Codex 安装态全量 `unittest` 均为 150/150；74 个正式 Skill 文件 SHA-256 差异 0。

### 3.0 v0.14.7：Panel 单资源复用

- Panel 使用 `frame_style` 表达四边/四角设计；同值资源只生成一次，尺寸不参与判定，Unity 通过 Sliced 九宫格适配。
- 默认 Panel Job 为 `1024×1024 / 1×1`；本批通用 Panel 与边框设计不同的背包格 Panel 均使用预乘 Alpha 等比缩放归一化到 `200×200`，未追加生图调用。
- `output/xiuxian-ui-five-functions-v0144` 现为 42 个本批资源＋7 个复用资源，共 49 Sprite；QA 49/49 通过、0 warning、0 fail、质量 100、风格 71.41。
- 五个静态 Screen 共用通用 Panel，只保留四边设计不同的背包格 Panel；Unity 导入报告为 49 Sprite、5 Prefab、5 Scene、5 PNG、0 issue、296 个 Binding 已清理。
- 用户明确静态界面不需要继续追查 batchmode 预览偶发漏绘；当前以 Prefab 层级、Sprite 引用和导入报告完成结构验收。
- 源码与 Codex 安装态全量 `unittest` 均为 149/149；74 个正式 Skill 文件 SHA-256 差异 0，其中 Panel 复用、批处理和 Unity 导出定向测试 38/38。

### 3.0 v0.14.6：四角九宫资源与五界面 Unity 稳定交付

- `panel-sheet-01.png` 已按用户纠正重生成：中心与四边中间 60% 无图案，装饰只在四角固定区。
- Button/Panel 纹理 QA 只放宽低对比、低梯度材质变化；高对比图案仍 hard fail。
- `output/xiuxian-ui-five-functions-v0144` 最终为 45 个新资源＋7 个复用装备资源，共 52 Sprite；QA 52/52 通过、0 warning、0 fail。
- 五个 1920×1080 Screen 已导入 `D:\CodeProjects\UIText`：5 Prefab、5 Preview Scene、5 Preview PNG、0 单资源 Prefab、0 issue，移除 296 个临时 Binding。
- Unity Preview 使用 1:1 WorldSpace、纹理/UGUI 强制就绪、四帧合成；逐 Screen 独立复验记录位于 `unity/isolated-runs/`。
- 源码全量 `unittest` 146/146 通过；安装态与哈希一致性需在本段最后同步后确认。

### 3.0 v0.14.5：Runner 空特征崩溃修复

- 九宫格拉伸带出现空列/空行时记录 `gap_positions` 并 hard fail，不再触发 `IndexError`。
- 风格缩略图没有最低可见 Alpha 像素时记录 `style-profile-empty-visible-pixels`，携带 `asset_id/job_id/file`，不再抛异常中断。
- 真实五界面批次 `output/xiuxian-ui-five-functions-v0144` 已落盘完整 QA：期望 45、导出 44、21 hard fail、质量分 8、风格分 71.36；Unity 未启动。
- 当前候选失败原因：Button 实际 13 件且跨槽连通、缺 1 态、九宫格中段违规；`Amplify` 46 个可见色键污染像素；`RefiningStone` 1100 个可见色键污染像素。
- 全局额外生图预算 1 已被 Button 首轮重试耗尽；当前 `batch-request.json` 还错误写成 `unity_delivery.enabled=false`。
- 源码与安装态全量 `unittest` 各 144/144 通过；74 个正式 Skill 文件 SHA-256 差异 0。

### 3.0 v0.14.4：最终 Prefab 辅助脚本清理

- `GameUIElementBinding` 改为仅供导入期定位；全部接线完成后、保存 Screen Prefab 前递归移除。
- `GameUIViewSwitcher`、Button、Layout Group、ScrollRect、TMP 等正式功能组件不清理，按钮互斥切换保持有效。
- Unity 导入报告新增 `removed_helper_component_count`，最终 Prefab 不应再出现截图中的 `Game UI Element Binding (Script)`。
- 已真实重导 `xiuxian-ui-character-inventory-1920x1080-v1`：48 Sprite、4 Screen Prefab、4 Preview Scene、4 Preview PNG、0 issue，移除 125 个辅助组件；`CharacterLeftFixed`、`CharacterAttributeRight`、`CharacterInventoryRight`、`CharacterInventoryScreen` 的 Binding GUID 均为 0。
- `interaction-v0144.json`：`entry_count=2`，默认态、第二按钮切换、第一按钮恢复均通过，0 issue；根 Prefab 仍保留 1 个 `GameUIViewSwitcher`。
- 源码与安装态全量 `unittest` 各 140/140 通过；72 个正式 Skill 文件 SHA-256 差异 0。

### 3.0 v0.14.3：自适应三路图片生成

- 独立 Production Sheet 默认最多并行 3 个；Panel、Button、Icon_Status 同波最多 2 个，低风险 Job 可填补第 3 槽。
- Alpha Matte、原生来源侧车和所有重试保持独占串行；每个已到达 Production Sheet 立即执行快速源门禁。
- `qa/generation-runtime.json` 持久保存有效并发；`--generation-event rate-limit|timeout|disconnect` 每次降一级，最低 1。
- `qa/generation-queue.json` 升级为 schema v2，增加 `active_tasks`、波次类型、配置并发和有效并发，同时保留 `active_task` 兼容字段。
- 全局额外图片调用预算仍默认 1；任何硬 `fail` 继续阻断正式 Manifest。
- 源码与安装态全量 `unittest` 各 139/139 通过；72 个正式 Skill 文件 SHA-256 差异 0。

### 3.0 v0.14.2：生图调用压缩与快速源门禁

- `content_policy.item_icons=empty-slots|runtime-data` 会把无须生成的 `Icon_Item` 标记为 `exclude`，不进入批量请求。
- 绿色色键 `Icon_Status` 首轮 Prompt 使用深蓝封闭底板和银白隔离边，禁止绿色/青绿色反光。
- `quick_source_gate.py` 在完整 Runner 前检查解码、比例、槽位、触边和状态图标反光；失败只生成定向重试，不启动完整 Runner。
- v0.14.2 当时默认 `generation_budget.max_extra_calls=1`；v0.15.0 已改为按风险动态预留，显式总额仍优先。
- 图片生成继续固定 `sequential-inputs`、最大并发 1；不启用并行图片 Job。
- 源码与安装态全量 `unittest` 各 136/136 通过；72 个正式 Skill 文件 SHA-256 差异 0。

### 3.0 v0.14.1：真实角色/属性/背包组合交付

- `xiuxian-ui-character-inventory-1920x1080-v1` 完成 1920×1080 真实 Unity 交付：固定左区、属性右区、背包右区三个独立 Prefab，由 `CharacterInventoryScreen` 以 3 个 `PrefabInstance` 组合。
- 新增通用 `GameUIViewSwitcher` 与 `toggle_groups`，属性默认显示；Unity batchmode 实际调用属性/背包两个 `Button.onClick`，默认、切换、恢复全部通过。
- 用户明确要求背包不生成/不显示道具 Icon：本次合并 Manifest 为 48 Sprite（旧资源30、装备6、属性12），20 个已生成道具文件保留在来源运行但不进入 Unity 合并 Manifest；背包 Prefab 为 25 个空格位、0 个 ItemMount。
- Unity 报告：48 Sprite / 0 资源 Prefab / 4 Screen Prefab / 4 Preview Scene / 4 Preview PNG / 0 issue；根预览已人工检查，6 件装备和12个属性图标可见。
- 源码与安装态全量 `unittest` 各 131/131 通过；Skill 源码/安装副本 70 个正式文件 SHA-256 差异 0。首次 Unity 编译变量重名失败已修复，后续导入与交互验收均通过。

### 3.0 v0.14.0：单次多界面、逐张图片队列与自动 Unity 拼装

- 用户一次声明全部界面即可；Codex 建立一个项目级批量请求，不要求用户逐张下需求。
- `prepare_ui_batch.py` 固定写入 `generation_policy.mode=sequential-inputs`、`max_concurrent_image_jobs=1`，并为 Job 写稳定 `generation_sequence`。
- `orchestrate_ui_delivery.py` 每次更新 `qa/generation-queue.json/md`；同一时刻只有一个图片输入为 `active`，其余为 `blocked`，完成后续跑才激活下一项。
- `compile_ui_project_intake.py` 可从多个 Screen 的 `unity_elements` 构建统一布局；启用 Unity 时强制 `layout_confirmed=true`、绝对工程/Editor 路径和每屏非空显式布局。
- 资源 QA 通过后自动执行 Unity 导出；每个 Screen 分别生成 Prefab、Preview Scene 和预览 PNG。Unity 失败使用 `--force-unity` 单独续跑，不重新生成图片。
- 两个 Screen 可共享同一 Sprite；自动导出完成态重复调用幂等复用，不重复启动 Unity。
- 源码与安装态全量 `unittest` 各 129/129 通过；68 个正式 Skill 文件 SHA-256 一致，0 差异。

### 3.0 v0.13.1：Unity `_Project` 导出目录

- Sprite：`Assets/_Project/UI/Sprites/<project-id>`。
- Screen Prefab：`Assets/_Project/Prefabs/UI/Demo`。
- Preview Scene：`Assets/_Project/Scenes/Demo`。
- 单资源 Prefab 已取消；同项目旧 `_Generated/GameUI/<project-id>/Prefabs/Assets` 在导入时定向清理。
- 回滚只处理项目 Sprite 子目录和本次明确生成的 Screen Prefab/Preview Scene，不删除共享目录。

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

当前没有被旧五界面美术批次阻断。该批次已收敛为 49/49、0 warning、0 fail，并完成 49 Sprite、5 Screen Unity 结构交付；v0.15.0 的 P0/P1/P2 优化已在源码测试中通过。

本任务 P0/P1/P2 已完成，源码和安装副本验证通过。当前无技术阻断；未提交、未推送，除非用户另行明确要求。

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
- v0.15.0 已把队列升级为风险资源优先，并增加契约缓存、目录预检、状态账本和恢复心跳。
- 下一阶段仅需用下一次真实 UI 生产任务观察动态预算与风险波次是否进一步减少图片调用；不需要重跑已完成五界面批次。

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
