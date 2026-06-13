# Meguri

语言：[English](README.md) | 简体中文

面向 Codex 和 Claude Code 的 Agent 验证工作台。

Meguri 是一个放在目标项目里的 AI loop 工作流。它让当前 Codex / Claude
Code 会话可以用稳定的方式理解项目、设计确定性的验证闭环、安全运行验证、必要时修复并复测，最后留下可审计的报告。

Meguri 不会自己理解你的项目。项目理解、测试流程设计、测试代码编写，仍然由当前终端里的 AI 完成；Meguri 负责提供结构、约束、校验、执行和记录。

## 快速开始

在目标项目里打开 Codex 或 Claude Code，然后粘贴：

```text
请在当前项目安装 Meguri，并启用 Codex / Claude Code 的 slash 入口。

运行：
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash -s -- --init --install-skills

安装完成后，执行：
/meguri inspect
```

更完整的可复制安装提示词在 [`prompts/install.md`](prompts/install.md)。

完成首次设置后，在 AI 终端里使用 Meguri：

```text
Claude Code: 输入 `/`，搜索 `meguri`，选择 `/meguri`
Codex: 重启/新开会话后输入 `/`，搜索 `meguri`，选择 `prompts:meguri`
Codex 备选：`/skills` -> `meguri`，或 `$meguri inspect`
```

如果新安装的入口没有出现，重启 Codex / Claude Code，或在同一个项目里开启新会话。

## 创建内容

安装器会创建项目工作流文件：

```text
.meguri/
  project.yaml
  loops/smoke/_loop.yaml
  scenarios/smoke.yaml
  README.md
.agents/skills/meguri/SKILL.md
.claude/skills/meguri/SKILL.md
.claude/commands/meguri.md
~/.codex/prompts/meguri.md
```

运行记录会保存在目标项目内：

```text
.meguri/
  index.html
  loops/<loop_id>/
    _loop.yaml
    index.html
    <YYYYMMDD_HHMMSS>/
      timeline.ndjson
      run.json
      report.md
      index.html
      replay.json
      evidence/
      steps/<step_id>/stdout.txt
      steps/<step_id>/stderr.txt
      steps/<step_id>/result.json
```

项目首页展示所有 loops，loop 首页展示该 loop 的历史运行记录，每次 run 的报告都是自包含文件并使用相对链接。`timeline.ndjson` 是追加写入的事件流水，会随着 loop 和每个 step 的推进持续落盘；`run.json`、`report.md`、`index.html` 会在 loop 开始时写入，并在每个 step 开始和完成时刷新；shell step 的 stdout/stderr artifact 会在命令运行中持续更新，所以长时间运行的 loop 不需要等最后一步结束才能检查部分记录。`run.json` 和命令 JSON 输出只保留 stdout/stderr 摘要与字符数，完整流仍保存在 step artifacts。如果 step 的结构化 stdout 声明了运行目录内的 `evidence_json` 或 `evidence_markdown` 文件，Meguri 会把它们提升成 step artifact 链接。Replay metadata 还会记录运行开始前的 git branch、commit、dirty 标记和 dirty 文件列表，方便把报告和当时的项目状态对应起来。旧的 `.meguri/scenarios/*.yaml` loop 文件仍可运行，新的运行记录会写入 `.meguri/loops/<loop_id>/`；既有 `.meguri/runs/<run_id>/` 报告仍然可读。

## Loop

Loop 是 Meguri 的用户主概念。它不是单纯的测试流程，而是一条完整的完成链路：

```text
目标 -> 安全执行 -> 确定性检查 -> 证据 -> 安全时修复 -> 复测 -> 通过 / 阻塞 / 询问
```

新 loop 存储在 `.meguri/loops/<loop_id>/_loop.yaml`。每次运行会创建一个带时间戳的 `.meguri/loops/<loop_id>/<YYYYMMDD_HHMMSS>/` 记录。旧的 `.meguri/scenarios/*.yaml` 文件仍可运行，并会把新记录写入 loop history 结构。

## AI 工作流

让 Codex / Claude Code 用 Meguri 完成：

| 工作流 | 当前 AI 会做什么 |
| --- | --- |
| Inspect | 阅读项目，并创建项目检查产物。 |
| Add loop | 在目标、安全执行入口、通过标准都清楚后，设计确定性的 loop。 |
| List loops | 查看当前项目里有多少个用户 add 过的 loop。 |
| Delete loop | 删除指定命名的用户 loop。 |
| Validate | 检查项目 pack、loop、adapter 引用、skill 文件和运行配置。 |
| Run | 执行指定 loop，写入运行中快照，并持续更新 shell stdout/stderr artifacts。 |
| Report | 打开或总结最新的本地 HTML 报告。 |

```text
示例：
/meguri inspect
$meguri inspect
用 Meguri 增加一个下单 loop。
用 Meguri 查看当前有多少 loop。
用 Meguri 删除 checkout loop。
用 Meguri validate 并运行 smoke loop。
用 Meguri 打开最新报告。
```

新增 loop 会保持保守。如果请求语义不清、缺少安全执行入口，或缺少确定性的通过标准，Meguri 会要求澄清，并且不写入文件。

## 工作规则

- 让 Codex / Claude Code 读取现有文档、测试、脚本和配置，再编写项目专属的 loop 或辅助测试。
- 除非用户明确批准 execute 模式，否则新 loop 保持 `dry_run`。
- 不要把 LLM 的自我评价当作通过标准。通过证据应来自命令、结构化输出、日志、产物、截图或文件。
- 编写 helper/verifier 脚本时，即使异常也要向 `MEGURI_EVIDENCE_DIR` 写结构化 evidence，包含部分输入/输出、错误、traceback 和 artifact 链接。
- 在启用 submit、deploy、payment、production writes、external sends 或 data migrations 前，必须先询问。
- 修改后，在安全的情况下校验 Meguri pack，并运行对应的安全 loop。

## 开发

在本仓库中运行：

```bash
python3 -m pip install -e '.[dev]'
pytest -q
```
