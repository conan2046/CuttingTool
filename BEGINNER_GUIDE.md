# CuttingTool 新手操作指南

## 1. 最简单的使用方法

你不需要自己建目录、写命令或 JSON。第一次在 Codex 中提出制作 UI 资源时：

1. 如果需求中没有项目名，Skill 会先询问项目名；建议输入英文、数字和短横线，例如 `xianxia-bag-ui`。
2. Skill 自动创建：

   ```text
   D:\CuttingTool\input\<项目名>\references\reference-notes.md
   ```

3. 你不需要填写 `reference-notes.md`。Skill 告知参考图目录后会暂停；把参考图放进 `references\`，然后回复“已放好”。
4. Skill 检查文件格式、尺寸、命名和重复内容，再逐张查看清晰度、完整性、职责和风格冲突，并自动完善说明文件。
5. Skill 把每个界面的布局、UI 元素是否与主参考一致、不一致差异和像素尺寸合并成一次确认。
6. 你确认后，Skill 自动生成资源清单并直接继续图片生成、切割、QA 和交付，不再要求逐步回复“继续”。

Codex 会负责建立请求、拆分 Sheet、生成图片、切割透明 PNG、运行 QA，并返回最终目录和 Contact Sheet。

V0.13 起，QA 失败时不再只返回错误：系统会生成单原因纠错 Prompt 和失败 Job 替换清单，Codex 自动按计划重生成并续跑。默认最多评估 3 个候选；质量分只用于选择更好的候选，任何 `fail` 都不会被高分放行。

同一批次至少有两张生产 Sheet 且提供 Canonical 时，还会生成 `qa/style-consistency.json`。它能发现某张 Sheet 的配色、材质、描边和光照漂移，但仍必须人工查看 Contact Sheet，确认装备语义、按钮状态和造型是否正确。

如果同时提供 Unity 项目路径，QA 通过后还会自动配置 Sprite、九宫格并从确认过的布局生成 Image/Button Prefab。当前已验证目标为 Unity 2022.3 LTS；业务点击事件、文本本地化和运行时数据仍由项目代码接线。

Unity 布局示例：`D:\CuttingTool\samples\unity-layout-example.json`。正式执行会生成 `unity-preflight.json`、`unity-import-report.json`、Unity 日志和回滚清单；九宫格低置信度时会要求明确 Border 覆写，不会猜测写入。

## 2. 参考图放在哪里

首次初始化后会得到：

```text
D:\CuttingTool\input\xianxia-ui\
└─ references\
   ├─ reference-notes.md
   ├─ canonical-style.png
   ├─ reference-01-material.png
   ├─ reference-02-color.png
   └─ reference-03-icon-shape.png
```

不要放在以下目录：

- `output/`：这里是系统生成的运行结果。
- `skills/game-ui-asset-pipeline/references/`：这里是 Skill 协议文档，不是用户图片目录。
- 系统临时目录：正式任务必须保留可追溯输入。

`input/` 中的私人参考图默认被 Git 忽略，不会随着普通提交上传。

放图要求：PNG/JPG/JPEG/WebP 静态图，宽高均不少于 256 像素；主图命名 `canonical-style`，辅助图命名 `reference-01-material` 等。参考图检查通过前，Skill 不会启动图片生成。

脚本并不强制参考图必须位于 `input/`；绝对路径也可以。但长期使用时统一放在这里最清楚。

## 3. 有多张参考图时怎么处理

### 3.1 先确定唯一主参考图

只能指定 1 张 `canonical-style`，它的优先级最高，用于锁定：

- 整体美术风格
- 材质与描边
- 主色和光照
- 细节密度
- 观察角度
- 缩小后的可读性

如果没有哪张图能代表最终整体风格，先要求 Codex 根据多张参考图生成一张 `canonical-ui-style.png`，确认后再生产正式资源。

### 3.2 其余图片只承担单一辅助作用

推荐命名；图片职责由 Codex 自动分析并写入说明：

| 文件 | 在需求中写明的作用 |
|---|---|
| `reference-01-material.png` | 只参考金属、木材、玉石等材质 |
| `reference-02-color.png` | 只参考配色，不参考造型 |
| `reference-03-icon-shape.png` | 只参考图标轮廓和观察角度 |
| `reference-04-detail.png` | 只参考纹理密度和高光方式 |

如果自动分析存在会改变最终产物的歧义，Codex 才会在一次性界面确认中列出并要求选择。

### 3.3 以下情况必须拆成不同任务

- 一张要写实暗黑，另一张要明亮卡通。
- 同一批资源要求两套不同主色或材质语言。
- 不同产品、不同版本或不同阵营需要各自独立风格。
- 你无法明确哪张图优先。

不要把互相冲突的参考图一起丢给模型后要求“自由融合”，这会降低稳定性和复现性。

## 4. 自然语言需求模板

复制下面内容到 Codex；不知道的字段写“自动判断”。

```text
请使用 game-ui-asset-pipeline 完整制作一套游戏 UI 图片资源。

【项目名称】
例如：xianxia-bag-ui

【游戏类型与使用场景】
例如：国风修仙放置手游，背包和主界面使用，手机端。

【主参考图】
D:\CuttingTool\input\xianxia-bag-ui\references\canonical-style.png
作用：最高优先级，锁定整体风格、材质、描边、配色和光照。

【辅助参考图】
1. D:\CuttingTool\input\xianxia-bag-ui\references\reference-01-material.png
   作用：只参考玉石和鎏金材质，不参考构图。
2. D:\CuttingTool\input\xianxia-bag-ui\references\reference-02-color.png
   作用：只参考青绿、金色配色，不参考造型。

