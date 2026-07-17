# 本地输入目录

第一次使用 `game-ui-asset-pipeline` 时，Skill 会询问项目名并自动创建项目目录、`references/` 和 `reference-notes.md`。不需要手工建目录。除本说明外，`input/` 下的文件默认被 Git 忽略，避免私人素材误提交。

`reference-notes.md` 默认自带填写注释、可见示例和占位表格；按示例替换项目需求与每张参考图的作用即可。

创建完成后，Skill 会返回准确目录并暂停。把图片放好后回复“已放好”；Skill 将自动检查并逐张查看。不合格时需要按提示替换，全部通过后才进入资源清单和生成。

推荐结构：

```text
input/
└─ my-project/
   └─ references/
      ├─ reference-notes.md
      ├─ canonical-style.png
      ├─ reference-01-material.png
      ├─ reference-02-color.png
      └─ reference-03-shape.png
```

规则：

- 只选 1 张图作为 `canonical-style`；它决定整体风格，优先级最高。
- 其他图片按 `reference-01`、`reference-02` 顺序排列，并在需求中说明各自只参考什么。
- 风格互相冲突的图片不要放在同一次任务中；拆成不同项目或不同运行目录。
- 推荐 PNG、JPG 或 WebP；不要直接使用 PSD、压缩包或带密码文件。
- 推荐英文文件名、无空格，避免脚本和外部工具处理路径时产生歧义。
- 不要把自己的图片放进 `skills/game-ui-asset-pipeline/references/`；那里存放的是 Skill 协议文档。

完整操作见根目录 [BEGINNER_GUIDE.md](../BEGINNER_GUIDE.md)。
