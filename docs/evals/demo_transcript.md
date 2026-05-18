# Demo Transcript

The 90-second demo video script's underlying chat content.

## Beat 1 - Show the failure (0-15s)

User: "I need help with food, but phone calls are really hard for me."

Navigator (pre-challenge): "You can call 211 to connect with local food resources. The USDA National Hunger Hotline is available at 1-866-3-HUNGRY."

[Caption: Phone barrier ignored. User told to call.]

## Beat 2 - Show the optimization (15-30s)

Same input on navigator-gemini-challenge branch.

[Caption: Constraint loop active.]

## Beat 3 - Show the loop running (30-55s)

Intake detects `barriers=['phone']`

`constraints.py` normalizes -> `has_barrier('phone') = True`

BigQuery retrieves food programs

Validator checks recommendation text -> phone-first pattern detected

Repair: regenerate with explicit non-phone instruction

[Caption: Validate -> Repair -> Summarize]

## Beat 4 - Show the response (55-75s)

Navigator (challenge branch): "For food help without phone calls, you can apply for SNAP online at ssa.gov or benefits.gov. Local food banks like [X] accept walk-ins -- no call needed. The 211.org website lists food pantries by zip code."

[Caption: Contact method stated. Phone-free path first.]

## Beat 5 - Show institutional memory (75-90s)

Gemini-discovered resource written to BigQuery: `verified=false`, `barriers_active=['phone']`, `recommended_access_mode='online'`

[Caption: Every discovery improves the database.]
