# CuttingTool 变更记录

记录每次正式功能提交的目标、主要改动、验证结果和兼容性影响。按时间倒序维护；纯格式整理或无功能影响的微小修正可以合并记录。

## 2026-07-21｜v0.13.0｜QA 驱动纠错、候选评分与失败 Job 定向重生成

发布分支：`codex/v0.13-quality-nine-slice`。

### 目标

把“Runner 发现失败后等待人工判断”升级为可追溯的 Codex 自动纠错闭环，同时保留正式交付的严格 `fail` 阻断。

### 完成

- 新增 `quality_feedback.py`：按数量、分离、构图、Alpha、Matte、尺寸和来源等维度计算 Run、Job、Asset 三级 `0–100` 质量分。
- 质量分只用于多候选排序；任一 `fail` 都保留硬阻断，不能被总分抵消。
- 编排器失败后自动选择一个最高优先级原因，生成 `qa/regeneration-plan.json/md` 和单原因纠错 Prompt。
- 计划精确声明需要替换的生产 Sheet、Alpha Matte 或原生 Alpha 来源侧车；Codex 负责按计划调用内置图片生成，Python 不调用图片 API。
- 候选使用全部必需输入的 SHA-256 组合指纹去重；原文件未变化时保持 `awaiting-regeneration`，不重复计次。
- 替代候选就绪后自动覆盖失败运行；默认最多 3 个候选，可配置为 1–5，耗尽后保持硬失败。
- `jobs.json` 持久化候选历史、分数、缺陷代码、重试次数和当前纠错目标。
- `delivery-summary.json/md` 增加质量分、硬阻断数和定向重生成入口。
- 新增 `test_quality_feedback.py`，扩充 P6 编排与 Delivery QA 测试，覆盖单原因选择、Matte 定向重试、未变化候选去重、恢复完成和预算耗尽。
- 新增 `style_consistency.py` 与 `test_style_consistency.py`：结合 Canonical 和 Sheet 间的调色板、平均色、亮度、饱和度、边缘密度输出逐 Job 与总风格分，并把漂移送入定向重生成。
- 使用装备强化参考图完成真实 GPT Image 多候选闭环：首轮 Button 受控暖红漂移分 28.27 被阻断；第二候选恢复冰蓝白玉风格；装备 Sheet 依次修复剑尖触边和人工发现的“斗笠误作头盔”。
- 最终真实批次 `output/xiuxian-ui-v013-enhancement`：10/10 导出，10 pass、2 warning、0 fail，质量 82，跨 Sheet 风格 67.10；两条 warning 为 Panel 色键边框波动与装备 Sheet 轻微风格漂移，Contact Sheet 人工复核通过。
- 用户复核发现两个 Panel 的上、下、左、右边中段仍有菱形/徽记，违反九宫格规则；已精修源 Sheet，清除 8 处中点装饰并重建连续边线，四角和中心材质保持不变。
- 修复根因：`build_prompt()` 之前没有把文档中的 Panel 九宫格规则写进实际生成 Prompt。现已强制禁止四边中间 60% 的星点、菱形、徽记、凸起和厚度变化。
- 新增 Panel/Button 共用的 `nine_slice_stretch_bands` 四边报告，检查外轮廓和内部纹理；分别用 `panel-stretch-band-decoration`、`button-stretch-band-decoration` 硬阻断，兼容保留 `panel_stretch_bands`。
- 新增 `make_nine_slice_preview.py`，按自动 Border 生成原尺寸、0.5×、1.5×、2× Sliced 对比图；真实 Panel 与 Button 四态预览均通过人工复核。
- 源码与安装态全量 `unittest` 各 120/120 通过；68 个正式 Skill 文件 SHA-256 一致，0 差异。
- 测试日志：`logs/unittest-v0.13.0-nine-slice.txt`、`logs/unittest-installed-v0.13.0-nine-slice.txt`。

### 范围

- 不新增图片 API、API Key、桌面 GUI、多 Provider 或跨引擎导出。
- 跨 Sheet 风格评分只处理视觉家族一致性，不替代 Contact Sheet 的人工资源语义与用途验收。

## 2026-07-20｜v0.12.6｜九宫格 Panel 拉伸带与控件安全区

状态：已完成并纳入当前版本基线。

### 目标

修复底部按钮压住最大外框，以及 Panel 的边中段装饰进入九宫格拉伸带后产生变形的问题。

### 主要改动

- 使用内置 GPT Image 2 精确编辑 `panel-sheet-01.png`：清除两块 Panel 上下左右边中段的星点、莲花和菱形装饰，重建连续边线；保留四角与 UniversalPanel 左上龙角。
- 保持生产 Sheet 为原始 `1254×1254 RGB`、两资源位置/数量和纯绿色键背景不变，重新执行完整切割、透明化、Manifest 和 QA。
- `InventoryActionsLayout` 上移 50px，并改为 `InventoryPanel` 子节点；按钮底边与 Panel 底边安全距离由 9px 增加到 59px。
- Panel 生成与 Unity 契约新增强制规则：独特装饰只位于四角固定区，四边中段和中心区必须干净可拉伸，禁止用异常大 Border 掩盖边中段装饰。

### 验证

- 整包资源：30 pass、0 warning、0 fail；两张 Panel 透明 PNG 与 Contact Sheet 已视觉检查。
- Unity：30 Sprite、30 资源 Prefab、1 Screen Prefab、1 Preview Scene、1 Preview PNG、0 issue。
- `UniversalPanelBase` 与 `InventorySlotFrame` 的自动 Border 置信度分别为 0.7854、0.8618；实际 Sliced 渲染四角稳定、边中段连续、无独特装饰拉长。
- 源码与安装态全量测试、Skill 哈希一致性：待最终回归后填写。

### 兼容性

- 继续使用 schema v1；现有非九宫格资源不受影响。
- 被替换前的 Panel Sheet 保留为 `generated/panel-sheet-01-pre-nine-slice-cleanup.png`，便于追溯。

## 2026-07-20｜v0.12.5｜Unity Scroll View 有限区域与溢出裁剪

状态：已完成并纳入当前版本基线。

### 目标

修复背包只有 GridLayoutGroup、内容增长后会越过规定区域的问题；将可增长列表统一为可裁剪、可滚动的 Scroll View 结构。

### 主要改动

- `unity-layout.json` schema v1 新增 `ScrollView` 与 `ScrollViewport`，支持 Content/Viewport 引用、滚动轴、MovementType、惯性、减速率和滚轮灵敏度。
- ScrollViewport 自动生成 `RectMask2D`；Content 支持 `ContentSizeFitter`，与 Grid/Horizontal/Vertical Layout Group 组合后按内容增长。
- Scroll View 默认使用透明 Raycast Image，不生成破坏现有美术的可见滚动条。
- Python 预检验证 ScrollView → Viewport → Content 引用链、滚动轴、枚举和非负参数，错误配置在启动 Unity 前失败。
- 角色界面背包改为垂直 Scroll View：Viewport 固定 772×632，Content Grid 为 5 列、当前 5 行；静态预览显示 4 行，第 5 行被裁剪并可向下滚动。

