# ADR 011: Use typed browser-native rendering

Status: accepted for the local diagnostic profile.

A larger framework could simplify component composition, but the terminal needs a small local deployment and explicit typed domain contracts.

Decision: Compile TypeScript to browser modules. Use native EventSource, tables, forms, SVG and a keyboard-accessible player dialog. Escape provider text before interpolation and avoid external scripts/fonts.

Consequence: Large string render functions are a maintainability limit. Current controls preserve search focus, reset navigation scroll and trap dialog focus. Broader assistive-technology validation remains pending.
