# 半透明 Alpha 来源与验收契约

## 适用范围

烟雾、玻璃、液体、柔光等依赖连续半透明层次的 `Icon_Effect` 使用本契约。支持两种来源，必须明确区分：

| 模式 | 来源标记 | 默认生成方式 |
|---|---|---|
| `model-matte-derived` | `gpt-image-2-matte-derived` | Codex 内置 GPT Image 2 |
| `native-alpha-required` | `model-native` | 用户明确授权的原生透明生成路径 |

色键移除、Matte 推导和模型原生 Alpha 是三种不同来源，不得混称。

## GPT Image 2 RGB＋Matte 双图模式

分类请求：

```json
{
  "category": "Icon_Effect",
  "transparency_mode": "model-matte-derived",
  "assets": ["Smoke", "Glass", "Liquid", "SoftGlow"]
}
```

准备器为每个 Job 生成：

```text
prompts/<job-id>.md
prompts/<job-id>-alpha-matte.md
generated/current/<job-id>.png
generated/current/<job-id>-alpha-matte.png
```

### 彩色 Sheet

- 使用内置 GPT Image 2。
- 背景为完全平整的纯黑 RGB。
- 保存烟雾密度、玻璃高光、液体薄膜和柔光衰减的彩色视觉信息。
- 资源数量、顺序、槽位和边距遵守 Layout Guide。

### Alpha Matte

- 把彩色 Sheet 作为编辑目标，不重新独立设计。
- 保持画布、位置、尺寸、轮廓、内部结构和粒子严格对齐。
- 纯黑表示透明、纯白表示不透明、连续灰度表示部分透明。
- 输出只能包含中性灰度，不得出现色偏、棋盘格、标签或背景装饰。

### Runner 预检

正式输出前检查：

- 双图存在且可读取。
- 彩色源图与 Matte 画布尺寸完全一致；尺寸不一致直接失败，不得自动缩放后继续交付。
- Matte 至少包含 8 个 Alpha 等级和 32 个部分透明像素。
- Matte 灰度通道差异 P95 不超过 24。
- Matte 边框 Alpha P95 不超过 24。
- 彩色源图边框色差 P95 不超过 28。
- 彩色前景与 Matte 的包围框 IoU 不低于 0.55。
- 双图可见像素覆盖率均不低于 0.65。
- 记录彩色源图和 Matte 的 SHA-256。

失败时只写 `qa/<job-id>-alpha-matte.json`、总 QA 和运行摘要，不创建正式 Manifest、Contact Sheet 或资源 PNG。

### 合成与保真

已知背景色为 `B`、彩色合成图为 `C`、Matte 为 `α`，直通道前景按以下公式恢复：

```text
F = clamp((C - (1 - α) × B) / max(α, 1/255))
```

- `α=0` 的隐藏 RGB 置零。
- 生产画布缩放和单体归一化使用预乘 Alpha Lanczos。
- Manifest 记录 `alpha_origin`、双图相对路径和双图 SHA-256。
- 最终单体必须仍有部分透明像素和至少 8 个 Alpha 等级。

## 模型原生 Alpha 模式

`native-alpha-required` 只接受生成源直接携带的 RGBA，不得使用色键或 Matte 推导冒充。来源侧车文件至少记录：非空模型、非空生成方式、相对路径、SHA-256、`alpha_origin=model-native` 和 `background_removal_applied=false`。

Runner 验证真实 RGBA、透明像素、部分透明像素、Alpha 等级和侧车哈希。失败时不得创建正式输出。内置 GPT Image 2 当前不直接提供该模式；只有用户明确要求并授权外部透明生成路径时才使用。

## 真实验收矩阵

必须分别覆盖烟雾、玻璃、液体、柔光，并检查：来源标记、透明层次、Matte 对齐、隐藏 RGB、边缘污染、缩放保真、Contact Sheet 视觉质量和失败降级。合成样本只能验证算法，不能替代真实生成验收。
