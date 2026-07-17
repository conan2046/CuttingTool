# Unity 导出契约

## 适用范围

在正式 PNG、Manifest、Contact Sheet 和 QA 已通过后，将静态 UI 资源导入 Unity 2022.3 LTS，配置 Sprite Editor 元数据，并从明确布局生成可交互 Prefab。

## 固定边界

- 支持 Unity `2022.3.x` 与 UGUI。
- 默认导入根目录：`Assets/_Generated/GameUI/<project-id>`。
- 安装嵌入包：`Packages/com.hongda.game-ui-asset-pipeline`。
- Sprite 使用 Single、Alpha Is Transparency、无 Mipmap、Clamp、Bilinear、Uncompressed。默认 PPU 100；Panel/Button 按源图到全部布局目标的最小缩放比自动提高 PPU，确保 Border 的 Unity 单位尺寸不会挤压目标控件。
- Panel/Button 可写九宫格；其他类别 Border 为零。
- 正式界面元素支持 `Image`、`Button`。
- Button 可显式绑定 Hover/Pressed/Disabled SpriteSwap；无 Sprite Image 可使用 RGBA 颜色。
- 每个 Screen 自动生成 Preview Scene 和由 Unity Camera 渲染的同尺寸 PNG，作为视觉验收证据。
- 不自动生成业务事件、本地化文本、数据绑定、动画状态机或项目专属控制器。

## `unity-layout.json` schema v1

```json
{
  "schema_version": 1,
  "nine_slice_overrides": {
    "01_Panel_Main_Default_001": [24, 24, 24, 24]
  },
  "pixels_per_unit_overrides": {
    "01_Panel_Main_Default_001": 320
  },
  "screens": [
    {
      "id": "MainScreen",
      "name": "MainScreen",
      "reference_size": [1920, 1080],
      "elements": [
        {
          "id": "Background",
          "asset_id": "01_Panel_Main_Default_001",
          "kind": "Image",
          "anchor_min": [0.5, 0.5],
          "anchor_max": [0.5, 0.5],
          "pivot": [0.5, 0.5],
          "anchored_position": [0, 0],
          "size": [1200, 760],
          "color": [1, 1, 1, 1],
          "raycast_target": false
        },
        {
          "id": "ConfirmButton",
          "parent_id": "Background",
          "asset_id": "02_Button_Confirm_Normal_001",
          "highlighted_asset_id": "02_Button_Confirm_Hover_002",
          "pressed_asset_id": "02_Button_Confirm_Pressed_003",
          "disabled_asset_id": "02_Button_Confirm_Disabled_004",
          "kind": "Button",
          "anchored_position": [0, -270],
          "size": [300, 96]
        }
      ]
    }
  ]
}
```

约束：

- `asset_id` 必须存在于正式 Manifest。
- `parent_id` 必须引用同一界面中更早声明的元素，禁止循环父子关系。
- 所有二元向量必须包含两个数字，`size` 必须为正数。
- `nine_slice_overrides` 使用 Unity 顺序 `[left,bottom,right,top]`，四值为非负整数，且必须留下非空中心区。
- `pixels_per_unit_overrides` 必须为正数，优先级高于自动推导；未覆写时 Panel/Button 使用全部布局引用中的最小缩放比推导，其他类别使用默认值。
- `color` 使用 `[r,g,b,a]`，每项为 `0..1`；没有 `asset_id` 的 Image 可作为纯色布局层。
- Button 状态资源 ID 可省略；提供任一状态资源时使用 `SpriteSwap`，所有引用必须存在于正式 Manifest。
- 未提供覆写时，Panel/Button 使用 Alpha 与预乘 RGB 的结构变化推断 Border；低置信度禁止导入。Border 经 PPU 换算后的左右/上下固定区必须分别小于每个目标控件的宽/高，否则禁止导入。

## 执行

```powershell
& $PYTHON scripts/export_unity_ui.py `
  --run-dir <absolute-run-dir> `
  --unity-project <absolute-unity-project> `
  --unity-editor <absolute-Unity.exe> `
  --layout <absolute-unity-layout.json>
```

执行顺序：Python 预检与九宫格推断 → 安装嵌入包/复制 PNG → Unity batchmode 配置 importer → 生成资源 Prefab → 生成屏幕 Prefab → 生成 Preview Scene → Unity 渲染预览 PNG → 写报告。

## 验收与回滚

必须检查：

- `unity/unity-preflight.json` 的 `ok=true`。
- `unity/unity-import-report.json` 的 `ok=true`，导入 Sprite/资源 Prefab/界面 Prefab 数量符合计划。
- Unity 日志包含 `GameUIImportComplete`，无编译错误。
- Prefab 位于 `Assets/_Generated/GameUI/<project-id>/Prefabs`。
- Preview Scene 位于 `Assets/_Generated/GameUI/<project-id>/Scenes`，渲染图位于运行目录 `unity/previews`。
- 所有声明四态的 Button 必须为 `SpriteSwap`，且 Highlighted/Pressed/Disabled Sprite 不为空。
- Border 来源记录为 `auto-inferred`、`manual-override` 或 `not-applicable`；PPU 来源记录为 `layout-derived`、`manual-override` 或 `default`。不得把低置信或几何不适配结果写入 Unity。

回滚：

```powershell
& $PYTHON scripts/rollback_unity_export.py `
  --manifest <run-dir>\unity\unity-rollback.json
```

默认只移除本项目生成根目录。加 `--remove-package` 才移除共享嵌入包；执行前确认没有其他生成 UI 依赖该包。
