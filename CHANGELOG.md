# CuttingTool 变更记录

记录每次正式功能提交的目标、主要改动、验证结果和兼容性影响。按时间倒序维护；纯格式整理或无功能影响的微小修正可以合并记录。

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
