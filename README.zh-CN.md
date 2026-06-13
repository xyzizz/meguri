# Meguri

语言：[English](README.md) | 简体中文

面向 Codex 和 Claude Code 的 Agent 验证工作台。

Meguri 是一个本地优先的 CLI，以及一组放在目标项目里的工作流文件。它让当前 Codex / Claude Code 会话可以用稳定的方式理解项目、设计确定性的验证流程、安全运行验证，并留下可审计的报告。

Meguri 不会自己理解你的项目。项目理解、测试流程设计、测试代码编写，仍然由当前终端里的 AI 完成；Meguri 负责提供结构、约束、校验、执行和记录。

## 快速开始

在目标项目里打开 Codex 或 Claude Code，然后粘贴：

```text
请在当前项目安装 Meguri，并继续在当前 AI 会话中完成初始化。

运行：
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash -s -- --init --install-skills

安装完成后，运行 `meguri inspect`，遵循输出的 Meguri 规范，并写入 `.meguri/project-inspect.json` 和 `.meguri/project-brief.md`。

如果项目目标、执行入口、通过标准、凭证、数据准备或禁止的副作用不清楚，请先向我提出具体问题，再编写场景或测试。
```

更完整的可复制安装提示词在 [`prompts/install.md`](prompts/install.md)。

完成首次设置后，在当前 AI 会话里使用：

```text
/meguri inspect
```

## 安装内容

`meguri init --install-skills` 会创建：

```text
.meguri/
  project.yaml
  scenarios/smoke.yaml
  README.md
.agents/skills/meguri/SKILL.md
.claude/skills/meguri/SKILL.md
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

## 命令

| 命令 | 用途 |
| --- | --- |
| `meguri init --install-skills` | 创建项目 pack，以及 Codex / Claude Code 入口文件。 |
| `meguri inspect` | 输出给当前 AI 会话使用的项目检查规范，并保存到 `.meguri/prompts/inspect.md`。 |
| `meguri add "flow" --command "..." --pass-criteria "..."` | 在目标、可安全执行入口和确定性通过标准都清楚时，新增场景草稿。 |
| `meguri validate [scenario]` | 校验项目 pack，或校验某个场景别名/路径。 |
| `meguri run [scenario] --open` | 运行场景，并写入 `run.json`、`report.md` 和 `index.html`。默认运行 `smoke`。 |
| `meguri report --last --open` | 打开最新的本地 HTML 报告。 |

`add` 会保持保守。如果请求语义不清、缺少安全命令，或缺少确定性的通过标准，它会要求澄清，不写入任何文件，并以退出码 `2` 结束。

## 工作规则

- 让 Codex / Claude Code 读取现有文档、测试、脚本和配置，再编写项目专属的验证场景或辅助测试。
- 除非用户明确批准 execute 模式，否则新场景保持 `dry_run`。
- 不要把 LLM 的自我评价当作通过标准。通过证据应来自命令、结构化输出、日志、产物、截图或文件。
- 在启用 submit、deploy、payment、production writes、external sends 或 data migrations 前，必须先询问。
- 修改后，在安全的情况下运行 `meguri validate` 和对应的 `meguri run <scenario>`。

## 只安装 CLI

如果只想安装 CLI：

```bash
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash
```

之后可以在任意目标项目里初始化：

```bash
meguri init --install-skills
```

## 开发

在本仓库中运行：

```bash
python3 -m pip install -e '.[dev]'
pytest -q
```
