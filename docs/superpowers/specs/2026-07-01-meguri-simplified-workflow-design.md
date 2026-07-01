# Meguri 简化工作流设计

## 背景

Meguri 当前已经从一个单 loop 执行器演化为面向 Codex 和 Claude Code 的本地验证工作台。它可以初始化项目 pack、生成 agent 入口、定义 loop、运行单个或多个 loop、写入 live run 记录、收集 evidence、生成单 run 报告、生成 batch 汇总，并维护项目/loop 索引页。

这些能力对高可信 agent 验证是有价值的，但用户需要理解的命令和参数已经偏多：`add`、`loops`、`delete`、`validate`、`upgrade`、`inspect`、`report --recent`、`report --runs`、`report --loops`、`run --all`、`run --exclude` 等入口让产品看起来像一个复杂 CLI，而不是一个 agent-facing workflow。

本设计的目标是降低用户使用负担。产品表面应尽量变成一个自然语言入口：用户使用 `/meguri` 表达意图，由 agent skill 把意图翻译成少数稳定 CLI 动作。底层 CLI 保持清晰和可自动化，但不再要求普通用户学习大量命令。

## 目标

- 让普通用户只需要记住 `/meguri`，用自然语言完成初始化、加 loop、运行、看报告、刷新 Meguri skill。
- 将公开 CLI 主命令硬收敛为 `init`、`run`、`report` 三个。
- `init` 默认联网刷新 Meguri 自身 skill/prompt，保证入口能力跟随官方仓库更新。
- `run` 负责运行前校验、单 loop、多 loop、`all` 和自动 batch report。
- `report` 只查看已有报告，不再承担手动拼 batch 或刷新历史报告。
- loop 的新增、删除和维护主要交给 `/meguri` agent workflow，不作为普通用户 CLI 主路径。

## 非目标

- 不在本阶段重构报告渲染内部结构。
- 不移除 evidence、replay、live snapshot、batch report 等已有核心能力。
- 不让 `init` 修改已有用户 loop、运行记录、evidence、helper 脚本或目标项目源码。
- 不把 Dapper/submit 领域指标从报告中拆出；这属于后续代码边界精简，不是本轮用户心智精简的主目标。

## 最终方向

产品体验采用自然语言优先：

```text
/meguri
初始化这个项目
给这个项目加一个 checkout 验证 loop
跑全部验证
跑 login 和 checkout
打开最新报告
刷新 Meguri skill
```

底层实现保留三个稳定 CLI：

```bash
meguri init
meguri run
meguri report
```

普通用户面对 `/meguri`。agent 和高级用户使用三条底层命令。这样产品表面是一个 agent workflow，工程上仍有稳定、可测试、可自动化的执行层。

## 用户心智

用户不再需要学习 `add`、`loops`、`delete`、`validate`、`upgrade` 或复杂的 `report` 聚合参数。

主要任务映射如下：

| 用户意图 | 推荐表达 | 底层动作 |
| --- | --- | --- |
| 初始化项目 | `/meguri 初始化这个项目` | `meguri init` |
| 刷新 Meguri skill | `/meguri 刷新 Meguri skill` | `meguri init` |
| 增加 loop | `/meguri 给登录流程加一个验证 loop` | agent 读项目并写 `.meguri/loops/<loop_id>/_loop.yaml` |
| 删除 loop | `/meguri 删除 checkout loop` | agent 删除对应 loop 文件夹 |
| 跑单个 loop | `/meguri 跑 login` | `meguri run login` |
| 跑多个 loop | `/meguri 跑 login 和 checkout` | `meguri run login checkout` |
| 跑全部用户 loop | `/meguri 跑全部验证` | `meguri run all` |
| 打开最新报告 | `/meguri 打开最新报告` | `meguri report --open` |

## CLI 合约

### `meguri init`

`init` 是唯一准备和维护入口。

默认行为：

