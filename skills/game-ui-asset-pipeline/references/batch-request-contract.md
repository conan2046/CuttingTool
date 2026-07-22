# 批量请求契约

## 用途

需要在同一运行目录内生产多个分类，或任一分类可能超过单张 Sheet 容量时，使用批量请求。

## 最小示例

```json
{
  "project_id": "dark-fantasy-ui",
  "style_notes": "Dark medieval fantasy mobile ARPG UI",
  "generation_method": "built-in-imagegen",
  "canonical_style": "D:/references/canonical-ui-style.png",
  "categories": [
    {
      "category": "Button",
      "assets": [
        {"semantic_name": "Confirm", "state": "Normal", "description": "primary action"},
        {"semantic_name": "Confirm", "state": "Pressed", "description": "pressed state"},
        {"semantic_name": "Confirm", "state": "Disabled", "description": "disabled state"}
      ]
    },
    {
      "category": "Icon_Item",
      "subject_uses_green": true,
      "target_size": [128, 128],
      "assets": ["HealthPotion", "ManaPotion", "QuestScroll"]
    }
  ]
}
```

## 顶层字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `project_id` | 是 | 项目标识；写入运行目录和 Manifest |
| `style_notes` | 否 | 所有分类共用的视觉约束 |
| `generation_method` | 否 | 默认 `built-in-imagegen` |
| `canonical_style` | 否 | 已批准风格基准图路径 |
| `references` | 否 | 其他风格参考图路径列表 |
| `retry_policy` | 否 | V0.13 定向重生成策略；`max_attempts` 默认 3，可设为 1–5 |
| `style_consistency` | 否 | 跨 Sheet 风格评分；默认启用，`warning_below=60`、`fail_below=40` |
| `generation_policy` | 否 | 固定为 `sequential-inputs`、图片 Job 最大并发 1；省略时自动写入 |
| `generation_budget` | 否 | 全局图片调用预算；`max_extra_calls` 默认 1，`estimated_minutes_per_call` 默认 `[5,8]` |
| `unity_delivery` | 否 | 资源 QA 通过后自动导出多个 Unity Screen；必须提供确认布局、工程和 Editor |
| `categories` | 是 | 一个或多个分类任务 |

多界面 Unity 请求在顶层增加：

```json
{
  "generation_policy": {
    "mode": "sequential-inputs",
    "max_concurrent_image_jobs": 1
  },
  "unity_delivery": {
    "enabled": true,
    "layout_confirmed": true,
    "unity_project": "D:/CodeProjects/MyGame",
    "unity_editor": "E:/Unity/2022.3/Editor/Unity.exe",
    "layout": {
      "schema_version": 1,
      "screens": [
        {
          "id": "BagScreen",
          "reference_size": [1920, 1080],
          "elements": [
            {"id": "Background", "kind": "Image", "asset_id": "01_Panel_Bag_Default_001", "size": [1200, 760]}
          ]
        },
        {
          "id": "ShopScreen",
          "reference_size": [1920, 1080],
          "elements": [
            {"id": "Background", "kind": "Image", "asset_id": "01_Panel_Shop_Default_002", "size": [1200, 760]}
          ]
        }
      ]
    }
  }
}
```

每个 `elements` 必须是非空显式布局。用户只需一次说明全部界面；Codex 负责建立本结构，内部按队列逐张生成。

## 分类字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `category` | 是 | Skill 支持的标准分类 |
| `assets` | 是 | 语义名字符串或资源对象列表 |
| `canvas` | 否 | `[width, height]`；默认使用分类规格 |
| `grid` | 否 | `[columns, rows]`；决定单张容量 |
| `target_size` | 否 | 最终单体画布；Panel/Button 可留空保持自适应 |
| `alignment` | 否 | `center` 或 `bottom-center` |
| `padding` | 否 | 最终透明安全留白，默认 8 |
| `chroma_key` | 否 | `auto` 或 `#RRGGBB` |
| `subject_uses_green` | 否 | `true` 时自动使用品红色键 |
| `allow_attached_glow` | 否 | 是否允许附着光效；`false` 时清理与稳定主体分离的低 Alpha 外溢并记录移除数量 |
| `fragment_policy` | 否 | 碎片策略覆盖；默认使用分类级校准参数 |
| `transparency_mode` | 否 | `chroma-key`、`model-matte-derived` 或 `native-alpha-required` |

`fragment_policy` 可配置 `merge_distance`、`merge_distance_ratio`、`merge_distance_max`、`major_component_ratio`。远离小组件默认 warning；只有明确设置 `detached_action: "allow-small"`，并同时提供正数 `small_detached_max_pixels` 和 `small_detached_max_anchor_ratio`，才允许保留该组件但不产生 warning。此模式不会删除组件，Manifest 仍记录接受数量。

## 拆 Sheet 规则

- 按 `grid` 容量自动生成 `sheet-01`、`sheet-02`。
- 同一 `semantic_name` 的按钮状态或资源变体必须放在同一张 Sheet。
- 单个状态组超过整张 Sheet 容量时直接失败，不得拆散或缩小硬塞。
- `category_index` 在分类内跨 Sheet 连续，最终文件名使用该编号。
- 每个 Job 生成独立请求、Prompt、Layout Guide、背景报告和切割报告。
- 所有 Job 按 `generation_sequence` 串行推进；同一时刻只有一个图片输入可生成。

## 阶段边界

批量准备器不调用图片 API。它只生成 `jobs.json`、Prompt 和 Layout Guide。使用内置 `image_gen` 完成每个 Job 后，把结果保存到 Job 的 `generated_output`，再运行确定性 Runner。

`native-alpha-required` 不得使用顶层 `generation_method=built-in-imagegen`。外部生成方式必须经用户明确确认，并为每个 Job 同时写出 `generated/<job-id>.provenance.json`；格式见 `native-alpha-contract.md`。

`model-matte-derived` 使用内置 `built-in-imagegen`，每个 Job 必须同时生成 `generated/<job-id>.png` 与 `generated/<job-id>-alpha-matte.png`。Matte 生成时把彩色 Sheet 作为编辑目标，禁止独立重画；Runner 在正式输出前验证双图对齐和连续灰度层次。

自然语言完整交付由 Codex 先建立本契约的请求 JSON，再交给 `orchestrate_ui_delivery.py`。编排器不解析自然语言、不调用图片 API；它负责生成 Job、报告精确缺图、补图续跑和汇总正式交付。状态机和摘要格式见 `orchestration-contract.md`。

V0.13 会把规范化后的 `retry_policy` 写入运行目录 `request.json`。失败候选按内容哈希去重，每轮只纠正一个最高优先级原因；达到候选上限后保持硬失败。

V0.14.2 同时写入 `generation_budget`。首轮调用数按 Production Sheet 和 Alpha Matte 计数；来源侧车不计图片调用。定向重生成在发出计划时消耗全局额外预算，默认只允许整个请求追加 1 次图片调用，不能按 Job 各自追加。

`style_consistency` 必须满足 `0 <= fail_below <= warning_below <= 100`。存在 Canonical 且至少两个 Job 时，Runner 输出 `qa/style-consistency.json`；风格漂移绑定到具体 Job，可触发定向重生成。
