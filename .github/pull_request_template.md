<!--
Title should follow Conventional Commits, e.g. "feat: add X" or "fix: handle Y".
See conventionalcommit.json for the accepted types.
-->

## Summary

<!-- What does this change do, and why? Link any related issue. -->

## Type of change

<!-- Mark the one that best matches; keep a PR to a single type where possible. -->

- [ ] `feat` — new feature
- [ ] `fix` — bug fix
- [ ] `docs` — documentation only
- [ ] `refactor` — no behaviour change
- [ ] `test` — tests only
- [ ] `chore` / `build` / `ci` — tooling, deps, or pipeline

## Checklist

- [ ] `pre-commit run --all-files` passes (lint, format, type check)
- [ ] `pytest -m "not slow"` passes, and new/changed behaviour is covered by tests
- [ ] `CHANGELOG.md` updated under `[Unreleased]` (unless purely internal)
- [ ] Docs / README / docstrings updated if the public API or usage changed

## Notes for reviewers

<!-- Anything worth calling out: trade-offs, follow-ups, areas to focus on. Optional. -->