### 验证

- 定向 `test_unity_export`：16/16 通过；源码与安装态全量 `unittest`：各 106/106 通过。
- Skill 源码与安装副本：63 个正式文件 SHA-256 一致，0 差异。
- 真实 Unity 导入：30 Sprite、30 资源 Prefab、1 Screen Prefab、1 Preview Scene、1 Preview PNG、0 issue。
- Prefab 已写入 ScrollRect、RectMask2D、GridLayoutGroup、ContentSizeFitter；Content/Viewport 引用有效，垂直滚动开启、横向关闭。
- 1980×1080 Unity 渲染已视觉检查：Viewport 外内容隐藏，无白底、越界或底部按钮遮挡。

### 兼容性

- 继续使用 schema v1；既有 Image/Button/LayoutGroup 布局不受影响。
- 数量固定且保证不溢出的装饰排列仍可只用 Layout Group；动态或可增长有限列表默认必须使用 Scroll View。

## 2026-07-20｜v0.12.4｜Unity Layout Group 规则布局

状态：已完成并纳入当前版本基线。

### 目标

将装备位、页签、背包格和操作按钮等规则排列从逐项坐标改为 Unity UGUI Layout Group 容器统一控制。

### 主要改动

- `unity-layout.json` schema v1 新增 `GridLayoutGroup`、`HorizontalLayoutGroup`、`VerticalLayoutGroup` 元素类型。
- Grid 支持单元尺寸、二维间距、固定行列、起排轴和起始角；横纵 Layout 支持间距、子项尺寸控制和扩展策略；三者支持内边距与子项对齐。
- Layout Group 容器与子项均保留稳定 BindingId，子项通过 `parent_id` 进入容器，声明顺序决定布局顺序。
- Python 预检严格验证 Layout Group 枚举、布尔向量、尺寸和约束，避免无效配置进入 Unity。
- 角色界面改为 4 个规则容器：6 格装备 Grid、4 个页签 Horizontal、25 格背包 Grid、2 个操作按钮 Horizontal。

### 验证

- 定向 `test_unity_export`：14/14 通过；源码与安装态全量 `unittest`：各 104/104 通过。
- Skill 源码与安装副本：63 个正式文件 SHA-256 一致，0 差异。
- 真实 Unity 导入：30 Sprite、30 资源 Prefab、1 Screen Prefab、1 Preview Scene、1 Preview PNG、0 issue。
- Prefab 已写入 2 个 GridLayoutGroup、2 个 HorizontalLayoutGroup；子节点数量为 6、4、25、2。
- 1980×1080 Unity 渲染已视觉检查：四组排列整齐，无越界、重叠或散排。

### 兼容性

- 继续使用 schema v1；原 Image/Button 布局无需修改。
- Layout Group 只负责静态层级和规则排布，不生成业务事件、文本、本地化或数据绑定。

## 2026-07-20｜v0.12.3｜低 Alpha 外溢与画布拉伸修复

状态：已完成并纳入当前版本基线。

### 目标

修复按钮主体外侧被模型生成的低 Alpha 光圈污染，以及非预期宽高比的生成图被强制缩放后造成角色拉伸的问题。

### 主要改动

- `allow_attached_glow=false` 时，归一化阶段清理与稳定主体边缘分离的低 Alpha 外溢，同时保留紧贴轮廓的抗锯齿像素，并记录移除数量。
- Runner 在生产尺寸调整前校验生成图与请求画布的宽高比；比例不一致直接失败，禁止非等比拉伸。
- 全局组件先按槽位中心初分，再按各资源主组件边界距离纠正跨槽碎片归属；避免宽面板的分离边饰串入相邻资源。
- 修正 `xiuxian-ui-character-1980x1080-v3` 角色彩色图与 Matte：等偏移补齐为 2048×2048，不缩放主体；Unity 布局启用等比显示。
- 新增低 Alpha 外溢清理与生成画布比例不一致阻断测试。

### 验证

- 源码与安装态全量 `unittest`：各 102/102 通过；63 个正式 Skill 文件 SHA-256 一致，0 差异。
- 真实项目重跑：30 个资源，30 pass、0 warning、0 fail；20/20 个 Button 完成外溢清理，共移除 511825 个低 Alpha 像素。
- `InventorySlotFrame` 的左侧跨槽碎片已重新归属到 `UniversalPanelBase`，最终 PNG 与 Unity 25 格渲染均无污染。
- 角色输出裁切与内容尺寸均为 527×886、缩放比 1.0，不再拉伸。
- Unity 重新导入：30 Sprite、30 资源 Prefab、1 Screen Prefab、1 Preview Scene、1 Preview PNG、0 issue；渲染检查通过。

## 2026-07-17｜v0.12.2｜九宫格 PPU 联动修复

状态：已完成并纳入当前版本基线。

### 目标

修复九宫格 Border 虽然落在源图结构线上，但固定 PPU=100 导致矮目标控件中固定边框总尺寸超过控件高度、被 Unity 比例压缩变形的问题。

### 主要改动

- Panel/Button 收集全部布局引用尺寸，按最小源图缩放比自动推导 PPU；手工 `pixels_per_unit_overrides` 优先。
- 新增 Border/PPU/目标尺寸联合几何校验，固定区超过目标宽高时在 Unity 启动前阻断。
- Unity 计划记录每张 Sprite 的 PPU、来源、布局缩放比和目标尺寸，便于追溯。
- 新增自动推导及超限阻断测试。

### 验证

- 真实 Unity 重新导入：86 Sprite、86 资源 Prefab、1 Screen Prefab、1 Preview Scene、1 Preview PNG、0 issue。
- `QuestRowFrame` 实际 `.meta`：Border `[180,95,180,95]`，PPU `447.8261`；修复后 Unity 渲染不再压扁上下边框。
- 源码与安装态全量 `unittest`：各 99/99 通过；63 个正式 Skill 文件 SHA-256 一致，0 差异。

## 2026-07-17｜v0.12.1｜真实 HUD 拼装与 Unity 视觉验收

状态：已完成并纳入当前版本基线。

### 目标

使用 `output/xiuxian-ui-1980x1080-v1` 的 86 件正式资源验证完整 Prefab 拼装，而不是只验证几个单件效果图。

### 主要改动

- Unity 布局新增 RGBA 颜色层及 Button Highlighted/Pressed/Disabled 状态资源引用。
- 具有状态资源的 Button 自动改用 SpriteSwap，不再只使用 ColorTint。
- 每个 Screen 自动生成带 Camera、CanvasScaler、GraphicRaycaster 和 EventSystem 的 Preview Scene。
- Unity batchmode 自动渲染目标分辨率 Preview PNG，作为 Prefab 视觉验收证据。
- 新增 1980×1080 修仙 HUD 布局：顶部状态栏、迷你地图、活动栏、任务面板、四条任务、聊天区、进度条及五格功能导航。

