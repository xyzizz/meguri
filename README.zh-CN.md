# Meguri

语言：[English](README.md) | 简体中文

面向 Codex 和 Claude Code 的 Agent 验证工作台。

Meguri 是一个放在目标项目里的 AI 工作流。它让当前 Codex / Claude Code
会话可以用稳定的方式理解项目、设计确定性的验证流程、安全运行验证，并留下可审计的报告。

Meguri 不会自己理解你的项目。项目理解、测试流程设计、测试代码编写，仍然由当前终端里的 AI 完成；Meguri 负责提供结构、约束、校验、执行和记录。

## 快速开始

在目标项目里打开 Codex 或 Claude Code，然后粘贴：

```text
请在当前项目安装 Meguri，并继续在当前 AI 会话中完成初始化。

运行：
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash -s -- --init --install-skills

安装完成后，启动 Meguri inspect 工作流，遵循输出的 Meguri 规范，并写入 `.meguri/project-inspect.json` 和 `.meguri/project-brief.md`。

如果项目目标、执行入口、通过标准、凭证、数据准备或禁止的副作用不清楚，请先向我提出具体问题，再编写场景或测试。
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
  scenarios/smoke.yaml
  README.md
.agents/skills/meguri/SKILL.md
.claude/skills/meguri/SKILL.md
.claude/commands/meguri.md
~/.codex/prompts/meguri.md
```

运行记录会保存在目标项目内：

```text
.meguri/runs/<run_id>/
  run.json
  report.md
  index.html
  steps/<step_id>/stdout.txt
  steps/<step_id>/stderr.txt
  steps/<step_id>/result.json
```

HTML 报告是自包含文件，并使用相对链接，因此整个 run 目录可以直接归档或分享。

## AI 工作流

让 Codex / Claude Code 用 Meguri 完成：

| 工作流 | 当前 AI 会做什么 |
| --- | --- |
| Inspect | 阅读项目，遵循 Meguri 规范，并写入 `.meguri/project-inspect.json` 和 `.meguri/project-brief.md`。 |
| Add verification | 在目标、安全执行入口、通过标准都清楚后，设计确定性的验证场景。 |
| Validate | 检查项目 pack、场景、adapter 引用、skill 文件和运行配置。 |
| Run | 执行指定场景，并写入 `run.json`、`report.md` 和 `index.html`。 |
| Report | 打开或总结最新的本地 HTML 报告。 |

```text
示例：
/meguri inspect
$meguri inspect
用 Meguri 增加一个 dry-run 的下单验证流程。
用 Meguri validate 并运行 smoke 场景。
用 Meguri 打开最新报告。
```

新增验证会保持保守。如果请求语义不清、缺少安全执行入口，或缺少确定性的通过标准，Meguri 会要求澄清，并且不写入文件。

## 工作规则

- 让 Codex / Claude Code 读取现有文档、测试、脚本和配置，再编写项目专属的验证场景或辅助测试。
- 除非用户明确批准 execute 模式，否则新场景保持 `dry_run`。
- 不要把 LLM 的自我评价当作通过标准。通过证据应来自命令、结构化输出、日志、产物、截图或文件。
- 在启用 submit、deploy、payment、production writes、external sends 或 data migrations 前，必须先询问。
- 修改后，在安全的情况下校验 Meguri pack，并运行对应的安全场景。

## 开发

在本仓库中运行：

```bash
python3 -m pip install -e '.[dev]'
pytest -q
```
