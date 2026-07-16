# Unknown Sheet QA Samples

这些图片是确定性流水线测试输入，不是正式美术资源。

| 文件 | 用途 | 预期结果 |
|---|---|---|
| `alpha-sheet.png` | 标准真实 Alpha Sheet | 检测为 `alpha-sheet`，2 个候选，可批准导出 |
| `checkerboard-presentation.png` | RGB 内烘焙假棋盘格 | 检测为 `checkerboard-presentation`，禁止当作透明资源导出 |
| `failure-overlap-crop-residue.png` | 画布裁边、连接主体和近色键残留 | 诊断产生风险项；未经修正不得进入正式输出 |

样本只使用简单几何图形，便于稳定复现检测和 QA 边界，不用于评价视觉风格。
