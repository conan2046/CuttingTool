# CuttingTool

> 当前版本：`v0.15.0`｜Python `>=3.11`｜Unity `2022.3.x` + UGUI

游戏 UI 位图资源生产与拆分工具。当前实现 `game-ui-asset-pipeline` Skill 的批量可执行核心链路：

```text
多分类任务规格
→ 自动拆分 Sheet 与 Layout Guide
→ GPT Image 资源 Sheet／RGB＋Alpha Matte 双图
→ 一键识别 Alpha、Matte 或色键并切割
→ 尺寸归一化与总 Manifest
→ Contact Sheet、严格 QA、运行摘要
→ Unity Sprite/九宫格配置与可交互 Prefab
```

项目制作标准见 [AGENTS.md](AGENTS.md)，每次正式功能提交见 [CHANGELOG.md](CHANGELOG.md)。

第一次使用请直接阅读 [新手操作指南](BEGINNER_GUIDE.md)。Skill 会先取得项目名并创建参考图目录；放图后由 Codex 自动完善 `reference-notes.md`，用户只需一次性确认界面布局、元素一致性和像素尺寸。

## 版本演进

| 版本 | 已完成能力 |
|---|---|
| `v0.1–v0.4` | 九类 UI 资源生成、色键透明化、切割归一化、Manifest/Contact Sheet/QA、未知整图诊断、自适应色键与三风格真实回归 |
| `v0.5–v0.9` | 分类碎片策略、bbox 人工校正、复杂边缘失败矩阵、原生 Alpha 来源证明、GPT Image 2 RGB＋Alpha Matte 双图链路 |
| `v0.10.x` | 自然语言一键编排、缺图续跑、交付摘要、跨风格 Matte 回归、项目初始化与参考图强制验收 |
| `v0.11.0` | 自动需求接收、首界面完整产出、后续界面按语义复用、从中间阶段安全起跑 |
| `v0.12.x` | Unity Sprite/Border/PPU、Image/Button Prefab、Preview Scene、真实 HUD、Layout Group、Scroll View、低 Alpha 外溢与九宫格安全区 |
| `v0.13.x` | Run/Job/Asset 质量评分、候选哈希去重、单原因定向重生成、跨 Sheet 风格一致性、Panel/Button 内外双重九宫格门禁、Unity `_Project` 目录规范 |
| `v0.14.x` | 单次多界面需求、自适应图片并发 3、生成前内容策略、逐图快速源门禁、全局额外生图预算、Unity 多 Screen、子 Prefab 组合与按钮互斥视图切换 |
| `v0.15.0` | P0/P1/P2 生产优化：风险资源优先、动态重试预算、契约感知缓存、九宫格快速门禁、自动色键预检、目录隔离、状态账本和运行心跳 |

完整逐版本记录见 [CHANGELOG.md](CHANGELOG.md)。

## v0.15.0 最新验收

- 生成队列先处理 Panel、Button、Icon_Status；高风险波次通过快速源门禁后才解锁普通图标。
- Panel/Button 源图在完整 Runner 前检查九宫格四边中间 60%；源门禁缓存同时绑定图片、请求、Layout、透明模式和门禁版本。
- 自动色键根据结构化主体颜色声明在绿、品红、青色中选择；显式冲突在图片生成前失败。
- 未显式配置预算时，为 Panel、Button、色键风险图标组各预留重试，并增加一次全局兜底，最高 5。
- 新任务使用 `generated/current/`、`.local/backups/`、`reused-staging/`、`final/` 四区隔离；污染活动目录会在 Runner 前阻断。
- `qa/pipeline-state.json` 保存安全恢复阶段和必需输入 SHA-256；`qa/operation-heartbeat.json` 标记 Runner 的运行、完成或中断状态。
- Unity 布局结构在生图前校验，可提前拦截 LayoutGroup `spacing` 类型等配置错误。
- 源码与 Codex 安装态全量 `unittest` 均为 157/157；74 个正式 Skill 文件 SHA-256 差异 0。

## v0.14.8 最新验收

- Panel 未显式覆写时，Unity 九宫格 Border 固定为 `[left,bottom,right,top] = [50,50,50,50]`。
- `nine_slice_overrides` 仍优先；Button 保持自动推断，不受 Panel 默认值影响。
- Panel 源图宽或高不大于 `100px` 时会因无法保留中心拉伸区而在 Unity 预检阶段失败。
- 真实五界面重导的两张 Panel 均为四边 50、来源 `panel-default-50`；Unity 报告 49 Sprite、5 Screen、0 issue。
- 源码与 Codex 安装态全量 `unittest` 均为 150/150；74 个正式 Skill 文件 SHA-256 差异 0。

