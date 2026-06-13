# Product

## Register

product

## Users

Meguri is for developers, agent harness operators, and engineers who use Codex or Claude Code to design project-specific verification flows. They want the AI to understand the current project, propose tests, write helper code when needed, and still leave a deterministic, auditable record.

Their job is not to hand-author every YAML scenario. Their job is to give the AI a controlled local workbench: inspect the project, ask when details are missing, design scenarios, execute steps, collect artifacts, evaluate deterministic checks, understand failures, and decide whether a repair loop can continue safely.

## Product Purpose

Meguri provides an agent-facing verification specification around Codex and Claude Code. The CLI owns local files, prompts, deterministic validation, scenario execution, and reports. The surrounding AI agent owns project understanding, test-flow design, and code/test authoring.

Success means an operator can ask an AI agent to design verification for a new project and still see what happened, why a run passed or failed, which evidence supports that result, and whether the workflow stopped before forbidden side effects. The product should make future self-repair loops safer by letting agents propose and implement changes while Meguri owns budgets, gates, artifacts, and success criteria.

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
