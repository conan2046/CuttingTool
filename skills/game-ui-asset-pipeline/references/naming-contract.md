# 资源命名与 Manifest 契约

## 分类前缀

| 前缀 | 类别 |
|---|---|
| `01` | `Panel` |
| `02` | `Button` |
| `03` | `Icon_Nav` |
| `04` | `Icon_Status` |
| `05` | `Icon_General` |
| `06` | `Icon_Item` |
| `07` | `Icon_Equip` |
| `08` | `Icon_Skill` |
| `09` | `Icon_Effect` |

## 文件名格式

```text
<Prefix>_<Category>_<SemanticName>_<StateOrVariant>_<Index>.png
```

示例：

```text
01_Panel_Main_Default_001.png
02_Button_Confirm_Normal_001.png
02_Button_Confirm_Pressed_001.png
06_Icon_Item_HealthPotion_Default_001.png
08_Icon_Skill_FireSlash_Default_001.png
```

## 命名规则

- `SemanticName` 使用英文 PascalCase。
- 状态使用固定词：`Default`、`Normal`、`Pressed`、`Selected`、`Hover`、`Disabled`。
- 编号为三位数，在同一分类和语义组内稳定递增。
- 不使用空格、中文、括号、井号或临时描述。
- 不覆盖已有文件；默认追加新编号或版本。
- 用户未给语义名时，根据资源清单生成，不从模型图片内容猜测复杂含义。

## Sheet 命名

```text
<category-kebab>-sheet-<NN>.png
```

示例：

```text
icon-item-sheet-01.png
button-sheet-01.png
```

## Manifest 最小字段

```json
{
  "schema_version": 1,
  "project_id": "dark-fantasy-ui",
  "assets": [
    {
      "id": "06_Icon_Item_HealthPotion_Default_001",
      "category": "Icon_Item",
      "semantic_name": "HealthPotion",
      "state": "Default",
      "source_sheet": "generated/icon-item-sheet-01.png",
      "source_index": 1,
      "category_index": 1,
      "source_bbox": [80, 96, 440, 460],
      "output": "final/Icon_Item/06_Icon_Item_HealthPotion_Default_001.png",
      "width": 128,
      "height": 128,
      "padding": 8,
      "alignment": "center",
      "pivot": [0.5, 0.5],
      "chroma_key": "#00FF00",
      "qa": "pass"
    }
  ]
}
```

## Manifest 规则

- 使用 UTF-8 和 `ensure_ascii=false`。
- 使用相对运行目录的路径。
- 字段顺序保持稳定，便于版本比较。
- `source_index` 使用从 1 开始的视觉顺序。
- `category_index` 在同一分类内跨 Sheet 连续，决定文件名末尾编号。
- `source_bbox` 使用 `[left, top, right, bottom]`。
- `source_sheet` 和 `output` 使用相对于运行目录的路径。
- 原生 Alpha 输入的 `chroma_key` 为 `null`；色键输入记录实际使用的色键。
- 每个 Manifest 条目必须对应一个实际文件。
- 每个实际正式输出文件必须存在一个 Manifest 条目。
- `qa` 只能为 `pass`、`warning` 或 `fail`。
- 存在 `fail` 时，资源包不得标记为完成。
