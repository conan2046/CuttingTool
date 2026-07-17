# P6.1 跨风格 Matte 回归矩阵

三份请求固定使用同一 `2×2` 布局和 `Smoke → Glass → Liquid → SoftGlow` 顺序，只改变视觉语言，用于验证 `model-matte-derived` 在暗黑幻想、明亮卡通和科幻全息风格下的稳定性。

每份请求先交给 `orchestrate_ui_delivery.py` 建立运行目录，再使用内置 GPT Image 2 生成纯黑底 RGB Sheet，并以该 RGB Sheet 为编辑目标生成同尺寸中性灰度 Matte。正式输出由统一 Runner 处理。

## 2026-07-17 验收结果

| 风格 | 运行目录 | 结果 | Matte bbox IoU | Alpha 等级 |
|---|---|---:|---:|---:|
| 暗黑幻想 | `output/p61-dark-fantasy-matte` | 4 pass / 0 warning / 0 fail | 0.9950 | 256 |
| 明亮卡通 | `output/p61-bright-cartoon-matte` | 4 pass / 0 warning / 0 fail | 0.9612 | 256 |
| 科幻全息 | `output/p61-sci-fi-holographic-matte` | 4 pass / 0 warning / 0 fail | 0.9837 | 256 |

- 三套彩色 Sheet 与 Matte 均为 `1254×1254`，Runner 未执行尺寸缩放。
- `alpha_origin` 均为 `gpt-image-2-matte-derived`。
- 三套 Contact Sheet 已人工检查，Smoke、Glass、Liquid、SoftGlow 顺序正确，轮廓完整且风格差异明确。