### 验证

- 真实 Unity 导入：86 Sprite、86 资源 Prefab、1 Screen Prefab、1 Preview Scene、1 Unity Preview PNG、0 issue。
- Screen Prefab：47 个 BindingId、9 个 Button；9/9 均为 SpriteSwap，Highlighted/Pressed/Disabled 均非空。
- Unity 日志包含 `GameUIImportComplete`，未发现编译错误或预览渲染失败。
- 源码与安装态全量 `unittest`：各 97/97 通过；63 个正式 Skill 文件 SHA-256 一致，0 差异。

### 兼容性

- 仍保持 schema v1；新增字段均有默认值，旧布局继续使用 ColorTint。
- 当前资源不含场景背景和角色，Preview 中央区域按 HUD 用途保留为空。

## 2026-07-17｜v0.12.0｜Unity 自动导入、九宫格与交互 Prefab

提交：随本记录同提交。

### 目标

把 QA 通过的 UI 位图继续交付到 Unity 2022.3，形成可追溯、可阻断、可回滚的 Sprite 与 UGUI Prefab。

### 主要改动

- 新增 `prepare_unity_export.py`、`export_unity_ui.py`、`infer_nine_slice.py` 和 `rollback_unity_export.py`。
- 新增 Unity 嵌入 UPM 包，批量配置 Sprite Single、Alpha、PPU、Pivot、Border，并生成资源/界面 Prefab。
- Panel/Button 九宫格使用确定性结构推断；低置信或无有效中心区在 Unity 启动前阻断，支持显式 Border 覆写。
- 新增 schema v1 `unity-layout.json`，正式支持 Image/Button、父子层级、锚点、Pivot、位置和尺寸。
- 输出 Unity 预检、导入报告、batchmode 日志和项目级回滚清单；默认只写 `Assets/_Generated/GameUI/<project-id>`。
- 新增 Unity 导出契约、示例布局、Skill 触发评测和测试矩阵；版本升级为 `0.12.0`。

### 验证

- 源码与安装态全量 `unittest`：各 95/95 通过；日志为 `logs/unittest-v0.12.0.txt`、`logs/unittest-installed-v0.12.0.txt`。
- 真实 Unity 2022.3.62f3c1 batchmode：返回码 0；导入 2 Sprite、生成 2 资源 Prefab 和 1 界面 Prefab，0 issue。
- 两个测试 Sprite 自动 Border 均为 `[13,13,13,13]`；Button 资源/界面 Prefab 均验证 Raycast、`Button.targetGraphic` 和 BindingId。
- Unity 证据：`output/unity-e2e/unity/unity-import-report.json`、`unity-batch.log`、`unity-import-plan.json`。
- Skill 源码与安装副本：63 个正式文件 SHA-256 一致，0 差异。

### 兼容性

- 当前正式支持 Unity `2022.3.x` 与 UGUI；不修改用户手工 Prefab。
- 业务点击事件、本地化、数据绑定和动画控制器仍由目标项目实现。

## 2026-07-17｜v0.11.0｜自动需求接收、跨界面复用与连续执行

提交：随本记录同提交。

### 目标

修正真实测试中参考说明依赖用户填写、确认项分散、资源清单后停顿、后续界面重复生成和无法从中间阶段进入的问题。

### 主要改动

- 参考图通过后由 Codex 自动分析并维护 `reference-notes.md` 自动区，保留区外人工内容。
- 界面布局、UI 元素与主参考一致性、差异说明和界面像素尺寸合并为一次用户确认。
- 新增 `compile_ui_project_intake.py`，自动输出 `ui-resource-inventory.md/json` 与 `batch-request.json`。
- 首界面全部生成；后续界面按 `category + semantic_name + state` 复用，忽略尺寸并记录来源。
- 新增 `ui-asset-catalog.json` 项目目录；完成 Runner 后自动从正式 Manifest 更新。
- `awaiting-generation` 改为 Codex 内部生成待办，补图后自动续跑，不再向用户停顿。
- 正式定义 intake、generation、processing、unknown-sheet、qa-only、resume 六类阶段入口。
- 新增断线恢复契约：保存轻量检查点、换新任务引用旧任务 ID、串行检查；明确 WebSocket 断开后当前任务无法自行执行回调的产品边界。
- 新增复用/尺寸/差异说明/自动回写测试和两条 Skill 行为评测。
- 项目版本升级为 `0.11.0`。

### 验证

- 定向 `unittest`：11/11 通过；源码与安装态全量 `unittest`：各 86/86 通过。
- 覆盖自动区不破坏人工文字、首界面强制生成、后续界面复用、跨尺寸复用、差异说明必填和 Catalog 合并。
- 完整测试日志：`logs/unittest-v0.11.0.txt`、`logs/unittest-installed-v0.11.0.txt`。
- Skill 源码与安装副本：51 个正式文件 SHA-256 一致，0 差异。

### 兼容性

- 保留旧批量请求 schema、统一 Runner、未知整图和原生/Matte/色键处理方式。
- 已有运行目录可直接 `resume`；已有 Sheet 不再强制重新走项目初始化。
- 断线自动创建新任务仍依赖 Codex 桌面提供断线回调；Skill 负责恢复协议和可追溯检查点，不能伪造产品回调。

## 2026-07-17｜v0.10.3｜参考图接收与强制验收关卡

提交：随本记录同提交。

### 目标

修正首次初始化后直接进入后续流程的问题，确保用户先放置合格参考图，Skill 验收通过后才开始资源清单和生成。

### 主要改动

- 初始化项目后返回参考图绝对目录并暂停，明确等待用户回复“已放好”。
- `reference-notes.md` 默认包含 Markdown 填写注释、可见示例、主/辅参考图表格和项目需求占位，方便新手直接照填。
- 新增 `validate_ui_references.py`：检查说明文件、图片数量、格式、可读性、动画、尺寸、命名、唯一主参考图和重复内容。
- 新增参考图接收契约：自动检查后必须使用 `view_image` 逐张检查清晰度、完整性、水印/大字污染、角色和风格冲突。
- 自动或视觉检查失败时返回具体文件、原因和替换要求；用户替换后完整复验，全部通过前禁止资源清单、请求 JSON 和图片生成。
- 新增自动检查单元测试和参考图关卡触发评测；同步新手指南、README、AGENTS、HANDOFF。
- 项目版本升级为 `0.10.3`。

### 验证

- 覆盖空目录、合法主/辅参考图、错误命名/小尺寸和重复内容。
- 触发评测覆盖初始化后暂停、用户确认放图、自动检查、逐图检查和失败替换循环。
- 源码与安装态全量 `unittest`：82/82 通过。
- Skill 源码与安装副本：47 个正式文件 SHA-256 一致，0 差异；`SKILL.md` 为 419 行。

### 兼容性

- 已知运行目录续跑和用户直接提供的未知整图诊断不强制走新项目参考图关卡。
- 不修改请求 schema、Runner、图片后处理算法或正式输出格式。

