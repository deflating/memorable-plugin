# Memorable Coding Style

Use this style for all future changes in this repository.

## Python

- Functions do one thing and stay under 30 lines. Split longer functions.
- Validate data only at system boundaries:
  - API handlers
  - file reads
  - user input
- Inside internal code paths, assume data is already clean.
- Do not add `isinstance` checks or internal `try/except` for normal flow.
- Keep comments minimal. Prefer clearer code over explanatory comments.
- Comments about why are acceptable.
- Do not use underscore-prefixed module helpers.
- Only use underscore-prefixed names when genuinely private to a class.
- Add docstrings only to public API functions.

## JavaScript

- Avoid repeating `getElementById` + null-check + `addEventListener`.
- When binding multiple elements, use a helper or a batched pattern.
- Prefer declarative patterns over imperative DOM manipulation when practical.
- Keep template literals readable.
- If a template has more than 3 nested conditionals, extract parts into variables first.

## CSS

- Use the existing CSS variable system for all colors.
- Do not hardcode hex colors outside `:root`.
- Follow existing naming conventions for new component styles.
- Reuse existing variables before creating new ones.

## General

- One concern per commit.
- Do not bundle unrelated changes.
- Keep implementations simple.
- Do not add defensive handling for impossible scenarios.
- If unsure whether defensive code is needed, do not add it.

