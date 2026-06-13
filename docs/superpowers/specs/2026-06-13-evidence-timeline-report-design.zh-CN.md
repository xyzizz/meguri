# Evidence Timeline 报告设计

## 背景

Meguri 现在已经会为每次 loop run 写入 `run.json`、`report.md` 和
`index.html`。现有报告能说明命令级别的执行结果，但对 AI 工作流验证来说
仍然太薄。真实使用中，一次 run 可能包含用户输入、模型回复、工具调用、
检查、修复和复测。用户需要按时间顺序查看这条链，并确认结果来自真实工作流，
而不是一段笼统总结。

本设计为生成的 HTML 报告新增结构化 evidence 文件和按 attempt 分组的时间线
视图。能力保持本地优先，报告仍是自包含文件。

## 目标

- 按时间顺序展示完整 AI 验证事件流。
- 按 attempt 分组，让失败、修复、复测链路清楚可追踪。
- 用户点击时间线事件后，可以查看输入、输出、检查结果和关联 artifact。
- 默认对敏感内容脱敏，同时保留本地 artifact 的审计能力。
- 提供 loop replay：一次已捕获的 run 可以用于复现问题，也可以在修复后重试。
- 每个 loop 都有自己的目录，用户可以按 loop 浏览所有历史触发记录。
- 当没有结构化 evidence 时，现有 Meguri loop 和报告仍能正常工作。

## 非目标

- 不让 HTML 页面直接执行本地命令。
- 不要求所有项目脚本都通过 stdout 输出 JSON。
- 不替换现有 `run.json`、`report.md` 或 step/check 报告。
- 本阶段不做实时报告刷新。

## 文件结构和历史记录导航

新的 loop run 使用 loop-first 文件结构：

```text
.meguri/
  index.html
  loops/
    <loop_id>/
      _loop.yaml
      _scripts/
      index.html
      <YYYYMMDD_HHMMSS>/
        run.json
        report.md
        index.html
        replay.json
        evidence/
        artifacts/
        steps/
```

每个 loop 都是一个文件夹。每次触发这个 loop 时，Meguri 在该 loop 文件夹下创建一个
按年月日时分秒命名的文件夹。这个时间文件夹就是该次 loop 的完整运行记录。文件夹名
使用本地开始时间，格式为 `YYYYMMDD_HHMMSS`；如果同一秒内出现多次 run，则追加短后缀，
例如 `20260613_152717_a1b2`。

以 `_` 开头的路径，例如 `_loop.yaml` 和 `_scripts/`，是 loop 定义和辅助文件，
不是历史运行记录。只有时间戳文件夹会被当成 run history。

静态历史页面：

- `.meguri/index.html` 展示所有 loops、每个 loop 的 run 数、最新状态、最新运行时间，
  并链接到每个 loop 的页面。
- `.meguri/loops/<loop_id>/index.html` 展示这个 loop 的所有时间戳 run，按最新优先排序，
  包含状态、耗时、replay status，以及打开每次 run 报告的链接。
- `.meguri/loops/<loop_id>/<YYYYMMDD_HHMMSS>/index.html` 是单次 run 的详细 attempt
  timeline。

用户在前端页面里的浏览路径是：

```text
全部 loops -> 某个 loop 的测试记录 -> 某一次 run 的详细时间线
```

现有 `.meguri/scenarios/*.yaml` loop 文件和 `.meguri/runs/<run_id>/` 报告继续可读，
用于兼容。新 loop 应创建在 `.meguri/loops/<loop_id>/_loop.yaml`，新 run 记录默认写入
loop-local 时间戳目录。

## Evidence 文件协议

验证脚本负责写结构化 evidence 文件。Meguri 在每个 run step 完成后读取这些文件，
并在最终渲染报告前再次读取。

支持两个输入位置：

```text
.meguri/loops/<loop_id>/<YYYYMMDD_HHMMSS>/evidence/*.json
.meguri/evidence/*.json
```

run-local evidence 目录优先。项目级 `.meguri/evidence/` 允许给那些不容易知道
当前 `run_id` 的脚本使用；Meguri 会在生成报告前把符合条件的文件复制到本次 run
目录里再链接。

项目级 evidence 只有在匹配当前 `loop_id` 且修改时间晚于当前 run 开始时间时才可用；
或者它显式声明了当前 `run_id`。这样可以避免把上一次 run 的旧 evidence 混进新报告。

Evidence 文件结构：

```json
{
  "version": 1,
  "run_id": "20260613_152717",
  "loop_id": "agent_multiturn_no_submit",
  "attempts": [
    {
      "id": "attempt_1",
      "title": "Real agent multi-turn verification",
      "status": "pass",
      "events": [
        {
          "id": "turn_1_user",
          "type": "user_input",
          "time": "2026-06-13T15:27:18+08:00",
          "title": "User turn 1",
          "status": "pass",
          "input": "Copy campaign 123 to staging account 456",
          "output": null,
          "checks": [],
          "artifacts": []
        },
        {
          "id": "turn_1_model",
          "type": "model_output",
          "time": "2026-06-13T15:27:24+08:00",
          "title": "Model reply 1",
          "status": "pass",
          "input": "Copy campaign 123 to staging account 456",
          "output": "I found the source campaign and will prepare a safe preview.",
          "checks": [
            {
              "id": "no_submit_commit",
              "status": "pass",
              "message": "submit_commit was not called"
            }
          ],
          "artifacts": [
            {
              "label": "Raw response",
              "path": "evidence/raw_turn_1.json"
            }
          ]
        }
      ]
    }
  ]
}
```

