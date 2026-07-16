# Sheet 布局契约

## 基本术语

- `canvas`：整张 Sheet 的像素尺寸。
- `grid`：列数×行数。
- `outer_margin`：画布边缘到第一排槽位的距离。
- `gutter`：相邻槽位之间的纯背景间距。
- `slot`：单个资源的布局区域。
- `safe_box`：资源允许占用的最大区域。

## 默认参数

对于 `2048×2048`、`4×4` Sheet：

```json
{
  "canvas": [2048, 2048],
  "grid": [4, 4],
  "outer_margin": 96,
  "gutter": 48,
  "safe_padding": 64,
  "ordering": "row-major"
}
```

对于大型面板 `2×2` Sheet，使用更大的槽位，但至少保留 `96px` 外边距和 `64px` 槽位间隔。

## 布局计算

给定：

```text
usable_width  = canvas_width  - 2 × outer_margin - (columns - 1) × gutter
usable_height = canvas_height - 2 × outer_margin - (rows - 1) × gutter
slot_width    = usable_width / columns
slot_height   = usable_height / rows
```

布局参数应选择能得到整数槽位的位置；出现小数时，通过左右或上下对称余量吸收，不要累积误差。

## Layout Guide 内容

布局引导图可以包含：

- 槽位边界
- 安全区边界
- 中心点
- 对齐基线
- 开发者可读标签

但传给图片模型时必须声明这些都不可出现在结果中。

## 资源放置规则

- 一个槽位只能包含一个主要资源。
- 资源不得跨越 safe box。
- 硬边、尖角和允许保留的紧贴光效都必须位于 safe box 内。
- 空槽只允许出现在用户明确要求少于布局容量时。
- 空槽默认排在 Sheet 尾部，不能夹在有效资源之间。
- 排序固定为从左到右、从上到下。

## 切割策略

### 已知网格优先

正式生产 Sheet 已知行列时，先在每个槽位内独立检测组件，避免两个槽位因背景噪点被错误合并。

### 连通域辅助

在槽位内：

- 删除低于面积阈值的小噪点。
- 合并属于同一主体且距离足够近的碎片。
- 保留封闭边框内部的透明孔洞。
- 紧贴主体的硬边特效可以合并。
- 脱离主体的散点默认标记为警告。

### 边缘失败

任何前景触碰：

- 画布外边缘
- 槽位边缘
- safe box 边缘的禁止区域

都应进入裁切风险检查。确认实际被截断时判定为 `fail`。

## 数量和容量

- `expected_count` 不得大于 `columns × rows`。
- 实际检测数量少于请求数量时判定为 `fail`。
- 实际检测数量多于请求数量时先排除噪点；仍超出则判定为 `fail`。
- 不得静默删除无法解释的额外主体。
