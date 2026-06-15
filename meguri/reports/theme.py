from __future__ import annotations


GLOW_BACKGROUND_HTML = '<div class="glow-bg" aria-hidden="true"></div>'


GLOW_BASE_CSS = """
:root {
  color-scheme: dark;
  --bg: #0b0f1a;
  --bg-deep: #070a12;
  --surface: rgba(15, 22, 38, 0.74);
  --surface-strong: rgba(22, 32, 52, 0.86);
  --surface-soft: rgba(160, 196, 255, 0.08);
  --ink: #f0f4ff;
  --muted: #9ca9c3;
  --line: rgba(190, 215, 255, 0.18);
  --line-strong: rgba(190, 215, 255, 0.34);
  --glow-primary: #a0c4ff;
  --glow-secondary: #d4b5ff;
  --glow-accent: #b4ffdb;
  --glow-warm: #ffd89b;
  --pass: #7cffbd;
  --fail: #ff6f91;
  --blocked: #ffd89b;
  --warning: #ffe5b4;
  --accent: var(--glow-primary);
  --unknown: #9ca9c3;
  --shadow-panel:
    0 18px 54px rgba(0, 0, 0, 0.38),
    0 0 34px rgba(160, 196, 255, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  --shadow-glow:
    0 0 16px rgba(160, 196, 255, 0.24),
    0 0 34px rgba(160, 196, 255, 0.12);
}
* { box-sizing: border-box; }
html { min-height: 100%; }
body {
  min-height: 100vh;
  margin: 0;
  color: var(--ink);
  background:
    radial-gradient(120% 90% at 50% -20%, rgba(83, 116, 255, 0.24), transparent 48%),
    linear-gradient(135deg, var(--bg-deep) 0%, #111827 42%, #151326 100%);
  font: 14px/1.55 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(190, 215, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(190, 215, 255, 0.035) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.8), transparent 86%);
}
.glow-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}
.glow-bg::before,
.glow-bg::after {
  content: "";
  position: absolute;
  inset: -22%;
  transform: translateZ(0);
}
.glow-bg::before {
  background:
    conic-gradient(from 210deg at 20% 20%,
      transparent 0deg,
      rgba(160, 196, 255, 0.34) 58deg,
      rgba(212, 181, 255, 0.28) 112deg,
      transparent 172deg,
      rgba(180, 255, 219, 0.2) 238deg,
      transparent 318deg);
  filter: blur(72px);
  opacity: 0.78;
  animation: glowDrift 22s ease-in-out infinite alternate;
}
.glow-bg::after {
  background:
    linear-gradient(115deg,
      transparent 18%,
      rgba(255, 216, 155, 0.14) 38%,
      transparent 58%),
    linear-gradient(35deg,
      transparent 32%,
      rgba(180, 255, 219, 0.12) 54%,
      transparent 74%);
  filter: blur(42px);
  opacity: 0.68;
  animation: glowBreath 8s ease-in-out infinite;
}
main {
  position: relative;
  z-index: 1;
  animation: fadeInGlow 0.7s ease-out both;
}
h1, h2, h3 {
  color: var(--ink);
  letter-spacing: 0;
}
h1 {
  text-shadow:
    0 0 18px rgba(255, 255, 255, 0.22),
    0 0 40px rgba(160, 196, 255, 0.26);
}
p { color: var(--muted); }
a {
  color: var(--glow-primary);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
  text-shadow: 0 0 12px rgba(160, 196, 255, 0.22);
}
a:hover { color: var(--glow-accent); }
code, pre {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
pre {
  color: #e8f0ff;
  background: rgba(7, 10, 18, 0.72);
  border: 1px solid rgba(190, 215, 255, 0.18);
  box-shadow: inset 0 0 18px rgba(160, 196, 255, 0.04);
}
table {
  border-color: var(--line);
}
th {
  color: var(--muted);
}
td {
  color: var(--ink);
}
a:focus-visible,
button:focus-visible,
summary:focus-visible {
  outline: 3px solid rgba(160, 196, 255, 0.34);
  outline-offset: 3px;
}
@keyframes glowDrift {
  from { transform: translate3d(-1.5%, -1%, 0) rotate(0.001deg); }
  to { transform: translate3d(1.5%, 2%, 0) rotate(0.001deg); }
}
@keyframes glowBreath {
  0%, 100% { opacity: 0.48; }
  50% { opacity: 0.82; }
}
@keyframes fadeInGlow {
  from { opacity: 0; transform: translateY(10px); filter: brightness(0.92); }
  to { opacity: 1; transform: translateY(0); filter: brightness(1); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
  }
}
""".strip()
