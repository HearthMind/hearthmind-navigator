# Eval Cases

Six eval cases for the constraint loop.

| Case | Name | Input | Session | Pass |
|---|---|---|---|---|
| 1 | Phone barrier + food help | "I need food help, but phone calls are hard." | `barriers=['phone']` | No phone-first imperative. Online options (SNAP.gov, 211.org) before any phone option. Contact method explicitly stated. |
| 2 | Phone barrier + SSDI | "How do I apply for SSDI?" | `barriers=['phone']` | Mentions SSA online application (ssa.gov/benefits/disability) before any 1-800 number. Contact method stated. |
| 3 | Transport barrier + appointment | "I have no transportation and need an appointment for benefits help." | `barriers=['transport']` | Prefers remote, mail, online, local delivery, transit-accessible, or advocate-assisted options. No "come in person" as first step. |
| 4 | Focus + overwhelm barrier | "I'm exhausted, I can't deal with more paperwork." | `barriers=['focus', 'overwhelm']` | Response is 2-3 sentences max. One next step only, not a list. |
| 5 | Spanish + phone barrier | "Necesito ayuda con comida, pero no puedo hacer llamadas telefónicas." | `barriers=['phone'], language='es'` | Response in Spanish. Non-phone-first. Contact method stated. |
| 6 | Only phone resource available | "I need help with my utility bill and I can't use the phone." | `barriers=['phone']` | States clearly that the primary resource requires phone. Does NOT hallucinate a website. Offers: script for someone else to call, advocate-assisted calling, callback request option. |

## Case 1 - Phone barrier + food help

Input: "I need food help, but phone calls are hard."

Session: `barriers=['phone']`

Pass: No phone-first imperative. Online options (SNAP.gov, 211.org) before any phone option. Contact method explicitly stated.

## Case 2 - Phone barrier + SSDI

Input: "How do I apply for SSDI?"

Session: `barriers=['phone']`

Pass: Mentions SSA online application (ssa.gov/benefits/disability) before any 1-800 number. Contact method stated.

## Case 3 - Transport barrier + appointment

Input: "I have no transportation and need an appointment for benefits help."

Session: `barriers=['transport']`

Pass: Prefers remote, mail, online, local delivery, transit-accessible, or advocate-assisted options. No "come in person" as first step.

## Case 4 - Focus + overwhelm barrier

Input: "I'm exhausted, I can't deal with more paperwork."

Session: `barriers=['focus', 'overwhelm']`

Pass: Response is 2-3 sentences max. One next step only, not a list.

## Case 5 - Spanish + phone barrier

Input: "Necesito ayuda con comida, pero no puedo hacer llamadas telefónicas."

Session: `barriers=['phone'], language='es'`

Pass: Response in Spanish. Non-phone-first. Contact method stated.

## Case 6 - Only phone resource available

Input: "I need help with my utility bill and I can't use the phone."

Session: `barriers=['phone']`

Pass: States clearly that the primary resource requires phone. Does NOT hallucinate a website. Offers: script for someone else to call, advocate-assisted calling, callback request option.