首批事件类型：

```text
user_input
model_output
tool_call
check
repair
rerun
artifact
note
```

未知事件类型不会让报告失败。Meguri 将其作为 neutral 的 `note` 风格事件展示，
并在报告 metadata 中记录 warning。

## 数据模型变化

在 `meguri/core` 下新增 evidence 相关 dataclass 或 typed dictionary：

- `EvidenceBundle`：source file、loop id、attempts。
- `EvidenceAttempt`：id、title、status、有序 events。
- `EvidenceEvent`：id、type、time、title、status、input、output、checks、
  artifacts、metadata。
- `ReplayBundle`：loop id、scenario path、command、project ref、inputs、
  脱敏后的环境摘要。

`RunReport` 新增：

```python
evidence: list[EvidenceBundle]
evidence_warnings: list[str]
replay: dict[str, Any] | None
```

这些字段都是追加字段，现有 `RunReport.to_dict()` 消费方保持兼容。

## Runner 行为

`run_scenario` 执行时，Meguri 应该：

1. 解析 loop id，并创建 loop-local 时间戳 run 目录。
2. 通过配置的 adapter 执行每个 step。
3. 像现在一样保存 stdout、stderr 和 result artifacts。
4. 每个 step 完成后扫描 evidence 输入，并在最终渲染报告前再次扫描。
5. 把符合条件的项目级 evidence 文件复制到当前 run 目录的 `evidence/` 文件夹。
6. 忽略不匹配当前 loop 或当前 run 窗口的项目级 evidence；如果被跳过的文件看起来相关，
   记录 warning。
7. 把有效 evidence 文件解析进 `RunReport.evidence`。
8. 对解析错误、schema 问题和缺失 artifact 记录 warning，而不是让本来有效的 run 失败。
9. 在 run 目录写入 `replay.json`。
10. 有 evidence 时，详细 run HTML 优先使用 evidence 渲染。
11. 重新生成 loop index 页面和 project index 页面。

Meguri 应向脚本暴露 run 目录环境变量：

```text
MEGURI_RUN_ID=<run_id>
MEGURI_LOOP_ID=<loop_id>
MEGURI_RUN_DIR=<absolute loop-local timestamp dir>
MEGURI_ARTIFACT_DIR=<absolute loop-local timestamp dir>
MEGURI_EVIDENCE_DIR=<absolute loop-local timestamp dir>/evidence
```

脚本可以直接把 evidence 写入 run-local evidence 目录。

## HTML 报告设计

每个详细 run 报告保留现有 summary header。核心新增视图是 `Attempt Timeline`。

桌面布局：

```text
Run Summary

Attempt 1: Real agent multi-turn verification        PASS
○──○──○──○──○──○
1  2  3  4  5  6

Attempt 2: Repair and rerun                          PASS
○──○──○──○
1  2  3  4

[timeline area]                         [fixed detail panel]
```

移动端布局中，选中事件的详情展示在时间线下方。

时间线行为：

- 每个 attempt 渲染为一条横向圆点链。
- event 按 `time` 排序；没有 `time` 的 event 保持文件内顺序。
- 默认选中第一个 failed 或 blocked event；如果没有失败或阻塞，则选中第一个 event。
- event 圆点只放短 label 或图标。长文本进入详情面板。
- 详情面板展示 title、event type、time、status、input、output、checks 和 artifact 链接。

状态颜色：

```text
pass      green
fail      red
blocked   amber
warning   yellow
neutral   gray
active    outline/highlight
```

如果没有结构化 evidence，报告降级为当前 step/check/stdout/stderr 视图，并显示：

```text
No structured evidence file found.
```

如果 evidence 文件无法解析，HTML 显示 evidence parse warning，同时继续渲染现有 step 报告。

Loop index 页面比详细 run 页面更简单，展示一个紧凑的历史记录表：

```text
Run time            Status   Replay   Duration   Links
20260613_152717     fail     full     1m 42s     Open / Replay / Retry
20260613_154308     pass     full     1m 11s     Open / Replay
```

Project index 页面按 loop 分组：

```text
Loop                       Runs   Latest status   Latest run
agent_multiturn_no_submit  12     pass            20260613_154308
static_syntax_smoke        4      pass            20260613_151902
```

## 脱敏

报告采用两层脱敏机制。

第一层由 evidence 显式标记：

```json
{
  "output": {
    "text": "Bearer sk-example",
    "redacted": true,
    "redacted_label": "LLM API token"
  }
}
```

HTML 展示为：

```text
[redacted: LLM API token]
```

第二层由 Meguri 在渲染 HTML 前自动脱敏常见 secret 模式：