【资源清单】
1. Panel：背包主面板、道具详情面板。
2. Button：确认按钮 Normal/Pressed/Disabled；取消按钮 Normal/Pressed/Disabled。
3. Icon_Item：生命丹、法力丹、突破丹、任务卷轴。
4. Icon_Skill：火球术、冰锥术、御剑术、治疗术。

【尺寸】
Panel、Button：自动判断。
Icon_Item、Icon_Skill：128×128。

【透明要求】
普通面板、按钮、图标：自动选择色键并输出透明 PNG。
烟雾、玻璃、液体、柔光：使用 RGB＋Alpha Matte，不要求模型原生 Alpha。

【特殊要求】
- 不要文字、数字、Logo、水印、棋盘格和可见网格。
- 按钮同一状态组必须保持相同轮廓和尺寸。
- 道具本体不要烘焙品质框、数量和等级。
- 资源不足一张 Sheet 时允许尾部空槽。
- 生成完成后必须运行统一 Runner、QA，并人工检查 Contact Sheet。

【执行方式】
先检查参考图和需求；如主风格不明确，先生成风格基准图让我确认。
主风格明确后，自动完成请求拆分、图片生成、断点续跑、切割、透明化、命名和交付。
最终返回资源目录、Manifest、Contact Sheet、QA 报告，以及 pass/warning/fail 数量。
```

## 5. 极简需求模板

资源少、风格明确时可以只发：

```text
使用 game-ui-asset-pipeline 制作资源。
项目：xianxia-item-icons
主参考图：D:\CuttingTool\input\xianxia-item-icons\references\canonical-style.png
辅助图：reference-01 只参考材质；reference-02 只参考配色。
资源：Icon_Item，生命丹、法力丹、突破丹、任务卷轴，共 4 个。
目标尺寸：128×128。
要求：无文字、无品质框，输出透明 PNG，完成 Runner、QA 和 Contact Sheet 检查。
```

## 6. 可运行 JSON 示例

如果你希望直接准备请求文件，可复制：

```text
D:\CuttingTool\samples\ui-request-example.json
```

关键字段：

```json
{
  "project_id": "xianxia-item-icons",
  "style_notes": "国风修仙手游，青玉与鎏金材质，正面视角，移动端清晰可读",
  "generation_method": "built-in-imagegen",
  "retry_policy": {"max_attempts": 3},
  "canonical_style": "D:/CuttingTool/input/xianxia-item-icons/references/canonical-style.png",
  "references": [
    "D:/CuttingTool/input/xianxia-item-icons/references/reference-01-material.png",
    "D:/CuttingTool/input/xianxia-item-icons/references/reference-02-color.png"
  ],
  "categories": [
    {
      "category": "Icon_Item",
      "target_size": [128, 128],
      "assets": ["HealthPill", "ManaPill", "BreakthroughPill", "QuestScroll"]
    }
  ]
}
```

新手建议直接发自然语言需求，由 Codex 生成 JSON；只有需要保存、复用或批量修改请求时再手工维护 JSON。

## 7. 当前支持的资源类别

| 内部类别 | 用途 | 默认单体尺寸 |
|---|---|---:|
| `Panel` | 面板、边框 | 保持比例 |
| `Button` | 无文字按钮及状态 | 按请求 |
| `Icon_Nav` | 导航图标 | 128×128 |
| `Icon_Status` | 货币、体力、生命等状态图标 | 128×128 |
| `Icon_General` | 通用功能图标 | 128×128 |
| `Icon_Item` | 道具图标 | 128×128 |
| `Icon_Equip` | 装备图标 | 128×128 |
| `Icon_Skill` | 技能图标 | 128×128 |
| `Icon_Effect` | 简单特效或半透明特效 | 256×256 |

请求中的 `category` 必须使用上表英文内部类别，不要写 `01_Panel`、`09_Icon_Effect` 等文件名前缀。

## 8. 透明模式怎么选

| 资源 | 推荐模式 | 是否需要 API Key |
|---|---|---|
| 面板、按钮、普通图标、硬边道具 | `chroma-key` | 否 |
| 烟雾、玻璃、液体、柔光 | `model-matte-derived` | 否 |
| 明确要求生成源直接携带原生 Alpha | `native-alpha-required` | 需要另行确认生成路径 |

不知道时写“自动判断”。当前默认不使用付费 API，也不会把 Matte 推导 Alpha 冒充模型原生 Alpha。

## 9. 任务完成后看什么

运行目录位于：

```text
D:\CuttingTool\output\<项目名>\
```

优先检查：

1. `qa/contact-sheet.png`：人工查看数量、风格、轮廓、透明边缘和错误拆分。
2. `qa/delivery-summary.md`：查看当前状态、结果数量和下一步动作。
3. `qa/qa-report.json`：检查 `fail_count` 是否为 0。
4. `qa/style-consistency.json`：检查总分、逐 Job 分数和 `cross-sheet-style-drift`。
4. `final/manifest.json`：资源清单、来源、尺寸和输出路径。
5. `final/<Category>/`：最终透明 PNG。

只有 `fail=0` 且 Contact Sheet 人工检查通过，资源包才算完成。

## 10. 常见错误

- 把 UI 截图中的遮挡元素当作可无损拆分素材：不可行，缺失部分无法恢复。
- 把烘焙棋盘格当作透明背景：不可行，必须重新生成纯色色键图或提供真实 Alpha。
- 主参考图放多张且不写优先级：会造成风格漂移。
- 把不同类别强塞在同一张正式 Sheet：系统会按类别拆 Job。
- 在按钮图片中生成文字：文字应由游戏运行时显示。
- 把道具主体和品质框烘焙在一起：默认应分离，便于运行时组合。
- 直接查看单张 PNG 就认为完成：必须同时看 Contact Sheet 和 QA。
