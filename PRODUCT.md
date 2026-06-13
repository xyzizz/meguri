# Product

## Register

product

## Users

Meguri is for developers, agent harness operators, and engineers who need to verify AI-driven coding or workflow agents before trusting their output. They use it while building, adapting, or supervising agent loops, especially when a target project has real business rules, expensive side effects, or safety boundaries that cannot be left to an LLM's self-report.

Their job is to turn an AI workflow into an observable, repeatable, inspectable run: define scenarios, execute steps, collect artifacts, evaluate deterministic checks, understand failures, and decide whether a repair loop can continue safely.

## Product Purpose

Meguri provides a controlled verification layer around AI agents. It runs project-specific scenarios through thin adapters, records every step and artifact, evaluates deterministic assertions, and gives operators a clear view of pass, fail, warning, and blocked states.

Success means an operator can see what happened, why a run passed or failed, which evidence supports that result, and whether the workflow stopped before forbidden side effects. The product should make future self-repair loops safer by letting agents propose changes while the harness owns budgets, gates, artifacts, and success criteria.

## Brand Personality

Calm, traceable, audit-friendly.

The voice should be precise and operational. It should feel like a dependable control room for high-stakes agent work: restrained, evidence-first, and comfortable with dense technical information. It should never pretend certainty when a run is blocked or when an external dependency failed.

## Anti-references

Do not make this feel like an AI SaaS landing page, a flashy demo, or a generic enterprise admin template. Avoid decorative gradients, inflated hero messaging, vague "agent magic" claims, and visual choices that make the interface feel more theatrical than trustworthy.

Avoid hiding raw evidence behind summaries. Avoid dashboards that optimize for vanity metrics over actionable run state. Avoid designs where pass/fail status depends only on color or where blocked states look like ordinary failures.

## Design Principles

Evidence before assertion: every status should point to the artifact, check, log, or command result that supports it.

Make loops legible: attempts, repairs, reruns, budgets, and stop conditions should read as a clear timeline rather than scattered logs.

Separate execution from judgment: agents may generate code or diagnoses, but the harness UI should make deterministic checks, gates, and human approvals visibly distinct.

Respect operator density: this is a technical product, so compact tables, timelines, and expandable details are appropriate when they improve scanability.

Surface risk early: forbidden side effects, production gates, missing dependencies, and blocked external services should be prominent and unambiguous.

## Accessibility & Inclusion

Target WCAG AA. Status must not rely on color alone; pair color with labels, icons, and clear copy. Support reduced motion for any timeline or state-change animation. Preserve keyboard access for navigation, expandable artifacts, dialogs, and command actions. Use readable contrast for dense logs, muted metadata, and disabled states.