## 2026-07-17｜v0.10.2｜首次项目初始化

提交：随本记录同提交。

### 目标

把新手首次使用时的项目目录和参考图说明文件创建动作纳入 Skill，避免要求用户手工建立目录或 Markdown。

### 主要改动

- Skill 首次触发且缺少项目名时，先询问项目名并暂停；需求中已有项目名时直接使用，不重复询问。
- 新增 `initialize_ui_project.py`，按现有项目名规则创建 `input/<project-id>/references/reference-notes.md`。
- 说明文件包含主参考图、辅助参考图职责和项目需求模板；重复初始化幂等复用，不覆盖用户内容。
- 新增初始化单元测试和首次使用触发评测；同步新手指南、README、AGENTS、HANDOFF 和 Skill UI 元数据。
- 项目版本升级为 `0.10.2`。

### 验证

- 覆盖首次创建、项目名归一化、重复调用保护用户内容和无有效英文项目标识失败。
- 首次使用评测固定首动作为询问缺失项目名，获得后运行初始化脚本。
- 源码与安装态全量 `unittest`：76/76 通过。
- Skill 源码与安装副本：44 个正式文件 SHA-256 一致，0 差异；`SKILL.md` 为 408 行。

### 兼容性

- 已有项目、已知运行目录和未知整图续跑不强制重新初始化。
- 不修改请求 schema、Runner、图片算法或正式输出格式。

## 2026-07-17｜文档｜新手操作与需求模板

提交：随本记录同提交。

### 目标

为第一次使用 CuttingTool 的用户提供从放置参考图、描述多图角色、提交自然语言需求到检查最终交付的完整操作入口。

### 主要改动

- 新增根目录 `BEGINNER_GUIDE.md`，提供最短操作流程、参考图目录、多图优先级、自然语言模板、JSON 示例和验收方法。
- 新增 `input/README.md`，固定本地输入目录结构与文件命名建议。
- 新增可直接复制修改的 `samples/ui-request-example.json`。
- `.gitignore` 默认排除 `input/` 中的私人参考图，只保留目录说明文件。
- README 增加新手指南入口；AGENTS 补充 `input/` 目录职责。

### 验证

- JSON 示例通过 UTF-8 解析。
- 示例中的类别、透明模式和参考图字段与当前批量请求契约一致。
- 本次不修改 Python、Skill、Runner 或输出格式，因此无需重跑图片端到端测试。

### 兼容性

- 不影响现有运行目录、历史请求和已安装 Skill。
- 参考图仍可使用任意有效绝对路径；`input/` 是推荐入口，不是脚本硬限制。

## 2026-07-17｜v0.10.1｜P6.1 跨风格 Matte 回归

提交：随本记录同提交。

### 目标

使用真实 GPT Image 2 样本验证 `model-matte-derived` 在差异明显的游戏 UI 风格下仍能稳定生成、对齐、切割和交付烟雾、玻璃、液体与柔光特效。

### 主要改动

- 新增暗黑幻想、明亮卡通、科幻全息三套固定回归请求，统一使用 `2×2` 布局和 `Smoke → Glass → Liquid → SoftGlow` 顺序。
- 每套均通过内置 GPT Image 2 生成纯黑底 RGB Sheet，再以同图编辑方式生成中性灰度 Matte。
- 保留三套完整运行目录、生成源、Matte、来源哈希、正式透明 PNG、Manifest、QA、Contact Sheet 和交付摘要。
- 更新 README、HANDOFF 和样本验收记录；项目版本升级为 `0.10.1`。

### 验证

- 三套端到端合计：12 pass / 0 warning / 0 fail；每套均为 4/4 资源通过。
- RGB 与 Matte 均为 `1254×1254`，未发生自动缩放；灰度通道差异 P95 均为 2，边框 Alpha P95 不超过 1。
- Matte bbox IoU：暗黑幻想 0.9950、明亮卡通 0.9612、科幻全息 0.9837；每套均保留 256 个 Alpha 等级。
- Manifest 均记录 `alpha_origin=gpt-image-2-matte-derived`；三套 Contact Sheet 已人工检查，顺序、透明层次、轮廓和风格一致性符合交付要求。
- 源码与安装态 `unittest`、源码/安装副本哈希一致性在本次提交前重新验证。

### 兼容性

- 本次仅扩充真实回归样本和验收证据，不修改核心算法、Job schema、Skill 触发范围或依赖。
- 不需要 API Key，不使用付费 Image API，不修改 Unity 项目；P7、P8 仍按既定顺序单独实施。

## 2026-07-17｜v0.10.0｜P6 自然语言一键编排与交付摘要

提交：随本记录同提交。

### 目标

把多分类 UI 生产从“手动依次运行准备器和 Runner”收敛为 Codex-first 一键编排流程，支持缺图暂停、补图续跑、失败恢复、完成态复用和统一交付摘要。

### 主要改动

- 新增 `orchestrate_ui_delivery.py`：首次传入批量请求建立 Job；后续只传运行目录即可检查输入并自动继续。
- 建立 `unprepared → awaiting-generation → ready-for-processing → complete|failed` 状态机；缺图是正常暂停，返回精确 Job、输出路径、Prompt、参考图角色和 Matte 编辑源。
- 按透明模式检查必需输入：色键 Sheet、RGB＋Matte 双图、原生 RGBA＋来源侧车；原生来源侧车缺失时不提前进入 Runner。
- 支持 Matte 预检失败后替换生成图直接恢复；已有正式 Manifest 的失败重跑要求显式 `--force-run`；完成态重复调用幂等复用。
- 每次调用生成 `qa/delivery-summary.json` 和 `qa/delivery-summary.md`，统一汇总生成方式、Job/输入进度、结果数量、交付路径、人工处理项和下一步动作。
- 新增 P6 编排契约、混合任务测试和静态触发评测；同步 Skill、OpenAI UI 元数据、README、AGENTS 和 HANDOFF。
- 项目版本升级为 `0.10.0`；P7 Unity 自动导入、P8 九宫格边界推断进入后续排期，本阶段未实施。

### 验证

- 源码 `unittest`：72/72 通过。
- 安装态 `unittest`：72/72 通过。
- P6 混合端到端：`Icon_Item` 色键＋`Icon_Effect` Matte，首次缺少 3 个输入，部分补图后 1/2 Job 就绪，最终 4 pass / 0 warning / 0 fail；完成态重复调用成功复用。
- 失败恢复：非灰度 Matte 预检失败不创建正式 Manifest，替换正确 Matte 后恢复完成。
- Contact Sheet 已人工检查：2 个道具和 2 个半透明特效顺序正确、背景透明、轮廓完整。
- JSON/Markdown 交付摘要、Manifest、QA、运行摘要路径一致。
- P6 静态触发评测：1/1 通过；九类既有独立新任务触发验收仍为 9/9。
- Skill 源码与安装副本：42 个正式文件 SHA-256 一致，0 缺失、0 额外、0 差异。

