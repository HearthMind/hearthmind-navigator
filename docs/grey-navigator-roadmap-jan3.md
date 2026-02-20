# Navigator Live Interaction Roadmap
*Grey's Spec — January 3, 2026*

---

## Phase 1 — "Feels Alive" (2–4 hours)
**Goal:** Convert Navigator from brochure → interactive tool.

### 1️⃣ Interactive Checklist
**What:**
- Render checklist items with checkboxes
- Save checked state in browser (localStorage)
- Add progress bar ("3 / 12 steps done")

**Why it matters:**
- Immediately proves cognitive load reduction
- Creates visible user progress (funders love progress loops)

### 2️⃣ Category Drill-Down
**What:**
- Clicking a Benefit / Resource category opens a dynamic panel
- Shows: Description, Example actions, "Next step" buttons

**Why:**
- Shows system is guiding, not just listing
- Makes Navigator feel like a navigator

---

## Phase 2 — "Proof of Guidance" (1 day)
**Goal:** Demonstrate intelligent decision flow.

### 3️⃣ Guided Intake Flow
**What:** A 3–5 question adaptive wizard:
- "What are you trying to do?"
- "What state are you in?"
- "What's hardest right now?"

**Output:**
- Custom checklist
- Suggested benefit paths
- Resource shortlist

**Why:**
- Demonstrates emotionally adaptive logic
- Becomes your demo showpiece

---

## Phase 3 — "Continuity" (1–2 days)
**Goal:** Show memory and relationship, not just answers.

### 4️⃣ Soft Memory Loop
**What:**
- Ask user for alias
- Remember: goals, barriers, preferences (opt-in)
- On return: "Welcome back, you were working on…"

**Why:**
- This is your secret weapon
- Continuity is your category differentiator

---

## Phase 4 — "Traction Engine" (½ day)
**Goal:** Convert traffic into measurable interest.

### 5️⃣ Feedback + Early Access Capture
**What:**
- Short feedback form
- Email opt-in
- "Request pilot access" button

**Why:**
- Turns demo into pipeline
- Creates engagement metrics for grants

---

## Phase 5 — "Credibility Layer" (optional polish)
**Goal:** Make Navigator look production-grade.

### 6️⃣ Progress Timeline UI
- Step timeline view
- Visual completion arcs

### 7️⃣ Consent + Privacy View
- Clear consent banner
- Data handling transparency page

---

## Build Order (Best ROI)
1. Interactive checklist
2. Drill-down panels
3. Guided intake
4. Memory loop
5. Feedback capture

Everything after that is polish.

---

# Guided Intake Flow — Full Spec

## UX: 3–5 Questions, Adaptive
Entry button: "Start Guided Intake"
Time promise: "Takes ~60 seconds."

### Q1 — What are you trying to do today?
Single-select tiles:
- Find benefits / assistance
- Handle a notice / paperwork
- Plan next steps
- Reduce overwhelm / get organized
- Just exploring

Store as: `goal`

### Q2 — Where are you located?
State dropdown (US states) + "Prefer not to say"
Store as: `state`

### Q3 — What's hardest right now?
Multi-select chips:
- I can't focus / brain fog
- I'm overwhelmed
- I don't know where to start
- I'm afraid I'll lose benefits
- Paperwork / forms
- Phone calls
- Deadlines
- Other

Store as: `barriers[]`

### Q4 — What kind of support do you want from Navigator?
Single-select tone:
- Direct + step-by-step
- Gentle + supportive
- Fast summary
- Just give me resources

Store as: `style`

### Q5 (Optional) — Urgency
Single-select:
- Today
- This week
- No deadline

Store as: `urgency`

---

## Output Page: "Your Plan"

### A) Your Next 3 Steps (always visible)
Example template:
1. "Identify the benefit area you're targeting"
2. "Gather documents (list)"
3. "Choose one action: call / online form / appointment"

### B) Your Checklist (dynamic, tickable)
- Pre-populated based on goal + barriers + urgency
- Save state to localStorage at minimum

### C) Resources (filtered)
- Show 5–10 links grouped by category
- If state provided, show state heading

---

## Mapping Rules (Simple Deterministic Logic)

### Checklist base items (always included)
- Make a folder (digital or physical)
- Gather ID + proof of address
- Gather income/benefit letters (if applicable)
- Write down 3 questions you need answered
- Log what you tried (dates/times)

