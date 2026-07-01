# Meguri

语言：[English](README.md) | 简体中文

面向 Codex 和 Claude Code 的 Agent 验证工作台。

Meguri 是一个放在目标项目里的 AI loop 工作流。它让当前 Codex / Claude
Code 会话可以用稳定的方式理解项目、设计确定性的验证闭环、安全运行验证、必要时修复并复测，最后留下可审计的报告。

Meguri 不会自己理解你的项目。项目理解、测试流程设计、测试代码编写，仍然由当前终端里的 AI 完成；Meguri 负责提供结构、安全规则、执行和记录。

## 快速开始

在目标项目里打开 Codex 或 Claude Code，然后调用 `/meguri` 并提出请求：

```text
Initialize this project with Meguri.
Update Meguri.
Add a verification loop for <goal>.
Run all verification.
Open the latest report.
```

首次安装时，可以把这段提示词粘贴给 Codex 或 Claude Code：

```text
Install Meguri in this project and enable the Codex / Claude Code slash entrypoint.

Run:
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash

After installation, invoke /meguri and ask:
Initialize this project with Meguri.
Update Meguri.
```

更完整的可复制安装提示词在 [`prompts/install.md`](prompts/install.md)。

如果新安装的入口没有出现，重启 Codex / Claude Code，或在同一个项目里开启新会话，然后输入 `/` 搜索 `meguri`。

`meguri init` 初始化项目 pack。`meguri refresh` 从官方仓库更新 Meguri 管理的 agent 入口文件；网络不可用时，运行 `meguri refresh --offline` 使用随包模板。

## 创建内容

安装器会创建项目工作流文件：

```text
.meguri/
  project.yaml
  generated/inspect.md
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
  batches/<batch_id>/
    batch.json
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

## Loop

Loop 是 Meguri 的用户主概念。它不是单纯的测试流程，而是一条完整的完成链路：

```text
目标 -> 安全执行 -> 确定性检查 -> 证据 -> 安全时修复 -> 复测 -> 通过 / 阻塞 / 询问
```

新 loop 存储在 `.meguri/loops/<loop_id>/_loop.yaml`。每次运行会创建一个带时间戳的 `.meguri/loops/<loop_id>/<YYYYMMDD_HHMMSS>/` 记录。多 loop 顺序运行会创建 `.meguri/batches/<batch_id>/` 记录。

通过 `/meguri` 用自然语言初始化项目、添加或移除 loop、运行验证、打开报告。请求清楚时，agent 会直接编辑 Meguri 管理的 loop 文件；如果目标、安全执行入口、通过标准、凭证、数据准备或禁止副作用不清楚，它会先提问。

## CLI 底层命令

公开 CLI 刻意保持很小：

```text
meguri init
meguri refresh
meguri run <loop>
meguri run <loop1> <loop2>
meguri run all
meguri report [run_or_batch_id]
```

`init` 初始化或修复项目 pack。`refresh` 从官方仓库更新 Meguri 管理的 agent 入口文件；网络不可用时，`meguri refresh --offline` 会使用随包模板。`run` 运行一个命名 loop、一个明确的顺序列表，或全部用户 loop。`report` 是只读命令，用于返回最新报告或指定 run / batch 报告。

## 工作规则

- 让 Codex / Claude Code 读取现有文档、测试、脚本和配置，再编写项目专属的 loop 或辅助测试。
- 除非用户明确批准 execute 模式，否则新 loop 保持 `dry_run`。批准后，execute-mode run 必须带 `--allow-execute` 确认标记。
- 不要把 LLM 的自我评价当作通过标准。通过证据应来自命令、结构化输出、日志、产物、截图或文件。
- 编写 helper/verifier 脚本时，即使异常也要向 `MEGURI_EVIDENCE_DIR` 写结构化 evidence，包含部分输入/输出、错误、traceback 和 artifact 链接。
- 在启用 submit、deploy、payment、production writes、external sends 或 data migrations 前，必须先询问。

## 开发

在本仓库中运行：

```bash
python3 -m pip install -e '.[dev]'
pytest -q
```
