# Constraint Matrix — Barriers → Output Behaviors

<!--
Which barriers gate which output behaviors in Navigator.
This is the spec the constraint loop enforces, the document the validator
reads against, and the document the eval cases test against.
Section headers only — matrix fills in Weekend 1 Sunday with Robin.
-->

## Purpose

## Scope

### What this matrix covers

### What this matrix does not cover

## Barrier vocabulary

### Recognized barriers (schema)

### Barrier sources (intake vs extracted vs inferred)

### Multi-barrier interaction rules

## Output dimensions

### Contact method ordering

### Reply length / step count

### Language

### Tone / framing

### Fallback behavior when no compatible option exists

## The matrix

| Barrier | Contact method | Length | Language | Tone | Fallback |
|---------|----------------|--------|----------|------|----------|
| phone   |                |        |          |      |          |
| transport |              |        |          |      |          |
| focus   |                |        |          |      |          |
| overwhelm |              |        |          |      |          |
| paperwork |              |        |          |      |          |
| deadlines |              |        |          |      |          |
| losing_benefits |        |        |          |      |          |

## Enforcement strength

### Hard-blocked behaviors

### Soft-discouraged behaviors

### Always-allowed-with-caveat behaviors

### Crisis exceptions

## How each row maps to code

### Intake → session

### Session → system prompt

### Session → retrieval filter

### Session → reply validator

### Session → repair agent

## Open questions

## References

- Eval cases: `docs/evals/eval_cases.md`
- Schema: `src/constraints.py` (Weekend 1 Saturday deliverable)
- Audit context: `docs/audit/NAVIGATOR_AUDIT_2026-05-15.md`, `docs/audit/NAVIGATOR_AUDIT_CC_2026-05-15.md`