- Authorization headers。
- API keys 和 bearer tokens。
- Cookies。
- `password`、`passwd`、`secret`、`token`、`api_key` 字段。
- DSN 中的密码片段。

生成的报告默认展示脱敏后的内容。验证脚本写出的 raw local artifacts 仍可能包含原文，
所以报告必须清楚标记 raw artifact 链接。

## Loop Replay

每次 run 写入：

```text
.meguri/loops/<loop_id>/<YYYYMMDD_HHMMSS>/replay.json
```

Replay bundle 结构：

```json
{
  "version": 1,
  "source_run_id": "20260613_152717",
  "loop_id": "agent_multiturn_no_submit",
  "scenario_path": ".meguri/loops/agent_multiturn_no_submit/_loop.yaml",
  "command": ["sh", "-lc", ".venv/bin/python .meguri/loops/agent_multiturn_no_submit/_scripts/verify.py"],
  "project_ref": {
    "git_commit": "abc1234",
    "dirty": true
  },
  "inputs": [
    {
      "source": "evidence",
      "path": "evidence/agent_multiturn.json"
    }
  ],
  "environment": {
    "python": ".venv/bin/python",
    "redacted_env": ["OPENAI_API_KEY", "DATABASE_URL"]
  },
  "replay": {
    "status": "partial",
    "missing": ["LLM credentials", "staging database"]
  }
}
```

Loop replay 是“一键复现”和“修复后重试”背后的同一个动作。HTML 不直接执行本地命令；
它只提供复制按钮，让当前 Codex / Claude Code 会话去执行。

普通 rerun，没有捕获输入时：

```bash
meguri run agent_multiturn_no_submit
```

重放一次已捕获的 loop run：

```bash
meguri run agent_multiturn_no_submit --replay .meguri/loops/agent_multiturn_no_submit/<YYYYMMDD_HHMMSS>/replay.json
```

修复后 retry 时，复制命令保留同一个 replay 输入，并记录它是从哪个 run 重试而来：

```bash
meguri run agent_multiturn_no_submit --replay .meguri/loops/agent_multiturn_no_submit/<YYYYMMDD_HHMMSS>/replay.json --retry-of <run_id>
```

`--replay` 加载 replay bundle，把路径通过 `MEGURI_REPLAY_FILE` 暴露给 loop，
并在新 run 中记录 replay 来源。Meguri 不假装能重建缺失的凭证、外部服务或生产数据。
loop 脚本负责在可行时用 replay bundle 驱动确定性输入。

`--retry-of` 表示新 run 是某个旧 run 在修复后的 retry。新报告应该链接回 source run；
source report 在可用时也应展示 retry command 和后续 run id。这样 loop 链路就是可审计的：

```text
original run -> failed/blocked event -> fix -> retry with same replay bundle -> pass/block
```

Replay status：

```text
full       命令、输入、环境元数据足够支持 rerun
partial    命令和输入存在，但缺少凭证或外部系统
none       没有结构化 evidence 或 replay 入口
```

## Markdown 报告

`report.md` 应保持简洁，只包含：

- Run summary。
- Evidence bundle 数量。
- Attempt 摘要。
- Failed 或 blocked event 摘要。
- Replay command 和 retry command，如果存在。

默认不内联完整对话，避免 Markdown 过长。

## Validate

`meguri validate` 应继续接受现有 pack，并且只在相关时增加 evidence warning：

- 当 scenario metadata 声明支持 evidence，但 sample run 后无法解析 evidence schema 时给 warning。
- 当 evidence 文件存在时，校验其中 artifact path。
- 对未知 event type、同一 attempt 内重复 event id、缺失 attempt id 给 warning。

缺少 evidence 不应导致旧 scenario 校验失败。

## 测试

新增聚焦测试：

- 在 `.meguri/loops/<loop_id>/` 下创建 loop-local 时间戳 run 目录。
- 能解析包含多个 attempt 的有效 evidence 文件。
- event 按 time 排序；没有 time 时保留文件顺序。
- evidence 存在时，HTML 渲染 timeline。
- 渲染 project index 和 loop index 页面，并能链接到历史 run 报告。
- evidence 不存在时，回退到 legacy step view。
- evidence parse warning 不会让报告生成失败。
- 显式 redacted object 和常见 secret pattern 都会被脱敏。
- `replay.json` 写入 source run id、scenario path、command、project ref、inputs 和 replay status。
- HTML 渲染可复制的 replay / post-fix retry command，但不嵌入命令执行能力。

## 已关闭决策

- 时间线粒度是完整事件流，不只是 Meguri step。
- 每个 loop 都是一个文件夹；每次触发在该 loop 下创建时间戳 run 文件夹。
- Evidence 从文件收集，不从 stdout 收集。
- Attempts 分组展示，不做一条全局扁平时间线。
- 事件详情在桌面端使用右侧固定详情面板。
- 详情展示 input/output、checks 和 artifact links。
- 脱敏同时支持脚本显式标记和 Meguri 自动 secret masking。
- 一键复现的本质是 loop replay：可复制的 replay / retry command 加 replay bundle，
  不是 HTML 直接执行命令。