## v0.14.7 最新验收

- Panel 按四边/四角设计键 `frame_style` 去重；同一设计只生成一次，默认 `1×1` Job、最终透明资源 `200×200`。
- 不再为界面宽高或长宽比生成 Panel 变体；五界面共用同一个通用 Panel，Unity 使用 Sliced 九宫格适配。
- 本批仅保留通用外框与边框设计不同的背包格两种 Panel，二者均已归一化为 `200×200`，未追加图片生成调用。
- `xiuxian-ui-five-functions-v0144` 收敛为 42 个本批资源＋7 个复用资源，共 49 Sprite；正式 QA 49/49 通过、0 warning、0 fail。
- 五个静态 Screen 的 Prefab、Preview Scene、Preview PNG 均已导出；导入报告 49 Sprite、5 Screen、0 单资源 Prefab、0 issue，移除 296 个临时 Binding。
- 源码与 Codex 安装态全量 `unittest` 均为 149/149；74 个正式 Skill 文件 SHA-256 差异 0，其中 Panel 复用、批处理和 Unity 导出定向回归 38/38。

## v0.14.6 最新验收

- Panel/Button 仍严格阻断高对比图案进入四边中间 60%；仅对低对比、低梯度材质变化放宽误报，不允许用扩大 Border 掩盖装饰。
- `xiuxian-ui-five-functions-v0144` 最终为 45 个新资源＋7 个复用装备资源，共 52 Sprite；正式 QA 52/52 通过、0 warning、0 fail。
- 五个 1920×1080 Screen 均已生成 Prefab、Preview Scene 和真实 Unity PNG；`asset_prefab_count=0`，共移除 296 个临时 Binding。
- Unity 批预览改为 1:1 WorldSpace、纹理/UGUI 强制就绪、四帧合成；逐 Screen 隔离日志保留在运行目录。
- 源码全量 `unittest` 为 `146/146`。

## v0.14.5 最新验收

- Panel/Button 中间 60% 拉伸带存在空列或空行时，不再触发 `IndexError`；报告 `gap_positions` 并以九宫格 hard fail 阻断。
- 风格评分缩略图中没有达到最低可见 Alpha 的像素时，不再抛出未处理异常；报告 `style-profile-empty-visible-pixels`，并携带 `asset_id`、`job_id` 和文件路径。
- 真实五界面批次已验证两个异常均能正常落入 QA；当前美术候选仍有 21 个 hard fail，未进入 Unity，详见 `output/xiuxian-ui-five-functions-v0144/qa/qa-report.json`。
- 源码与 Codex 安装态全量 `unittest` 各 `144/144` 通过；74 个正式 Skill 文件 SHA-256 差异 0。

## v0.14.4 最新验收

- Screen Prefab 在布局、ScrollRect、PrefabInstance 和 Toggle 接线完成后，递归移除全部 `GameUIElementBinding` 临时组件。
- 保留 `GameUIViewSwitcher`、Button、Layout Group、ScrollRect、TMP 等实际运行组件，不破坏按钮切换。
- Unity 导入报告新增 `removed_helper_component_count`，可追溯每批清理数量。
- `CharacterInventory` 真实重导：4 个 Screen Prefab 共清理 125 个辅助组件，最终 Binding 残留 0；两按钮切换、默认态和恢复态全部通过。

## v0.14.3 验收

- 独立 Production Sheet 默认最多并发 3 个；Panel、Button、Icon_Status 等高风险类别同波最多 2 个，低风险 Job 可补足第 3 个槽位。
- Alpha Matte、原生来源侧车和所有重试保持独占串行；每个 Production Sheet 到达后立即执行快速源门禁。
- 限流、超时或断线会持久降级 `3→2→1`，状态记录在 `qa/generation-runtime.json`。
- 全局额外图片调用预算仍默认 1；质量分不覆盖任何硬 `fail`。

## v0.14.2 验收

- 背包/商店可用 `content_policy.item_icons=empty-slots|runtime-data` 排除无须生成的道具 Icon。
- 绿色色键状态图标首轮 Prompt 强制深蓝封闭底板、银白隔离边并禁止绿色反光。
- 每张源图先检查比例、槽位、触边和色键反光；失败不启动完整 Runner。
- 默认全局只追加 1 次生图调用，交付摘要显示首轮调用、总调用预算和 5–8 分钟/次的时长区间。