### 兼容性

- 不新增依赖、API Key、付费调用、OpenCV、桌面 GUI 或 Unity 项目修改。
- 现有 `prepare_ui_batch.py` 与 `run_ui_pipeline.py` 继续作为分步调试入口；P6 编排器是新的推荐完整交付入口。
- Unity 导入和九宫格仅进入排期，后续分别立项、验证和授权实施。

## 2026-07-17｜v0.9.1｜P4/P5 合并审查加固

提交：随本记录同提交。

### 目标

在 P4、P5 依次合入 `main` 前完成独立代码审查，修复透明来源校验和本机路径回归，确保远程分支成果可直接安装使用。

### 主要改动

- `model-matte-derived` 新增彩色源图与 Matte 画布尺寸强校验；尺寸不一致在正式输出前失败，不再通过自动缩放冒充像素对齐。
- `native-alpha-required` 来源侧车新增非空 `generation_method` 校验，避免缺少生成方式的来源文件通过证明链路。
- 修复 P5 文档把本机路径写成 `C:\Users\Administrator` 的回归，恢复项目实际使用的 `C:\Users\Admin`。
- 同步更新 Skill、透明来源契约、README、AGENTS、HANDOFF 和版本号；项目版本升级为 `0.9.1`。

### 验证

- P4 独立源码 `unittest`：56/56 通过。
- P5 修复后源码 `unittest`：67/67 通过；安装态 `unittest`：67/67 通过。
- P5 确定性 RGB＋Matte 端到端：4 pass / 0 warning / 0 fail；Contact Sheet 已人工检查，透明层次、轮廓、顺序和背景显示正常。
- 新增回归：Matte 尺寸不一致、原生来源缺少生成方式均被正式输出前阻断。
- Skill 源码与安装副本：39 个正式文件 SHA-256 一致，0 缺失、0 额外、0 差异。

### 兼容性

- 不新增依赖、API Key、付费调用、OpenCV、桌面 GUI 或 Unity 自动导入。
- 合法且同尺寸的 RGB＋Matte Job 行为不变；历史上依赖自动缩放错尺寸 Matte 的输入现在会明确失败并要求重新生成对齐图。

## 2026-07-17｜文档｜GitHub CLI 路径与发布检查

提交：随本记录同提交。

### 目标

固化本机 GitHub CLI 的可执行路径与发布前检查方式，避免 PowerShell PATH 未刷新时误判 `gh` 未安装。

### 主要改动

- 在 `AGENTS.md` 记录 `C:\Program Files\GitHub CLI\gh.exe` 固定路径。
- 规定提交推送或创建 PR 前执行版本和认证状态检查，并禁止记录 Token。

### 验证

- `gh 2.96.0` 可执行。
- GitHub 账号 `conan2046` 已认证，Git 操作协议为 HTTPS，具备仓库发布所需权限。

### 兼容性

- 仅补充工具说明，无代码、依赖、资源格式或流水线行为变化。

## 2026-07-16｜v0.9.0｜P5 GPT Image 2 RGB＋Alpha Matte 双图链路

提交：随本记录同提交。

### 目标

不依赖 API Key，直接使用 Codex 内置 GPT Image 2 完成烟雾、玻璃、液体和柔光的连续半透明 RGBA 生产，同时严格区分 Matte 推导 Alpha 与模型原生 Alpha。

### 主要改动

- 新增 `transparency_mode=model-matte-derived`，批量和单分类准备器同时生成彩色 Sheet Prompt、Alpha Matte Prompt、双图输出路径和 Job 元数据。
- 彩色图固定使用纯黑 RGB 背景；Matte 通过同图编辑生成，黑/白/灰分别表示透明/不透明/部分透明。
- 新增双图合成器：估算真实黑背景，按 `F=(C-(1-α)B)/α` 恢复直通道前景 RGB，零 Alpha 隐藏 RGB 清零。
- Runner 在正式输出前验证灰度纯度、黑边、连续 Alpha、彩色背景平整度、双图包围框和像素覆盖关系，并记录双图 SHA-256。
- 新增非灰度、全不透明、错位和背景污染失败矩阵；任何预检失败均不创建正式 Manifest。
- Manifest、QA 和运行摘要记录 `alpha_origin=gpt-image-2-matte-derived`，不冒充模型原生 Alpha。
- 原有 `native-alpha-required` 继续保留为独立可选模式；版本升级到 `0.9.0`。

### 验证

- 内置 GPT Image 2 真实生成 1 张彩色 Sheet＋1 张 Matte，覆盖烟雾、玻璃、液体、柔光四类资源。
- 真实 Matte：256 个 Alpha 等级、731103 个部分透明像素、源图/Matte 包围框 IoU 0.9625、源图覆盖率 0.8336、Matte 支持率 0.9998。
- 真实端到端：4 pass / 0 warning / 0 fail；Contact Sheet 已人工检查，四类透明层次、轮廓、缩放和颜色均通过。
- 源码 `unittest`：65/65 通过。
- 安装态 `unittest`：65/65 通过；源码/安装副本 39 个正式文件 SHA-256 完全一致，缺失、差异和额外文件均为 0。

### 兼容性

- 不新增 API Key、付费调用、Python 依赖、OpenCV、桌面 GUI 或 Unity 自动导入。
- 现有色键、已有 Alpha 和模型原生 Alpha Job 行为不变；Matte 模式为显式 opt-in。

## 2026-07-16｜v0.8.0｜P5 原生 Alpha 接入、来源证明与失败降级

提交：随本记录同提交。

### 目标

建立烟雾、玻璃、液体、柔光的原生 RGBA 接入链路，先用实测证明内置生成边界，再实现不依赖色键估算的来源校验、保真处理和失败阻断。

### 主要改动

- 使用内置 `imagegen` 生成四类透明特效探测 Sheet；结果为 `1254×1254 RGB` PNG，棋盘格烘焙进像素，无 Alpha 通道。真实失败样本固化到 `samples/native-alpha`。
- 批量和单分类请求新增 `transparency_mode=native-alpha-required`；准备器拒绝把 `built-in-imagegen` 配置为原生来源，并生成独立来源侧车路径。
- 新增原生 Alpha 预检：验证 RGBA、透明像素、部分透明像素、Alpha 等级、源图 SHA-256、模型/生成方式、`alpha_origin=model-native` 和 `background_removal_applied=false`。
- 原生预检失败只写 Job 报告、总 QA 和失败摘要，不创建正式 Manifest、Contact Sheet 或资源 PNG。
- 原生分流只清理零 Alpha 隐藏 RGB；生产画布缩放和单体归一化统一使用预乘 Alpha Lanczos。
- Manifest 追加透明模式、Alpha 来源、源图哈希和来源侧车路径；最终 QA 检查连续 Alpha 层次是否在切割/缩放后丢失。
- 新增原生 Alpha 契约、四类合成矩阵和真实内置失败回归；版本从 `0.7.0` 升级为 `0.8.0`。

### 验证

