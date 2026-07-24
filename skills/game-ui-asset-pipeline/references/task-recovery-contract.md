# Codex 任务断线恢复契约

## 适用错误

当任务界面实际出现：

```text
stream disconnected before completion: websocket closed by server before response.completed
```

不要在旧任务继续发送消息。若当前仍有可执行控制权，立即停止旧任务，并只终止该任务明确登记的活动命令；不得按进程名批量结束无关程序。

## 新任务恢复

创建一个新 Codex 任务，首条消息必须包含：

- 原任务 ID。
- “继续之前任务未完成内容”。
- 项目绝对路径。
- 恢复检查点、运行目录和最新交付摘要路径。
- “读取和检查改为串行轻量操作，不修改既有项目文件，先核对状态再续行”。

新任务先读取项目 `HANDOFF.md`、运行目录 `qa/pipeline-state.json`、`qa/operation-heartbeat.json`、`qa/delivery-summary.json`、`jobs.json` 和 Git 状态；先核对输入 SHA-256、最近安全阶段与心跳状态，再确认没有仍在写入的旧命令，从 `resume_from` 指定阶段恢复。

若断线发生在图片生成波次中，新任务核对现有输出后，首次续跑编排器时增加 `--generation-event disconnect`，只记录一次并降低后续有效并发。已经由旧任务或外部监督器记录过该事件时不得重复传入。

## 能力边界

WebSocket 已关闭后，断线任务本身不再获得执行机会，因此 Skill 和本地 Python 无法保证在错误发生后自行创建新任务或杀掉旧命令。只有 Codex 桌面或外部监督任务提供断线回调时，才能全自动执行上述切换。

在产品回调可用前，采用以下可执行降级：

- 每次进入图片生成或 Runner 前更新 `qa/delivery-summary.json`、`qa/pipeline-state.json`、`qa/operation-heartbeat.json`、`jobs.json` 和项目 `HANDOFF.md`。
- 长任务只运行一个；文件读取、Git 状态和摘要检查串行且轻量。
- 新任务收到原任务 ID 后按上述顺序恢复，不重新生成已经存在且哈希有效的输入。