1. 从 Meguri 官方仓库拉取最新版 skill/prompt 模板。
2. 覆盖更新 Meguri 自身入口文件：
   - `.agents/skills/meguri/SKILL.md`
   - `.claude/skills/meguri/SKILL.md`
   - `.claude/commands/meguri.md`
   - `~/.codex/prompts/meguri.md`
3. 初始化或刷新 `.meguri` pack。
4. 写入或刷新 `.meguri/generated/inspect.md`。
5. 打印 inspect workflow，交给当前 agent 继续理解项目。

`init` 可以在首次初始化时创建 Meguri 系统文件，例如 system `smoke` loop；但对已有项目，`init` 不更新：

- `.meguri/loops/<user_loop>/**`
- `.meguri/batches/**`
- `.meguri/runs/**`
- `.meguri/evidence/**`
- `.meguri/project-inspect.json`
- `.meguri/project-brief.md`
- `.meguri/loops/*/_scripts/**`
- 目标项目源码、测试、业务 prompt 或用户 helper 文件

联网刷新失败时，`init` 直接失败并退出非 0。错误信息应说明 skill refresh 失败，并提示用户检查网络或显式使用 `--offline`。

保留高级参数：

```bash
meguri init --offline
meguri init --force
```

`--offline` 使用本机已安装包内置模板，不访问网络。`--force` 只允许覆盖 Meguri 自身入口、system 文件和生成文件，不允许覆盖用户 loop、用户脚本、运行记录或源码。

### `meguri run`

`run` 是唯一执行入口。

支持：

```bash
meguri run <loop>
meguri run <loop1> <loop2>
meguri run all
```

规则：

- `all` 只选择用户添加的 loops，不运行系统 `smoke`。
- 显式多 loop 列表按用户给定顺序执行。
- 运行前自动 validate 目标 pack 和所有选中 loop。
- validate 失败时不执行任何 step。
- 多 loop 和 `all` 自动生成 batch report。
- execute-mode loop 仍必须显式带 `--allow-execute`。
- `--json` 和 `--open` 保留给 agent、自动化和本地查看。

移除：

```bash
meguri run --all
meguri run --exclude <loop>
meguri run --include-system
```

替代方式：

- `meguri run all`
- `meguri run <loop1> <loop2>`

### `meguri report`

`report` 只查看已有报告。

支持：

```bash
meguri report
meguri report <run_id>
meguri report <batch_id>
meguri report --open
meguri report <run_id> --open
```

规则：

- 不带参数时解析最新已有报告，可以是单 run 或 batch。
- 指定 id 时解析唯一匹配的 run 或 batch。
- `--json` 可保留给 agent/自动化。
- `--open` 打开解析到的 HTML 报告。

移除：

```bash
meguri report --recent <N>
meguri report --runs <run_id-or-path> ...
meguri report --loops <loop> ...
meguri report --running
meguri report --refresh
```

替代方式：

- batch report 只由 `meguri run <loop1> <loop2>` 或 `meguri run all` 自动生成。
- 历史报告不再通过 `report` 手动刷新。

## 硬移除范围

移除顶层命令：

```bash
meguri inspect
meguri add
meguri loops
meguri delete
meguri validate
meguri validate-scenario
meguri upgrade
```

替代关系：

| 被移除命令 | 替代方式 |
| --- | --- |
| `inspect` | `meguri init` |
| `add` | `/meguri` agent workflow 写 loop 文件 |
| `loops` | `/meguri` agent workflow 读取 `.meguri/loops` |
| `delete` | `/meguri` agent workflow 删除 loop 文件 |
| `validate` | `meguri run` 自动前置 validate |
| `validate-scenario` | 不作为公开命令保留 |
| `upgrade` | `meguri init` 默认联网刷新 skills |

保留但不主推的参数：

```bash
--allow-execute
--json
--open
--offline
--force
```

## Agent Workflow

生成的 Codex/Claude skill 和 prompt 应只主推自然语言工作流与三个底层命令。

入口文案重点：

