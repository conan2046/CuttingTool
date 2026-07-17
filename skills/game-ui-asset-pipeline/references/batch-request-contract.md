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
| `categories` | 是 | 一个或多个分类任务 |

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
| `allow_attached_glow` | 否 | 是否允许紧贴主体的硬边光效 |
| `fragment_policy` | 否 | 碎片策略覆盖；默认使用分类级校准参数 |
| `transparency_mode` | 否 | `chroma-key`、`model-matte-derived` 或 `native-alpha-required` |

`fragment_policy` 可配置 `merge_distance`、`merge_distance_ratio`、`merge_distance_max`、`major_component_ratio`。远离小组件默认 warning；只有明确设置 `detached_action: "allow-small"`，并同时提供正数 `small_detached_max_pixels` 和 `small_detached_max_anchor_ratio`，才允许保留该组件但不产生 warning。此模式不会删除组件，Manifest 仍记录接受数量。

## 拆 Sheet 规则

- 按 `grid` 容量自动生成 `sheet-01`、`sheet-02`。
- 同一 `semantic_name` 的按钮状态或资源变体必须放在同一张 Sheet。
- 单个状态组超过整张 Sheet 容量时直接失败，不得拆散或缩小硬塞。
- `category_index` 在分类内跨 Sheet 连续，最终文件名使用该编号。
- 每个 Job 生成独立请求、Prompt、Layout Guide、背景报告和切割报告。

## 阶段边界

批量准备器不调用图片 API。它只生成 `jobs.json`、Prompt 和 Layout Guide。使用内置 `image_gen` 完成每个 Job 后，把结果保存到 Job 的 `generated_output`，再运行确定性 Runner。

`native-alpha-required` 不得使用顶层 `generation_method=built-in-imagegen`。外部生成方式必须经用户明确确认，并为每个 Job 同时写出 `generated/<job-id>.provenance.json`；格式见 `native-alpha-contract.md`。

`model-matte-derived` 使用内置 `built-in-imagegen`，每个 Job 必须同时生成 `generated/<job-id>.png` 与 `generated/<job-id>-alpha-matte.png`。Matte 生成时把彩色 Sheet 作为编辑目标，禁止独立重画；Runner 在正式输出前验证双图对齐和连续灰度层次。

自然语言完整交付由 Codex 先建立本契约的请求 JSON，再交给 `orchestrate_ui_delivery.py`。编排器不解析自然语言、不调用图片 API；它负责生成 Job、报告精确缺图、补图续跑和汇总正式交付。状态机和摘要格式见 `orchestration-contract.md`。
