<!--
Title should follow Conventional Commits, e.g. "feat: add X" or "fix: handle Y".
See conventionalcommit.json for the accepted types.
-->

## Summary

<!-- What does this change do, and why? Link any related issue. -->

## Changelog-worthy changes

<!-- Check all that apply — a PR can span more than one category. These mirror
     the sections in CHANGELOG.md; use them as a guide for what to add there. -->

- [ ] Added — new feature or capability
- [ ] Changed — change in existing behaviour
- [ ] Deprecated — soon-to-be-removed feature
- [ ] Removed — removed feature or code
- [ ] Fixed — bug fix
- [ ] Security — vulnerability fix
- [ ] None of the above (e.g. docs, tests, or internal tooling with no
      user-facing effect)

## Checklist

- [ ] `pre-commit run --all-files` passes (lint, format, type check)
- [ ] `pytest -m "not slow"` passes, and new/changed behaviour is covered by tests
- [ ] `CHANGELOG.md` updated under `[Unreleased]` (unless purely internal)
- [ ] Docs / README / docstrings updated if the public API or usage changed

## Notes for reviewers

<!-- Anything worth calling out: trade-offs, follow-ups, areas to focus on. Optional. -->