- Meguri 的主入口是 `/meguri`。
- 用户可以自然语言要求初始化、添加 loop、运行验证、打开报告。
- agent 在添加 loop 前必须读取项目、明确安全执行入口和确定性通过标准。
- loop 文件仍写入 `.meguri/loops/<loop_id>/_loop.yaml`。
- helper/verifier 脚本仍应向 `MEGURI_EVIDENCE_DIR` 写 crash-safe structured evidence。
- execute-mode loop 仍需要用户明确批准，并用 `--allow-execute` 执行。

生成的 skill 不应再把 `add/loops/delete/validate/upgrade/report --recent/...` 作为普通路径列给用户。

## 错误处理

- `init` 默认联网刷新 skills；网络失败、仓库不可达、模板下载失败或模板校验失败时直接失败。
- `init --offline` 是显式逃生口，使用当前安装包内置模板。
- `init` 只更新 Meguri 自身入口、system 文件和允许刷新的生成文件，不碰已有用户 loop、用户脚本、运行记录、evidence、helper 脚本或源码。
- `run all` 没有用户 loop 时失败，并提示用户通过 `/meguri` 添加 loop。
- `run` 找不到 loop、validate 不通过或 execute loop 未带 `--allow-execute` 时，在执行 step 前停止。
- 多 loop 运行中断时继续写 blocked batch record，并保留 interruption metadata。
- `report` 找不到指定 run/batch 时失败，不生成新 batch，不刷新历史报告。

## 测试策略

新增或调整测试覆盖：

- CLI help 只暴露 `init`、`run`、`report` 三个主命令。
- `init` 默认执行远程 skill refresh；refresh 失败时 `init` 失败。
- `init --offline` 使用本地模板并跳过网络。
- `init` 不修改已有用户 `.meguri/loops/<user_loop>/**`、`.meguri/batches/**`、`.meguri/runs/**`、`.meguri/evidence/**`、用户 loop `_scripts/**` 或项目源码。
- `run all` 只选择用户 loops，不运行系统 `smoke`。
- `run <loop1> <loop2>` 运行前自动 validate，并生成 batch report。
- validate 失败时 shell step 不会执行。
- execute-mode loop 未带 `--allow-execute` 时失败且不执行。
- `report` 默认解析最新已有报告。
- `report <run_id>` 和 `report <batch_id>` 能解析指定报告。
- `report` 不再接受 `--recent`、`--runs`、`--loops`、`--running`、`--refresh`。
- 生成的 skill/prompt 只主推 `/meguri` 自然语言 workflow 和 `init/run/report` 三个底层命令。

## 迁移影响

这是一次有意的硬精简，会破坏旧命令和部分旧参数。

用户迁移：

- 旧的 `meguri upgrade --skills --refresh-index` 改为 `meguri init`。
- 旧的 `meguri run --all --exclude checkout` 改为显式列出需要跑的 loops，或调整 loop 集合后运行 `meguri run all`。
- 旧的 `meguri report --recent N`、`--runs`、`--loops` 不再用于手动拼 batch；需要汇总时重新运行多 loop 或 `all`。
- 旧的 `meguri add`、`loops`、`delete` 改为通过 `/meguri` 让 agent 执行。

文档迁移：

- README 快速开始只保留 `/meguri` 和三个底层命令。
- 安装提示不再要求安装后重复 `/meguri init`，除非安装器不再自动初始化。
- 生成的 `.meguri/README.md` 和 skill/prompt 同步减少命令表。

## 成功标准

- 新用户文档能在很短路径里说明：打开 agent，输入 `/meguri`，用自然语言说要做什么。
- 顶层 CLI help 中只有 `init`、`run`、`report` 三个主命令。
- 常见任务不需要用户理解 legacy scenarios、manual batch report、report refresh 或 loop management commands。
- `init` 默认拿到官方仓库最新 Meguri skill/prompt，失败时明确报错。
- 多 loop 运行仍保留自动 batch report，不牺牲现有审计能力。
