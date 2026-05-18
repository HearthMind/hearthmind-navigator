# Before/After: Phone Barrier + Food Help

## Before (pre-challenge branch, production behavior)

Input: "I need food help but phone calls are hard for me"

barriers: none enforced

Response: recommended calling 211, gave 1-800 numbers, no acknowledgment of phone barrier

Failure mode: constraint detection existed but was advisory only; reply-side validator absent; Gemini disabled

## After (navigator-gemini-challenge branch)

Same input

barriers: `['phone']` detected and enforced

`constraints.py` validates recommendation text

Reply-side validator fires, detects phone-first pattern, triggers repair

Response: leads with SNAP online application, 211.org web portal, in-person food bank locations. Phone options listed last with explicit note that online/in-person alternatives exist.

Evidence: commit a3ab0ca (validator wiring), commit 218bbab (constraints.py)
