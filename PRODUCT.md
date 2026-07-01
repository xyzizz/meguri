# Product

## Register

product

## Users

Meguri is for developers, agent harness operators, and engineers who use Codex or Claude Code to design project-specific verification loops. They want the AI to understand the current project, propose tests, write helper code when needed, and still leave a deterministic, auditable record.

Their job is not to hand-author every YAML file. Their job is to give the AI a controlled local workbench: inspect the project, ask when details are missing, design loops, execute steps, collect artifacts, evaluate deterministic checks, understand failures, repair when safe, rerun, and decide whether the loop can close.

## Product Purpose

Meguri provides an agent-facing verification specification around Codex and Claude Code. The user-facing object is a loop: a verification goal plus the completion chain from check to evidence to safe repair to rerun to pass, blocked, or needs-confirmation. Meguri owns local files, prompts, deterministic validation, loop execution, and reports. The surrounding AI agent owns project understanding, loop design, and code/test authoring.

The first-run experience is also agent-facing: the operator can paste a single
installation prompt into Codex or Claude Code, and the active AI session installs
Meguri, refreshes Meguri-owned entrypoints, invokes `/meguri`, runs
`meguri init`, follows the generated inspection workflow in the same session,
and continues from the resulting project specification. When the operator asks
to update Meguri itself, the active agent uses `meguri refresh` to update
Meguri-owned entrypoints separately from project initialization. Meguri still
never launches a second model or agent process, and project inspection is not
exposed as a separate public command.

Success means an operator can ask an AI agent to design a loop for a new project and still see what happened, why a run passed or failed, which evidence supports that result, and whether the loop stopped before forbidden side effects. The product should make future self-repair loops safer by letting agents propose and implement changes while Meguri owns budgets, gates, artifacts, and success criteria.

## Brand Personality

Calm, traceable, audit-friendly.

The voice should be precise and operational. It should feel like a dependable control room for high-stakes agent work: restrained, evidence-first, and comfortable with dense technical information. It should never pretend certainty when a run is blocked or when an external dependency failed.

## Anti-references

Do not make this feel like an AI SaaS landing page, a flashy demo, or a generic enterprise admin template. Avoid decorative gradients, inflated hero messaging, vague "agent magic" claims, and visual choices that make the interface feel more theatrical than trustworthy.

Avoid hiding raw evidence behind summaries. Avoid dashboards that optimize for vanity metrics over actionable run state. Avoid designs where pass/fail status depends only on color or where blocked states look like ordinary failures.

## Design Principles

AI does understanding, Meguri does constraints: project analysis and code changes come from Codex or Claude Code; Meguri supplies prompts, schemas, safety rules, validation, execution, and reports.

Evidence before assertion: every status should point to the artifact, check, log, or command result that supports it.

Make loops legible: attempts, repairs, reruns, budgets, and stop conditions should read as a clear timeline rather than scattered logs.

Separate execution from judgment: agents may generate code or diagnoses, but the harness UI should make deterministic checks, gates, and human approvals visibly distinct.

Respect operator density: this is a technical product, so compact tables, timelines, and expandable details are appropriate when they improve scanability.

Surface risk early: forbidden side effects, production gates, missing dependencies, and blocked external services should be prominent and unambiguous.

## Accessibility & Inclusion

Target WCAG AA. Status must not rely on color alone; pair color with labels, icons, and clear copy. Support reduced motion for any timeline or state-change animation. Preserve keyboard access for navigation, expandable artifacts, dialogs, and command actions. Use readable contrast for dense logs, muted metadata, and disabled states.