- P4 基线：56/56 通过。
- 源码 `unittest`：60/60 通过。
- 安装态 `unittest`：60/60 通过；真实内置失败样本使用 Skill 内自包含派生裁片，安装后不依赖项目根目录。
- P5 定向矩阵：4/4 通过，覆盖烟雾、玻璃、液体、柔光、内置 RGB 棋盘格拒绝和背景移除伪原生拒绝。
- 合成端到端：4 pass / 0 warning / 0 fail；Manifest、来源报告、Contact Sheet、QA 和运行摘要完整。
- Contact Sheet 已人工检查：四项渐变 Alpha 可见，透明留白、缩放和分类顺序正确；该合成样本只验证算法，不替代外部真实生成验收。
- Skill 源码与安装副本：38 个正式文件哈希一致，0 差异。
- 外部真实生成尚未执行：需要用户再次确认带 API Key/可能计费的 `gpt-image-1.5` 透明回退。

### 兼容性

- 现有色键和已有 Alpha Job 默认行为不变；原生模式为显式 opt-in。
- 不新增 Python 依赖、OpenCV、桌面 GUI 或 Unity 自动导入。
- `native-alpha-required` 使用 Manifest schema v3 和来源侧车文件；旧运行目录继续按原路径处理。

## 2026-07-16｜路线调整｜P5 原生透明特效链路升为最高优先级

提交：随本记录同提交。

### 目标

将烟雾、玻璃、液体、柔光等复杂半透明资源从远期能力调整为下一阶段最高优先级，避免继续把色键估算 Alpha 当作原生透明能力。

### 主要改动

- HANDOFF 新增 P5 执行清单和完成标准，下个会话直接进入原生透明链路开发。
- README 和 AGENTS 同步路线优先级、能力边界、真实样本矩阵及失败降级要求。
- 明确必须证明 Alpha 来自生成源；内置链路不支持时先提交实测证据，再确定最小外部方案。

### 验证

- 本次仅调整路线、协议和交接，无代码行为变化，不运行单元测试。
- 已检查 AGENTS、README、HANDOFF 与现有 Skill 范围，P5 不改变已交付 V1 色键链路行为。

### 兼容性

- 不新增依赖，不产生 API 费用，不改变现有 CLI 和输出格式。
- 用户已授权推进原生透明能力；实际付费 API 调用仍需在确认方案和凭据后执行。

## 2026-07-16｜v0.7.0｜P4 失败矩阵扩充与复杂边缘真实回归

提交：随本记录同提交。

### 目标

扩充色键、复杂边缘、跨槽桥接和多碎片失败矩阵，用真实 `Icon_Effect` Sheet 暴露并修复仅靠既有合成样本无法发现的问题。

### 主要改动

- 新增 P4 六组固定矩阵：硬边部分透明光带、白金高光/深色描边、绿/品红近色主体、大画布逐像素色键漂移、跨槽噪声桥接、多个合法远离小装饰。
- 近色风险新增 `stable_core_support_ratio`：稳定不透明核心不少于含糊过渡像素时允许恢复硬边光带；缺少核心的近色主体继续阻断自动采用。
- 大画布局部前景搜索半径扩大到最多 `32px`，覆盖模型和生产放大形成的宽色键反射带；处理仍限于背景邻域，避免再次漂白确定前景。
- 新增 `discarded_opaque_chroma_spill_pixels`，清理背景邻域内仍不透明的强色键残边。
- `visible-chroma-spill` 从透明边缘扩展到整个 `alpha >= 16` 可见主体；模型把色键反射画进主体内部时强制拒绝并重生成，不做破坏纹理的全图去色。
- 连通域最低 Alpha 从 `8` 调整为 `16`；新增 `cross-slot-connected-component`，显式拦截覆盖多个槽位中心的噪声桥接。
- 修复单分类 `prepare_ui_run.py` 仍输出 schema v1、缺少 `layout_json` 导致统一 Runner `KeyError`；现在请求与 Job 均使用 schema v2，并记录 `expected_count`。
- 项目版本从 `0.6.0` 升级为 `0.7.0`；同步 Skill、色键/碎片契约、README、AGENTS、HANDOFF 和测试。

### 验证

- 源码 `unittest`：56/56 通过。
- 真实复杂边缘回归：内置 `imagegen` 生成 12 件 `Icon_Effect`。首版因内部绿色反射和低 Alpha 跨槽桥接被视觉/规则拒绝；二版 12/12 通过，0 warning，0 fail。
- Contact Sheet：人工检查通过；白金高光、黑紫深描边、环形透明孔洞、硬边光带和分离碎片完整，无绿边、误切、错误桥接或纹理漂白。
- 安装态 `unittest`：56/56 通过。
- Skill 源码与安装副本：34 个正式文件哈希一致，0 差异。

### 兼容性

- 不新增依赖、API Key、OpenCV、桌面 GUI 或 Unity 自动导入。
- 单分类 Job schema 升级到 v2，Runner CLI 不变；旧的 schema v1 运行目录需补充 `layout_json` 后再运行。
- Alpha 8–15 的亚可见像素不再参与组件连接；达到最低可见阈值的合法效果继续保留。

## 2026-07-16｜v0.6.0｜P3 轻量人工校正体验

提交：随本记录同提交。

### 目标

强化未知整图的 Codex-first 人工校正体验，在不引入桌面 GUI 的前提下提供可定位、可修正、可对比、可阻断的 bbox 审核链路。

### 主要改动

- bbox 标注预览新增候选编号、候选问题类型、严重级别、颜色图例和全局背景失败原因。
- 修正 JSON 升级为 schema v2，新增原始 `detected_bbox`、候选级 review、字段级 JSON 错误路径，以及组件像素、bbox 留白、背景阈值和最低可见 Alpha 建议。
- 应用修正前新增结构化预检：越界、重叠、空框、可见前景裁断、重复来源编号、非法类别和非连续分类编号均在正式导出前阻断。
- 预检错误包含 `message`、`location`、`suggestion`、推荐 bbox、触碰边和安全留白；失败时不创建正式 Manifest 或资源 PNG。
- 成功和失败均生成 `correction-validation.json` 与 `bbox-diff-preview.png`；差异图并排标记 detected/approved 和 changed/unchanged。
- 裁断检查统一使用 `alpha >= 16` 的最低可见阈值，避免低 Alpha 色键清理残留误报，同时继续阻断肉眼可见的截断。
- 项目版本从 `0.5.0` 升级为 `0.6.0`；同步 Skill、未知整图契约、README、AGENTS、HANDOFF 和测试。

### 验证

- 源码 `unittest`：49/49 通过。
- 真实未知整图端到端：12/12 通过，0 warning，0 fail；输入为内置图片生成得到的 12 件品红色键道具整图，不使用 Layout Guide 进入诊断。
- 视觉检查：候选编号/严重级别预览、修正前后差异图和最终 Contact Sheet 均通过；12 件资源轮廓完整、透明背景正确、无可见品红残边或误切。
- 错误矩阵：越界、重叠、可见裁断和非连续编号均在正式输出前阻断，并返回精确 JSON 路径与修正建议。
- 安装态 `unittest`：49/49 通过。
- Skill 源码与安装副本：33 个正式文件哈希一致，0 差异。