## v0.14.1 Unity 验收

| 项目 | 结果 |
|---|---:|
| 源码测试 | `131/131` |
| Codex 安装态测试 | `131/131` |
| Skill 源码/安装副本 | 72 个正式文件，SHA-256 `0` 差异 |
| 自适应生成队列 | 独立 Production 最多激活 3 个；Matte、来源侧车和重试仅激活 1 个 |
| 多 Screen Unity 预检 | 2 个 Screen 共享 1 个 Sprite，2 Prefab + 2 Preview Scene 回滚项正确 |
| 真实组合界面 | 48 Sprite / 4 Screen Prefab / 4 Scene / 4 Preview / 0 issue |
| 属性/背包切换 | Unity 实际调用两个 `Button.onClick`，默认、切换、恢复三项均通过 |
| 真实装备强化批次 | 10 pass / 2 warning / 0 fail |
| Panel/Button 九宫格 | 2 个 Panel + 4 个 Button 状态，6 条边带报告全部通过 |
| 多尺寸 Sliced 预览 | 原尺寸、`0.5×`、`1.5×`、`2×` 人工视觉验收通过 |

两条非阻断 warning 分别为 Panel 色键边框存在轻微波动、装备 Sheet 与 Canonical 存在轻微风格漂移；正式资源无 fail，质量分 82，跨 Sheet 风格分 67.10。

## 当前能力

