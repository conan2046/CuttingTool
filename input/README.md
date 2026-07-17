# 本地输入目录

第一次使用 `game-ui-asset-pipeline` 时，Skill 会询问项目名并自动创建项目目录、`references/` 和 `reference-notes.md`。不需要手工建目录。除本说明外，`input/` 下的文件默认被 Git 忽略，避免私人素材误提交。

`reference-notes.md` 由 Codex 根据图片自动分析并维护；用户无需填写模板。

创建完成后，Skill 会返回准确目录并暂停。把图片放好后回复“已放好”；Skill 自动检查、逐张查看并回写说明。不合格时按提示替换；通过后只需一次确认布局、元素一致性和界面像素尺寸，之后自动执行到交付。

推荐结构：

```text
input/
└─ my-project/
   ├─ references/
   │  ├─ reference-notes.md
   │  ├─ canonical-style.png
   │  ├─ reference-01-material.png
   │  ├─ reference-02-color.png
   │  └─ reference-03-shape.png
   ├─ reference-analysis.json
   ├─ ui-resource-inventory.md
   ├─ ui-resource-inventory.json
   ├─ batch-request.json
   └─ ui-asset-catalog.json
```

规则：

- 只选 1 张图作为 `canonical-style`；它决定整体风格，优先级最高。
- 其他图片按 `reference-01`、`reference-02` 顺序排列；Codex 自动判断各自只参考什么。
- `ui-asset-catalog.json` 保存已正式交付资源；首个界面全生成，后续界面按类别、语义名和状态复用，尺寸不参与判定。
- 风格互相冲突的图片不要放在同一次任务中；拆成不同项目或不同运行目录。
- 推荐 PNG、JPG 或 WebP；不要直接使用 PSD、压缩包或带密码文件。
- 推荐英文文件名、无空格，避免脚本和外部工具处理路径时产生歧义。
- 不要把自己的图片放进 `skills/game-ui-asset-pipeline/references/`；那里存放的是 Skill 协议文档。

完整操作见根目录 [BEGINNER_GUIDE.md](../BEGINNER_GUIDE.md)。
