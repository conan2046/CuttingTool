# P5 内置生成透明能力探测样本

`built-in-checkerboard-rgb.png` 由 2026-07-16 的 Codex 内置 `imagegen` 实测生成。提示词明确要求四类特效的真实透明背景，结果仍为：

- PNG `RGB`，无 Alpha 通道。
- `1254×1254`。
- 棋盘格烘焙进 RGB 像素。

该样本用于固定验证：内置链路不能被标记为 `model-native`，Runner 必须在正式输出前拒绝。

安装态测试使用其左上角 `256×256` 派生裁片 `skills/game-ui-asset-pipeline/tests/fixtures/built-in-checkerboard-rgb-crop.png`，避免测试依赖项目根目录。
