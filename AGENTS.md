# evaldiff agent rules

Single source of rules for every coding agent. `CLAUDE.md` imports this file.

## Commands

- `make context`: fetch, then branch vs `origin/main`. Run it at session start.
- `make test [TEST=<module>]` (`unittest`, e.g. `TEST=tests.test_stats`); `make check` runs the
  tests plus `git diff --check`.
- Run: `python3 -m evaldiff` (http://127.0.0.1:8765/).
- Python 3.9+, standard library only. No linter, formatter or CI yet.

## Build workflow (agents in `.claude/agents/`)

1. `planner` (opus/high) writes `spec.md`: sprints with pass/fail criteria.
2. `generator` (sonnet/medium) builds one sprint and commits.
3. `evaluator` (opus/high) checks every criterion and reports PASS or FAIL with a bug list.
4. On FAIL, `generator` fixes every listed bug, then `evaluator` runs again.

## Git and GitHub workflow

Remote: `origin` on GitHub. `main` changes only through merged PRs.

- Session start: `make context`, then report the current branch and how it compares with
  `origin/main`. Local state can be stale: a PR may have merged on GitHub since.
- Update local `main` only with `git pull --ff-only` while on `main`. Never merge,
  fast-forward or commit to `main` locally.
- New work: `git switch -c <type>/<topic> origin/main` (types: `feat`, `fix`, `docs`,
  `chore`). Never reuse a branch whose PR has merged.
- Commit locally at the end of each unit of work (a sprint, a fix) without asking.
- Ask the user first, every time, and wait for a clear yes: `git push`, opening a PR
  (`gh pr create`), and merging a PR. A yes covers that one action only.
- After a PR merges: `git switch main && git pull --ff-only`, then
  `git branch -d <branch>` (lowercase `-d` only). If it refuses, for example after a
  squash merge, ask the user before `-D`.