- 创建资源任务运行目录。
- 首次使用时只询问缺失的项目名，并自动初始化本地参考图目录和说明文件；重复调用不覆盖自动区外的用户内容。
- 初始化后等待用户放图；文件级与逐图验收通过后，Codex 自动分析主/辅参考职责并更新 `reference-notes.md`，不要求用户填写模板。
- 将界面布局、UI 元素是否与主参考一致、差异说明和每个界面像素尺寸合并为一次用户确认。
- 确认后自动生成 `ui-resource-inventory.md/json` 与批量请求，并连续执行到最终美术资源交付；`awaiting-generation` 仅是内部状态。
- 首个界面全部产出；后续界面按类别、语义名和状态复用项目既有资源，忽略尺寸，并记录引用 ID、文件和来源运行。
- 支持从需求接收、生成、已有 Sheet 后处理、未知整图、仅 QA 或断点续跑等阶段独立进入。
- 同一请求编排多个资源分类。
- 超过分类容量时自动拆分多张 Sheet，并保持按钮状态组不跨 Sheet。
- 生成确定性 Layout Guide 和 JSON 槽位坐标。
- 生成 GPT Image 2 资源 Sheet 提示词。
- 纯色色键转真实 Alpha。
- 根据边框色差分布自适应诊断并安全采用色键阈值。
- 软 Alpha 边缘和色键污染清理；除软遮罩过渡带外，背景邻域中符合色键—前景混合模型或存在色键通道优势的像素也会进行局部前景重建，无法安全重建的残边会透明化并计数。
- 在已知布局槽位内独立检测和切割资源。
- 全局组件按槽位中心初分后，以各资源主组件边界距离二次纠正跨槽碎片归属，避免宽资源的分离边饰串入相邻资源。
- 智能合并近邻碎片；Panel、Button、128 图标、Skill 和 Effect 使用真实生产校准后的分类级比例与像素上限，避免大面板阈值失控。
- 远离碎片默认 warning；可通过显式 `fragment_policy` 接受受双重尺寸限制的小组件，组件仍保留并记录，不静默删除。
- 保留面板、边框和图标内部透明孔洞。
- 自动识别空槽、槽位边缘接触和额外组件。
- 按目标尺寸、留白和对齐方式归一化；RGBA 缩放使用预乘 Alpha，避免低 Alpha 色键像素在缩小时重新显色。
- `allow_attached_glow=false` 时清理与稳定主体分离的低 Alpha 外溢，并记录移除像素数；紧贴轮廓的抗锯齿仍保留。
- 生成图可在宽高比一致时等比适配请求画布；宽高比不一致时在正式处理前失败，禁止强制拉伸。
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
- 支持 `native-alpha-required` Job：正式输出前验证生成源 RGBA、连续 Alpha、SHA-256、模型/生成方式和“未做背景移除”来源声明。
- 原生 Alpha 分流只清理零 Alpha 隐藏 RGB；生产尺寸和单体缩放均使用预乘 Alpha；Manifest 与运行摘要保留来源证据。
- 原生来源预检失败时只输出结构化 QA 和失败摘要，不创建正式 Manifest 或资源包。
- 支持 `model-matte-derived`：使用 Codex 内置 GPT Image 2 生成纯黑底彩色 Sheet，再基于同一图生成像素对齐的灰度 Matte，不需要 API Key。
- Matte Runner 校验灰度纯度、黑色边框、连续 Alpha、背景平整度、像素覆盖关系和双图 SHA-256；通过后按黑背景合成方程恢复 RGBA。
- Manifest 明确记录 `alpha_origin=gpt-image-2-matte-derived`，不会把 Matte 推导结果冒充模型原生 Alpha。
- P6 一键编排器支持首次准备、精确缺图清单、补图续跑、自动 Runner、完成态复用和统一交付摘要。
- 每次编排写出 `qa/delivery-summary.json` 与 `qa/delivery-summary.md`，集中列出生成方式、Job/输入进度、结果数量、交付路径和人工处理项。
- V0.13 为 Run、Job、Asset 输出 `0–100` 质量分和硬阻断数；分数只排序候选，任何 `fail` 仍禁止交付。
- Runner 失败后自动选择一个最高优先级原因，生成 `qa/regeneration-plan.json/md` 与单原因纠错 Prompt；Codex 只重生成计划指定的失败 Job 输入。
- 候选按 SHA-256 去重，未替换原图不会重复计次；替代候选就绪后自动重跑，默认最多 3 个候选，耗尽后保持硬失败。
- 至少两个生产 Job 且存在 Canonical 时，输出 `qa/style-consistency.json`：综合 Canonical 与 Sheet 间的调色板、平均色、亮度、饱和度和边缘密度；漂移绑定具体 Job 并进入定向重生成。
- 完成态自动把正式 Manifest 合并到 `input/<project-id>/ui-asset-catalog.json`，供后续界面确定性复用。
- 支持 Unity 2022.3 自动导入：Sprite Single、Alpha、布局自适应 PPU、Pivot、无 Mipmap、Clamp、Bilinear 和 Uncompressed。
- Panel 默认使用四边 `50` 的九宫格 Border，Button 自动推断；两者结合全部布局目标尺寸推导 PPU。无有效中心区、Button 低置信或 Border 显示尺寸超限时阻断，支持显式人工覆写。
- 九宫格 Panel/Button 只在四角固定区保留独特装饰，四边中段和中心区保持干净可拉伸；实际多尺寸 Sliced 预览必须检查角饰、连续边线、内部纹理和控件安全边距。
- Panel/Button Prompt 强制禁止四边中点装饰；正式 QA 同时检查四边中间 60% 的外轮廓与内部纹理变化，并在报告中写出 `nine_slice_stretch_bands`。凸起、凹口或独特边带花纹直接硬失败。
- 从已确认的 `unity-layout.json` 生成 Image/Button/TMP Text 界面 Prefab；稳定元素 ID 用于导入期定位，最终 Prefab 清理临时 `GameUIElementBinding`。标题、数值占位和按钮名为明确 Text 节点，支持 CJK 字体来源与动态 TMP Font Asset。单独美术资源不生成 Prefab。Sprite 写入 `Assets/_Project/UI/Sprites/<project-id>`，界面 Prefab 写入 `Assets/_Project/Prefabs/UI/Demo`。
- 背包、任务、商店等可增长有限区域使用 ScrollView、RectMask2D Viewport、Layout Group Content 和 ContentSizeFitter；内容超出规定范围时裁剪并滚动，不允许越界显示。
- 每次 Unity 导出生成预检、导入报告、批处理日志和安全回滚清单。
- Unity 布局支持 RGBA 底色和 Button 四态 SpriteSwap，并自动生成可运行 Preview Scene 与同尺寸 Unity 渲染图。

## 流程提速

- 项目级语义复用：后续界面不重复生成已有按钮、状态图标和通用图标。
- 最靠后阶段起跑：已有 Sheet、透明资源或运行目录时跳过无关前置步骤。
- 单次合并确认：布局、一致性和尺寸一次确认，减少对话往返。
- Job 自动装箱：同类资源按容量拆 Sheet，状态组不跨 Sheet。
- 完成态和有效输入按哈希/现有状态复用，失败只重做问题 Job。
- 独立 Production Sheet 使用最多 3 路自适应并发；Runner、Matte、来源侧车和重试仍为单路重任务。
- 限流、超时或断线按 `3→2→1` 降级，并保留运行目录级恢复状态。

