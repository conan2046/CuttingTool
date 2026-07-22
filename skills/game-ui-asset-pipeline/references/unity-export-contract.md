# Unity 导出契约

## 适用范围

在正式 PNG、Manifest、Contact Sheet 和 QA 已通过后，将静态 UI 资源导入 Unity 2022.3 LTS，配置 Sprite Editor 元数据，并从明确布局生成可交互 Prefab。

## 固定边界

- 支持 Unity `2022.3.x` 与 UGUI。
- Unity 内容根目录统一为 `Assets/_Project`。
- Sprite 导入：`Assets/_Project/UI/Sprites/<project-id>`。
- Screen Prefab 导入：`Assets/_Project/Prefabs/UI/Demo`。
- Preview Scene 导入：`Assets/_Project/Scenes/Demo`。
- 单独美术资源只保留 Sprite，不生成资源 Prefab；导入时删除同项目旧的 `Assets/_Generated/GameUI/<project-id>/Prefabs/Assets`。
- 安装嵌入包：`Packages/com.hongda.game-ui-asset-pipeline`。
- Sprite 使用 Single、Alpha Is Transparency、无 Mipmap、Clamp、Bilinear、Uncompressed。默认 PPU 100；Panel/Button 按源图到全部布局目标的最小缩放比自动提高 PPU，确保 Border 的 Unity 单位尺寸不会挤压目标控件。
- Panel/Button 可写九宫格；其他类别 Border 为零。
- 正式界面元素支持 `Image`、`Button`、`Text`（TMP）、`GridLayoutGroup`、`HorizontalLayoutGroup`、`VerticalLayoutGroup`、`ScrollView`、`ScrollViewport`。
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
          "id": "ActionLayout",
          "parent_id": "Background",
          "kind": "HorizontalLayoutGroup",
          "anchored_position": [0, -270],
          "size": [700, 96],
          "spacing": [100, 0],
          "padding": [0, 0, 0, 0],
          "child_alignment": "MiddleCenter",
          "child_control_size": [false, false],
          "child_force_expand": [false, false]
        },
        {
          "id": "ConfirmButton",
          "parent_id": "ActionLayout",
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

- `Image`、`Button` 的非空 `asset_id` 必须存在于正式 Manifest；Layout Group 容器不使用 `asset_id`。
- `Text` 必须提供非空 `text`。导入器先确认 TMP Essential Resources 与项目 TMP 默认字体：默认字体存在时直接使用；不存在时才回退 `Assets/_Project/UI/Fonts/SourceHanSansOLD-Heavy-2.otf` 与 `Assets/_Project/UI/Fonts/TMP_SourceHanSansOLD Heavy SDF.asset`。需要覆写时两条字体路径必须同时提供且位于 `Assets/`。导入器从 source Font 创建或复用 Dynamic TMP Font Asset，并在 SDF 记录的源字体与当前 OTF 不一致时重建，避免 CJK 字符显示方框。Text 可设置 `font_size`、`font_style`、`text_alignment`、`text_overflow`、`enable_auto_sizing`、`font_size_min`、`font_size_max` 与 `color`。
- 工程尚未导入 TMP Essential Resources 时，导入器从已安装的 `com.unity.textmeshpro` 包一次性导入官方 Essential Resources；字体来源应是项目有权使用的可再分发字体文件。
- 每个静态标题、容量/数值占位和 Button 可见文案都必须是明确的 Text 子节点或 Text 元素，不能只保留透明 Image Mount。
- `parent_id` 必须引用同一界面中更早声明的元素，禁止循环父子关系。
- 所有二元向量必须包含两个数字，`size` 必须为正数。
- `nine_slice_overrides` 使用 Unity 顺序 `[left,bottom,right,top]`，四值为非负整数，且必须留下非空中心区。
- `pixels_per_unit_overrides` 必须为正数，优先级高于自动推导；未覆写时 Panel/Button 使用全部布局引用中的最小缩放比推导，其他类别使用默认值。
- `color` 使用 `[r,g,b,a]`，每项为 `0..1`；没有 `asset_id` 的 Image 可作为纯色布局层。
- Button 状态资源 ID 可省略；提供任一状态资源时使用 `SpriteSwap`，所有引用必须存在于正式 Manifest。
- 规则排列必须使用 Layout Group 容器，不逐项写死坐标。Grid 使用 `cell_size`、二维 `spacing`、`constraint`、`constraint_count`、`start_axis`、`start_corner`；Horizontal/Vertical 使用一维 `spacing`、`child_control_size`、`child_force_expand`。三者都支持 Unity 顺序 `[left,right,top,bottom]` 的 `padding` 和 `child_alignment`。
- Layout Group 子节点仍需稳定 `id`/BindingId，并通过 `parent_id` 指向先声明的容器；子节点顺序决定布局顺序。
- 内容数量可能增长且展示范围有限时必须使用 `ScrollView → ScrollViewport → Content`：ScrollView 配置 `viewport_id`、`content_id`、滚动轴和 `movement_type`；ScrollViewport 自动带 `RectMask2D`；Content 使用 Layout Group，并在增长轴配置 `ContentSizeFitter.PreferredSize`。超出 Viewport 的内容必须裁剪，不能泄漏到面板、按钮或相邻区域。
- ScrollView 默认透明且不生成可见滚动条；需要滚动条美术时必须显式提供资源和布局。静态预览至少验证 Content 大于 Viewport 时末端内容被裁剪，Prefab 中 ScrollRect 引用有效。
- 未提供覆写时，Panel/Button 使用 Alpha 与预乘 RGB 的结构变化推断 Border；低置信度禁止导入。Border 经 PPU 换算后的左右/上下固定区必须分别小于每个目标控件的宽/高，否则禁止导入。
- Panel 的四角固定区可以保留独特装饰；水平拉伸带、垂直拉伸带和中心区不得包含星点、莲花、菱形、徽记等独特图案。不能用异常增大的 Border 把边中段装饰包进固定区来规避视觉问题。
- Button、分页、列表和其他子控件必须位于所属 Panel 的安全区内，不得覆盖或越过 Panel 外框固定区；优先作为 Panel 子节点声明，并在渲染验收中检查四边安全距离。

## 执行

```powershell
& $PYTHON scripts/export_unity_ui.py `
  --run-dir <absolute-run-dir> `
  --unity-project <absolute-unity-project> `
  --unity-editor <absolute-Unity.exe> `
  --layout <absolute-unity-layout.json>
```

执行顺序：Python 预检与九宫格推断 → 安装嵌入包/复制 PNG → Unity batchmode 清理旧资源 Prefab → 配置 importer → 生成屏幕 Prefab → 生成 Preview Scene → Unity 渲染预览 PNG → 写报告。

## 验收与回滚

必须检查：

- `unity/unity-preflight.json` 的 `ok=true`。
- `unity/unity-import-report.json` 的 `ok=true`，导入 Sprite/界面 Prefab 数量符合计划，`asset_prefab_count=0`。
- Unity 日志包含 `GameUIImportComplete`，无编译错误。
- Screen Prefab 位于 `Assets/_Project/Prefabs/UI/Demo`。
- Sprite 位于 `Assets/_Project/UI/Sprites/<project-id>`。
- Preview Scene 位于 `Assets/_Project/Scenes/Demo`，渲染图位于运行目录 `unity/previews`。
- 所有声明四态的 Button 必须为 `SpriteSwap`，且 Highlighted/Pressed/Disabled Sprite 不为空。
- 所有 Text 节点须在 Screen Prefab 中使用 `TextMeshProUGUI`，具备非空文本与 TMP Font Asset；中文/日文等 CJK 文案必须在 Unity Preview 中可读，不能显示缺字方块。
- 所有规则排列容器必须在 Screen Prefab 中具有对应 Layout Group 组件；检查约束、行列、间距、子节点数量和 Unity 渲染结果，不能只确认组件存在。
- 所有可增长有限列表必须检查 `ScrollRect.content`、`ScrollRect.viewport`、滚动轴、`RectMask2D`、ContentSizeFitter、Content/Viewport 尺寸关系和裁剪渲染；只添加 GridLayoutGroup 不算通过。
- Border 来源记录为 `auto-inferred`、`manual-override` 或 `not-applicable`；PPU 来源记录为 `layout-derived`、`manual-override` 或 `default`。不得把低置信或几何不适配结果写入 Unity。
- 对所有 Sliced Panel/Button 做实际多尺寸拉伸视觉检查：四角不变形、四边中段连续、内部无独特纹理拉长或重复、Panel 子控件不压住外框。自动 Border 通过不代表美术拉伸带一定可交付。

回滚：

```powershell
& $PYTHON scripts/rollback_unity_export.py `
  --manifest <run-dir>\unity\unity-rollback.json
```

默认删除本项目 Sprite 子目录和本次清单中的 Screen Prefab、Preview Scene，不删除共享的 `Demo`、`Sprites`、`Scenes` 根目录。加 `--remove-package` 才移除共享嵌入包；执行前确认没有其他生成 UI 依赖该包。