### 兼容性

- 不新增依赖、API Key、OpenCV、桌面 GUI 或 Unity 自动导入。
- bbox 修正 schema 从 v1 升级为 v2，仅追加 review、阈值和原始检测框字段；现有核心字段与 CLI 参数不变。
- 更严格的预检会让无效修正在正式写文件前失败；成功导出新增两项 QA 产物，不改变 Manifest 资源字段。

## 2026-07-16｜v0.5.0｜P2 碎片策略真实校准

提交：随本记录同提交。

### 目标

用面板、按钮、装备链条和技能硬边火花真实生产样本校准碎片合并距离，防止大面板比例阈值过宽，同时保留合法分离装饰。

### 主要改动

- 使用内置 `imagegen` 生成 4 张校准 Sheet、16 件真实资源，覆盖尖角、链条、悬挂件、独立符文和硬边火花。
- 将统一 `15%` 合并比例改为分类级比例与像素上限：Panel `0.06/64px`、Button `0.06/48px`、常规128图标 `0.12/48px`、Skill `0.15/96px`、Effect `0.18/128px`。
- Manifest 写入实际 `fragment_policy`；资源记录新增 `accepted_detached_count`。
- 远离组件默认继续 warning；新增显式 `allow-small`，仅在绝对像素与锚点面积比例双重限制内保留并降为 info，不删除组件、不放行显著第二主体。
- 批量请求支持透传 `fragment_policy`；同步 Skill、参考契约、README、AGENTS 和测试。
- 项目版本从 `0.4.0` 升级为 `0.5.0`。

### 验证

- P2 真实生产回归：16/16 通过，0 warning，0 fail。
- Contact Sheet：人工检查通过；链条、尖角、悬挂件、符文和硬边火花完整，无误切、错误合并或截断。
- 旧三风格真实回归：36/36 通过，0 warning，0 fail。
- 源码 `unittest`：45/45 通过。
- 安装态 `unittest`：45/45 通过。
- Skill 源码与安装副本：33 个正式文件哈希一致，0 差异。

### 兼容性

- 不新增依赖、API Key、OpenCV、桌面 GUI 或 Unity 自动导入。
- 大型 Panel/Button 的远距离噪点更容易被识别为 warning；Skill/Effect 保留更宽的合法硬边碎片范围。
- 新字段均为追加；旧请求无需修改。明确需要接受小型远离装饰时才配置 `fragment_policy`。

## 2026-07-16｜v0.4.0｜三风格真实生产回归与跨色键边缘修复

提交：随本记录同提交。

### 目标

用暗黑金属、明亮卡通、低明度深色三套真实生产 Sheet，覆盖绿色、品红和青色第三色键，修复真实输入暴露的颜色漂白、缩放残色与互补色边缘偏色问题。

### 主要改动

- 使用内置 `imagegen` 生成暗黑金属 Canonical Reference 和 12 件 `Icon_Equip` 生产 Sheet。
- 使用内置 `imagegen` 生成明亮卡通 Canonical Reference 和 12 件 `Icon_Item` 品红色键生产 Sheet。
- 使用内置 `imagegen` 生成低明度深色 Canonical Reference 和 12 件 `Icon_Skill` 青色键生产 Sheet。
- 修复局部前景投影错误覆盖主体内部的问题；远离背景的确定前景保留原始 RGB/Alpha。
- 对背景邻域中符合色键—前景线性混合模型或具有色键通道优势的像素扩展局部前景重建，解决绿色主体叠品红色键时欧氏距离过快变大造成的整圈品红边。
- 稳定前景种子排除色键偏色像素，并降低门槛以覆盖蓝、白、金、绿等合法前景颜色。
- 对无法安全重建、仍接近色键的部分 Alpha 残边执行透明化，并在背景报告记录丢弃像素数量。
- 归一化改用预乘 Alpha 缩放，避免低 Alpha 绿色 RGB 在缩小时重新形成可见绿边。
- QA 新增参数化 `visible-chroma-spill`，拦截不接近纯色键、但在透明边缘形成连续色键通道偏色的像素带。
- 新增复杂纹理内部保持、绿色主体叠品红色键、连续色键偏色拦截和低 Alpha 色键缩放回归测试；同步 Skill、色键契约、README、AGENTS 和 HANDOFF。
- 项目版本从 `0.3.0` 升级为 `0.4.0`。

### 验证

- 暗黑金属端到端：12/12 通过，0 warning，0 fail。
- 明亮卡通端到端：12/12 通过，0 warning，0 fail。
- 低明度深色端到端：12/12 通过，0 warning，0 fail。
- 三份 Contact Sheet：人工检查通过；无漂白、绿边、品红边、青边、误切、截断或孔洞丢失。
- 源码 `unittest`：41/41 通过。
- 安装态 `unittest`：41/41 通过。
- Skill 源码与安装副本：33 个正式文件哈希一致，0 差异。

### 兼容性

- 不新增依赖、API Key、OpenCV、桌面 GUI 或 Unity 自动导入。
- 色键边缘和缩小图标结果会更稳定；背景报告新增丢弃残边与混合投影统计字段，QA 新增 `visible-chroma-spill`，不删除现有字段。

## 2026-07-16｜v0.3.0｜自适应色键、碎片合并与全类别触发验收

提交：随本记录同提交。

### 目标

完成下一优先级：自适应色键阈值诊断、碎片智能合并、金色/白色/深色抗锯齿失败矩阵，以及九类资源的独立 Codex 新任务触发验收。

### 主要改动

- 色键处理统计边框色差分位数，输出建议透明/不透明阈值、置信度、近色主体风险和安全自动采用结论。
- Runner 默认采用安全自适应阈值；低置信度、近色主体或过宽阈值阻止自动处理，保留固定阈值回退参数。
- 净边算法改为使用邻近稳定前景色反推抗锯齿 Alpha 与边缘 RGB；视觉检查发现并修复了原算法对金色、白色、深色边缘的绿边/品红边漏检。
- 切割器按像素距离与主体尺寸比例合并近邻碎片，单独报告远离碎片和显著第二主体，并把计数写入 Manifest。
- 新增金色/白色/深色通过矩阵，以及偏移色键、近色主体、污染边框失败矩阵。
- 九个内部资源类别各有一条静态 eval；9 个独立 Codex 新任务均命中 `game-ui-asset-pipeline`、正确识别类别并给出符合流程的第一动作。
- 明确 `Icon_Effect` 是内部类别，`09_Icon_Effect` 仅是文件名前缀；首次真实验收暴露该混用后已修正规则并复验通过。
- 项目版本从 `0.2.0` 升级为 `0.3.0`，同步更新 Skill、README、参考契约和 AGENTS 制作标准。

### 验证