碎片策略真实校准样本位于 `output/p2-fragment-calibration`：面板、按钮、装备、技能共 16 件，包含尖角、链条、悬挂件、独立符文和硬边火花。

当前仍不自动处理：

- Unity 业务事件、本地化文本、数据源、动画状态机和项目专属控制器接线。
- 外部模型原生 Alpha 生成仍为可选能力；只有明确要求源文件直接携带 Alpha 时才需要额外授权。
- 复杂混合展示图的自动语义分类和遮挡内容恢复。

## 路线优先级

1. V0.13：QA 驱动纠错、候选评分、失败 Job 定向重生成、真实 GPT Image 多候选闭环和跨 Sheet 风格评分（已完成）。
2. P6：Codex 自然语言一键编排和稳定交付（已实现）。
3. P6.1：GPT Image 2 RGB＋Matte 跨风格回归（已完成：暗黑幻想、明亮卡通、科幻全息三套真实样本）。
4. P7/P8：Unity 自动导入、Sprite Editor、九宫格和交互 Prefab（已实现）。
5. 下一阶段：积累更多跨品类真实样本，校准风格阈值并扩展人工语义问题的结构化回写。
6. 根据真实生产任务继续优化色键、碎片、JSON 修正、bbox 预览和 Contact Sheet。
7. 桌面 GUI：长期最低优先级。只有前述流程稳定完成，且高频人工操作无法通过现有轻量方式解决时才重新评估。

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

## 推荐：P6 一键编排

Codex 先根据自然语言建立批量请求，格式见 [batch-request-contract.md](skills/game-ui-asset-pipeline/references/batch-request-contract.md)，完整状态机见 [orchestration-contract.md](skills/game-ui-asset-pipeline/references/orchestration-contract.md)。

用户可以一次提出多个界面，例如：

> 一次制作背包、商店和任务三个界面，统一仙侠青玉风格，内部按自适应队列生成资源，最后导入指定 Unity 2022.3 工程并分别生成三个 Screen Prefab。界面尺寸均为 1920×1080，布局按已确认参考图。

Codex 会一次建立完整请求，默认按 `adaptive-parallel` 调度。`qa/generation-queue.json/md` 的 `active_tasks` 是当前可启动波次：独立 Production Sheet 最多 3 个，高风险类别同波最多 2 个；Matte、来源侧车和重试只激活 1 个。用户不需要按 Sheet 重复提需求。

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\orchestrate_ui_delivery.py `
  --request .\batch-request.json `
  --run-dir .\output\dark-fantasy-ui
```

首次调用返回精确缺图清单。按 `jobs.json` 使用内置 `image_gen` 生成并保存到指定路径，补齐后续跑：

```powershell
& $PYTHON .\skills\game-ui-asset-pipeline\scripts\orchestrate_ui_delivery.py `
  --run-dir .\output\dark-fantasy-ui
```

输入齐全后自动执行 Runner，并输出：

```text
final/manifest.json
qa/contact-sheet.png
qa/qa-report.json
qa/run-summary.json
qa/delivery-summary.json
qa/delivery-summary.md
qa/generation-queue.json
qa/generation-queue.md
qa/generation-runtime.json
qa/style-consistency.json
qa/nine-slice-multi-size-preview.json
qa/nine-slice-multi-size-preview.png
```

批量请求声明 `unity_delivery.enabled=true`、目标工程、Editor 和已确认的多 Screen 显式布局后，资源 QA 通过会自动继续 Unity 导出；不需要再单独调用导出命令。Unity 阶段失败时使用 `--force-unity` 续跑，不重新生成图片。

失败进入定向纠错时还会输出 `qa/regeneration-plan.json/md` 与 `prompts/<job-id>-retry-<NN>.md`；只有全部硬阻断清零后才生成正式交付。

复杂半透明任务默认设置 `transparency_mode: "model-matte-derived"`。每个 Job 使用内置 GPT Image 2 生成彩色黑底 Sheet 和同名 `-alpha-matte.png`；不需要 API Key。真实烟雾、玻璃、液体、柔光验收位于 `output/p5-model-matte-real`。

只有明确要求模型原生 Alpha 时才使用 `native-alpha-required` 和来源侧车文件。完整格式见 [native-alpha-contract.md](skills/game-ui-asset-pipeline/references/native-alpha-contract.md)。

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
generated/current/<sheet>.png
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
