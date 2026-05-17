# Archive — 2026-05-16

Snapshot of files removed from OVH during Weekend 1 cleanup of the Navigator production box. Captured so historical state is searchable in git without leaving clutter alongside live code on the deployment host.

## Files

### `routes_v2.pre-intake.bak`

(originally `/home/ubuntu/hearthmind-navigator/src/routes_v2.py.bak` on OVH; 136 lines)

Pre-May-11 snapshot of `routes_v2.py` — taken before the intake-wiring trilogy commits (`9fc3079` intake + `eaad96b` multi-select styling fix + `71e4195` phone-as-barrier Action Card branch) landed on May 11. Predates `_BARRIER_NOTES`, `_BASE_SYSTEM_PROMPT`, `_STYLE_GUIDANCE`, `_GOAL_FRAMING`. Predates session-aware system prompt entirely.

Useful as historical reference if anyone needs to diff "what did intake wiring change" without hunting through git.

### `routes_v2.pre-gemini-off.bak`

(originally `/home/ubuntu/hearthmind-navigator/src/routes_v2.py.pre-gemini-off.bak` on OVH; 144 lines)

Snapshot from before the Gemini wire-in was commented out for the intake-first deferral. Captures what the Gemini-integrated routes looked like *before* the disable. Also predates the session-aware system prompt addition. **The eventual Gemini wire-in will need to merge two patterns not both alive at the same time before**: this file's pre-disable Gemini path AND current `routes_v2.py`'s session-aware system prompt.

## Why archive instead of delete

The board's "stop arguing with my memory, search/check first" principle (May 15) cuts both directions: search/check beats memory, but search requires search-substrate to exist. Deleting these files makes future-Stark or future-Codex confabulate about what they contained. Keeping them in `docs/archive/` makes them queryable as files, not just as diff-text in `git log`.

## Why not in main repo root or `src/`

These are dead code. Putting them alongside live code creates exactly the "which file is real?" confusion the cleanup is designed to fix. `docs/archive/<date>/` is a scoped resting place that:

- Doesn't pollute `src/` with `.bak` files
- Sorts by date so future archives don't tangle
- Lives in `docs/` where reference material belongs

## Naming change from OVH

OVH had `routes_v2.py.bak` and `routes_v2.py.pre-gemini-off.bak`. Both renamed to `.bak` suffix only (dropped `.py`) since they're no longer expected to be valid Python imports — they're archive artifacts now. The first was renamed to `routes_v2.pre-intake.bak` to explicitly name what it is (the chronologically *older* one, since "the .bak with no description" is the bug we're fixing).

## OVH state after cleanup

The corresponding files on OVH (`/home/ubuntu/hearthmind-navigator/src/routes_v2.py.bak` and `.pre-gemini-off.bak`) are scheduled for deletion in this same cleanup pass. Run via:

```bash
ssh -i ~/.ssh/hearthmind_ovh_rsa ubuntu@15.204.75.156 \
  "rm /home/ubuntu/hearthmind-navigator/src/routes_v2.py.bak \
      /home/ubuntu/hearthmind-navigator/src/routes_v2.py.pre-gemini-off.bak"
```

Document this archive existed *before* deletion, so anyone questioning the deletion later can trace the chain.
