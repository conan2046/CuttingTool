# CuttingTool 会话交接

> 更新时间：2026-07-16  
> 工作目录：`D:\CuttingTool`  
> 仓库：`https://github.com/conan2046/CuttingTool.git`  
> 分支：`main`  
> 已完成功能基线：v0.6.0 P3 轻量人工校正体验

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
```

核心原则：AI 负责视觉，Python 脚本负责确定性处理和验收。桌面 GUI 已明确降为长期最低优先级，不是当前开发目标。

## 3. 已经完成什么

### 3.1 V1 确定性核心链路

- 建立 Skill 标准目录、`SKILL.md`、参考契约、脚本、测试和安装副本。
- 支持九类静态资源：`Panel`、`Button`、`Icon_Nav`、`Icon_Status`、`Icon_General`、`Icon_Item`、`Icon_Equip`、`Icon_Skill`、`Icon_Effect`。
- 支持 Layout Guide、纯色色键转真实 Alpha、连通域检测、切割、归一化、稳定命名和 Manifest。
- 支持 Contact Sheet 和严格 QA。
- 当前依赖只有 Pillow 和 NumPy，不依赖 OpenCV。

### 3.2 批量分类与统一 Runner

- `prepare_ui_batch.py` 支持多分类请求和超容量自动拆 Sheet。
- 同一语义按钮状态组不会跨 Sheet。
- `run_ui_pipeline.py` 统一处理原生 Alpha 和色键 Sheet。
- 自动汇总总 Manifest、Contact Sheet、QA 和 `run-summary.json`。
- 分类编号跨 Sheet 连续。

### 3.3 未知 UI 整图诊断

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

最后一次已验证：

| 项目 | 结果 |
|---|---:|
| 源码 `unittest` | 41/41 通过 |
| 安装态 `unittest` | 41/41 通过 |
| 三风格真实生产回归 | 36 pass / 0 warning / 0 fail |
| 独立 Codex 新任务触发 | 9/9 通过 |
| Skill 源码/安装副本 | 33 个正式文件哈希一致，0 差异 |

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

## 4. 当前卡在哪

没有代码阻塞、测试阻塞或 Git 阻塞。当前是阶段完成后的会话收口点。

已知环境限制：WindowsApps 内的 `codex.exe` 从 PowerShell 直接执行会报“拒绝访问”，所以不能用 `codex exec` 做新任务触发验收。此前已改用 Codex 桌面的独立任务接口完成 9 类验收，不要再浪费时间重复尝试 WindowsApps CLI。

当前尚未实现，但不属于阻塞：

- Unity 自动导入和 Sprite Editor 配置。
- 自动九宫格边界推断。
- 复杂烟雾、玻璃、液体、柔光等原生半透明资源的完全自动抠图。
- 混合展示图的全自动语义分类和遮挡内容恢复。
- 桌面 GUI。

## 5. 下一步计划

推荐按以下顺序继续：

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

### P4：扩充失败矩阵

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

当前用户只有 Codex，没有 API Key。不要切到付费 Image API，不要引入 OpenCV，不要开发 Unity 自动导入，也不要启动桌面 GUI 技术栈，除非用户明确扩大范围。

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

## 8. 最终状态

- `c8666b8` 已推送至 `origin/main`。
- v0.6.0 P3 轻量人工校正体验已完成；最终测试与安装态数量以 CHANGELOG 最新记录为准。
- 下一阶段直接进入 P4 失败矩阵扩充，不重做 P1/P2/P3 样本。
- GUI 继续保持最低优先级。
