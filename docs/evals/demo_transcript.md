# Demo Transcript — 90-Second Video, Underlying Chat Content

<!--
The 90-second submission video has five beats (Grey's arc).
This file is the chat content underlying each beat — what the screen
actually shows when the camera is on the Navigator UI.
Voiceover script lives separately. This is just the chat content.
Section headers only — content drops in Weekend 4 polish with Robin.
-->

## Overview

### Target length

### Submission context

### What this file is (and isn't)

## The five-beat arc

### Beat 1 — Show the failure

#### Setup (which surface, which session)

#### User input

#### System response (current production / main branch)

#### What the viewer should notice

### Beat 2 — Show the optimization

#### Setup (challenge branch, same session)

#### User input (identical to Beat 1)

#### System response (challenge branch)

#### What the viewer should notice

### Beat 3 — Show the agent team running the loop

#### Setup (instrumentation visible)

#### Intake → barrier identified

#### BigQuery retrieval → resources returned

#### Constraint Agent → phone-first mismatch flagged

#### Repair Agent → recommendation rewritten

#### Final response → contact method stated

#### What the viewer should notice

### Beat 4 — Show institutional memory

#### Setup (BigQuery `discovered_resources` table view)

#### Gemini-discovered resource written

#### Schema fields visible (`verified=false`, `barriers_active`, `discovered_from_query_hash`)

#### Privacy guardrails visible (no raw query)

#### What the viewer should notice

### Beat 5 — Show the handoff

#### Setup (action plan + caseworker summary)

#### User-facing action plan

#### Caseworker summary

#### What the viewer should notice

## Continuity notes

### Same user across beats

### Same session payload

### Visible elements per beat (UI, terminal, BigQuery console)

## Cuts and timing

### Beat 1 timing

### Beat 2 timing

### Beat 3 timing

### Beat 4 timing

### Beat 5 timing

## Open questions

## References

- Eval cases: `docs/evals/eval_cases.md` (Case 1 = Beats 1-2)
- Before/after evidence: `docs/evals/before_after_phone_barrier.md`
- Constraint matrix: `docs/evals/constraint_matrix.md`
- Grey-revised schedule v2 demo arc: `docs/grey-gemini-challenge-schedule-2026-05-15-v2.md` (§ Demo arc)