- 源码测试：38/38 通过。
- 安装态测试：38/38 通过。
- 金色、白色、深色抗锯齿视觉矩阵：3 pass、0 warning、0 fail；边缘无可见绿边或品红边。
- 独立 Codex 新任务触发：9/9 严格通过，证据保存在 `evals/trigger-acceptance-2026-07-16.json`。
- Skill 源码与安装副本：33 个正式文件哈希一致，0 差异。

### 兼容性

- 不需要 API Key，不新增 OpenCV、桌面 GUI、Unity 自动导入或其他第三方依赖。
- Runner 默认色键结果可能因更准确的自适应阈值和净边算法发生改善；需要复现旧阈值时可使用 `--fixed-chroma-thresholds`。
- Manifest 新增碎片统计字段，不删除或改名现有字段。

## 2026-07-16｜桌面 GUI 调整为最低优先级

提交：随本记录同提交。

### 目标

明确项目继续以 Codex-first 流水线为核心，避免在确定性处理和自动验收尚未完全成熟时投入桌面 GUI。

### 主要改动

- AGENTS 明确桌面 GUI 为路线图长期最低优先级。
- 优先使用 JSON 修正、bbox 标注预览和 Contact Sheet 处理人工介入。
- README 增加路线优先级，桌面 GUI 不再列为普通“暂未实现”功能。
- 规定只有核心流程稳定且出现持续高频、无法由轻量方式处理的人工操作时，才重新评估 GUI。

### 验证

- 已检查 AGENTS、README、SKILL 和现有变更记录中的 GUI 边界，规则无冲突。
- 本次仅调整路线规划和制作规范，无运行时代码变化。

### 兼容性

- 不改变 Skill 行为、依赖、命令、输出格式或安装方式。
- GUI 仍属于重大变更；未来重新评估后也必须获得用户明确授权才能开发。

## 2026-07-16｜建立强制提交说明制度

提交：随本记录同提交。

### 目标

让仓库使用者不需要逐个阅读代码 Diff，也能快速确认每次提交解决了什么、如何验证、是否影响兼容性。

### 主要改动

- 新增根目录 `CHANGELOG.md`。
- 回填仓库现有 3 次功能提交的目标、主要改动、验证结果和兼容性说明。
- README 增加变更记录入口。
- AGENTS 增加每次正式功能提交强制同步变更记录的规则和完成条件。

### 验证

- 已根据 Git 历史核对 3 次提交哈希、提交时间、文件统计和当时测试结果。
- 本次只修改文档和项目治理规则，无运行时代码变化。

### 兼容性

- 不改变 Skill 行为、依赖、输出格式和安装方式。

## 2026-07-16｜v0.2.0｜未知 UI 整图诊断与 bbox 修正

提交：[`7cf9f88`](https://github.com/conan2046/CuttingTool/commit/7cf9f88943552099e3f78b3a801de72f5652d8d2)

### 目标

在无图片 API、无桌面 GUI 的前提下，让 Codex 可以诊断没有 Layout Guide 的 UI 整图，并通过 JSON 修正 bbox 后交付透明资源包。

### 主要改动

- 新增 `diagnose_ui_sheet.py`：识别真实 Alpha、纯色背景、RGB 假棋盘格和无法解析的混合背景。
- 自动输出 `input-diagnosis.json`、`bbox-corrections.json` 和 `bbox-preview.png`。
- 新增 `apply_bbox_corrections.py`：使用批准后的 bbox 完成透明化、切割、归一化、Manifest、Contact Sheet 和 QA。
- 未批准修正、假棋盘格、未解析背景、bbox 重叠、越界或裁断前景时禁止交付。
- 新增真实 Alpha、假棋盘格、裁边/连接/残色三类持久 QA 样本。
- 更新 Skill、README、AGENTS、评测用例和未知整图契约。
- 项目版本从 `0.1.0` 升级为 `0.2.0`。

### 验证

- 源码测试：29/29 通过。
- 安装态测试：29/29 通过。
- Alpha 整图端到端：2/2 资源通过，0 warning，0 fail。
- 假棋盘格按预期返回失败并阻止透明资源导出。
- Skill 源码与安装副本：29 个文件哈希一致。

### 兼容性

- 不需要 API Key。
- 不新增桌面 GUI、Unity 导入或第三方依赖。
- 保留原单 Sheet 和批量 Runner 流程。

## 2026-07-16｜批量分类与统一 Runner

提交：[`3005c43`](https://github.com/conan2046/CuttingTool/commit/3005c43b0d2513b5017c6ac683127f6beded3ebe)

### 目标

把原有单分类手动命令链升级为多分类、多 Sheet、可自动汇总交付的 Codex-first 流程。

### 主要改动

- 新增 `prepare_ui_batch.py`，支持多分类请求和超容量自动拆 Sheet。
- 同一语义名的按钮状态组不会跨 Sheet 拆分。
- 新增 `run_ui_pipeline.py`，统一处理原生 Alpha 和色键图片。
- 自动生成总 Manifest、Contact Sheet、QA 报告和 `run-summary.json`。
- 分类编号跨 Sheet 连续；Manifest 补齐来源、输出、留白、对齐和 Pivot 字段。
- 新增批量请求契约和多分类端到端测试。

### 验证

- 测试：22/22 通过。
- 端到端：2 分类、3 Sheet、8/8 资源通过，0 warning，0 fail。
- Skill 源码与安装副本一致。

### 兼容性

- 图片生成仍使用 Codex 内置 `image_gen`，Runner 不调用付费 API。
- 原有单分类调试命令继续可用。

## 2026-07-16｜v0.1.0｜首版 Skill 与确定性核心链路

提交：[`dc5ddd0`](https://github.com/conan2046/CuttingTool/commit/dc5ddd00871912b772f741c2fad52528e930234b)

### 目标

建立 `game-ui-asset-pipeline` 首个可运行版本和 GitHub 源码仓库。

### 主要改动

- 建立 Skill、参考协议、测试、README、AGENTS 和项目依赖声明。
- 实现 Layout Guide、提示词准备、色键转 Alpha、连通域切割、归一化、命名和 Manifest。
- 实现 Contact Sheet 与严格资源包 QA。
- 增加 `.gitignore`，排除 `output/`、`tmp/`、`logs/` 和缓存文件。

### 验证

- 测试：18/18 通过。
- 合成样本完成透明化、切割、归一化、Manifest、Contact Sheet 和 QA。

### 兼容性

- 依赖仅为 Pillow 和 NumPy。
- 不包含桌面 GUI、Unity 自动导入、九宫格推断和复杂半透明特效抠图。

## 后续记录模板

```markdown
## YYYY-MM-DD｜版本或阶段名称

提交：`<历史提交链接>` 或 `随本记录同提交`

### 目标
- 本次要解决的问题。

### 主要改动
- 用户可感知的功能和关键文件。

### 验证
- 测试数量、端到端结果、QA 和视觉检查。

### 兼容性
- 新依赖、迁移要求、行为变化和保留能力。
```