### If goal = paperwork
Add:
- Identify form/notice type
- Find deadline date
- Draft response notes
- Make copies / screenshots
- Submit + confirm receipt

### If goal = benefits
Add:
- Identify program (SNAP/Medicaid/SSDI/etc.)
- Check eligibility basics
- Prepare verifications
- Contact method choice (online/phone/in-person)

### If barriers includes "phone calls"
Add:
- Call script template
- "Ask for supervisor / call-back" checklist item
- Best-time-to-call suggestion (placeholder)

### If urgency = today
Promote:
- "One action now" card: pick exactly one step
- "Stop condition" card: what "done for today" means

---

## Data Model

```json
{
  "goal": "paperwork",
  "state": "WA",
  "barriers": ["overwhelmed", "phone_calls"],
  "style": "step_by_step",
  "urgency": "this_week",
  "created_at": "ISO"
}
```

**Persistence options:**
- MVP: localStorage only
- Next: SQLite (session table) with optional email capture

---

## Microcopy (low-stress)
- "You're not behind. You're orienting."
- "One step counts."
- "Navigator can remember this plan (optional)."

---

## Acceptance Criteria
- [ ] Guided Intake exists and is accessible from home
- [ ] Generates plan + checklist + resources
- [ ] Checklist is interactive and persists on refresh
- [ ] No login required
- [ ] Clear "Demo / Beta" badge with expectations

---

# Call Script Generator — Spec

## Purpose
Phone calls are one of the biggest barriers for people navigating benefits.
This tool gives users ready-made scripts so they don't have to think while anxious.

## Entry Point
Card on user's plan:
📞 Call Script Helper — "Get words you can read when you call."
Button: Generate My Script

## Inputs (from Guided Intake)
- goal
- state
- barriers
- urgency
- style

## Script Output Structure

### 1️⃣ Opening Line
"Hi, my name is ___ and I'm calling because I need help with ___."
(Auto-filled using goal)

### 2️⃣ Identity / Context Block
"I'm trying to make sure my information is correct and that I'm following the right steps."

### 3️⃣ The Ask (from goal)
- Paperwork: "I received a notice and I want to make sure I understand what it means."
- Benefits: "I'm trying to check my eligibility and what documents are required."

### 4️⃣ Anxiety Support Lines (if barrier includes overwhelm/phone_calls)
- "I may need you to repeat things slowly — thank you."
- "Could you tell me what my next step is in simple terms?"

### 5️⃣ Supervisor / Escalation Option
"If you're not able to help me, may I speak to a supervisor?"

### 6️⃣ Closing Line
"Could you please tell me my reference number or who I spoke to today?"

## UI Features
- Copy button
- Print button
- "Edit words" free-text field
- "Save this script to my plan"

---

# Letter & Form Response Generator — Spec

## Purpose
Most people don't fail benefits systems because they're ineligible.
They fail because they can't write the right words under stress.

## Entry Point
Card on plan:
📝 Letter & Form Helper — "Get calm, correct words for paperwork."
Button: Generate My Letter

## Step 1 — What are you responding to?
Single-select:
- A notice / denial
- A verification request
- An appeal
- A general information request
- Something else

Store as: `letter_type`

## Step 2 — What's the situation?
Multi-select:
- I missed a deadline
- I'm confused about what they're asking
- My income changed
- My medical situation changed
- I need an extension
- I need reconsideration
- Other

Store as: `situation[]`

## Step 3 — Tone preference
Single-select:
- Direct & formal
- Polite & neutral
- Gentle & personal

Store as: `tone`

## Output — Generated Letter

### Header
- Date:
- To:
- Re:

### Opening Paragraph (context)
"I am writing in response to the notice I received dated ___ regarding my benefits."

### Situation Paragraph (dynamic from situation[])
- Missed deadline: "I apologize for the delay. I am currently managing health and administrative challenges..."
- Income change: "My income has changed and I want to ensure my records are accurate."

### Request Paragraph (the ask)
- Appeal: "I am respectfully requesting reconsideration of this decision."
- Verification: "I am submitting the requested documentation."
- Extension: "I am requesting additional time to gather documents."

### Closing
"Thank you for your time and assistance. Sincerely,"

## UI Features
- Editable text
- Copy / Print / Download PDF
- Save to Plan
- "What to Attach" helper checklist

---

# Future Features (mentioned)
- Agency Call Log
- Deadline Guardian
- State-specific resource packs
- Email capture: "Send this plan to yourself"
- Print/PDF view
