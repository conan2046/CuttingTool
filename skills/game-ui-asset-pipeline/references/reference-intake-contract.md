# 参考图接收与验收契约

## 目的

首次创建项目目录后等待用户放置参考图。参考图合格后由 Codex 自动分析并回写说明，再进行一次性界面确认；用户不填写 Markdown。

## 状态流程

```text
等待项目名
→ 初始化 references 目录
→ awaiting-user-references
→ deterministic-check
→ visual-review
→ reference-analysis
→ layout-elements-size-confirmation
→ 自动回写说明与资源清单
→ 自动生成与交付
```

任何检查失败都返回 `awaiting-user-references`，不得跳过、降级为 warning 后继续生成。

## 用户放置说明

初始化后明确返回绝对目录：

```text
D:\CuttingTool\input\<project-id>\references\
```

要求用户：

- 至少放一张 PNG、JPG、JPEG 或 WebP 静态图片。
- 推荐一张 `canonical-style.png` 作为最高优先级主参考图。
- 辅助图使用 `reference-01-material.png`、`reference-02-color.png` 等命名。
- 放置完成后回复“已放好”；这是参考图尚未进入工作区时的必要暂停。

## 自动检查

运行 `validate_ui_references.py`，必须检查：

- `reference-notes.md` 存在。
- 至少一张参考图。
- 仅接受 PNG、JPG、JPEG、WebP。
- 图片可解码且不是动画。
- 宽高均不少于 256 像素。
- 主参考图最多一张，命名为 `canonical-style.<ext>`。
- 辅助图命名为 `reference-<两位序号>-<英文语义>.<ext>`。
- 不允许内容哈希完全相同的重复图片。

失败时输出结构化问题、文件和修复建议，并返回非零退出码。

## 视觉检查

自动检查通过后，使用 `view_image` 逐张检查：

- 图片清晰，无严重模糊、压缩块或低分辨率放大。
- 关键 UI 主体完整，没有影响判断的裁切或大面积遮挡。
- 没有可能被模型复制的明显水印、Logo、大段说明文字或可见引导网格。
- 主参考图能代表目标整体风格、材质、描边、配色、光照和观察角度。
- 自动推断每张辅助图的单一职责和排除项，并写入结构化分析；只有存在多种同等合理解释且会改变产物时才询问。
- 多张图片没有互相冲突的主风格；冲突时要求重新选择主参考图或拆成不同项目。

普通游戏截图可以作为风格参考，但不得把它当作可直接切割的 Production Asset Sheet。

## 失败反馈

逐项返回：

```text
文件：reference-02-color.png
问题：图片只有 128×128，无法稳定判断配色和材质。
处理：请替换为宽高至少 256 像素的清晰图片，然后回复“已重新放好”。
```

用户替换后重新运行全部自动检查并再次逐图查看。不要只复查上一项失败，也不要保留旧的通过结论。

## 通过条件

只有同时满足以下条件才标记 `references-approved`：

- 自动检查 `ok=true`。
- 每张图片均已实际查看。
- 主参考图已确认，或明确需要使用辅助图先生成主风格基准。
- 辅助图职责和优先级无歧义。
- 没有未处理的冲突、水印、清晰度或完整性问题。

通过后不要让用户填写 `reference-notes.md`。先汇总主参考布局、元素一致性判断和每个界面目标尺寸，要求用户一次性确认；确认后按 `project-intake-and-reuse-contract.md` 自动更新说明、建立资源清单并继续生成。
