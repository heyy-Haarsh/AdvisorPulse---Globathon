# Advisor Pulse — Speaker Notes

**Deck:** `deliverables/ppt/Globathon_Advisor_Dynamic_Summary.pptx`  
**Timing guide (12-slide ideation deck):** ~8–10 minutes + Q&A.  
**Finale pitch:** compress to slides 1, 4, 8, 9/12 (official Round 2 PPT is **2–4 slides**).

---

## Slide 1 — Product & promise
“Judges, our product is **Advisor Pulse**. The question every advisor must answer every day is: *Where does this client stand?* We are an investor-intelligence and attention-prioritization layer — not another CRM, not another chart wall. You’ll see a live demo book of **220 synthetic clients** with a computed review queue — currently **16** clients need review, with **1 Critical** and **15 High**.”

## Slide 2 — Problem
“Advisors already have data. What they lack is continuous, explainable attention across a book that often exceeds capacity. Cerulli’s 2026 AI study found **64%** of surveyed RIAs say AI reduced admin work — firms use AI to expand capacity, not replace advice. Our hypothesis: the workflow gap is prioritization with evidence.”

## Slide 3 — Why existing tools fall short
“Be fair: Salesforce engages households; Morningstar researches; Aladdin monitors risk at institutional depth. We are not claiming they do nothing. We claim the **cross-context loop** — goal path vs actual, why the gap, why now, what to prepare — is still fragmented, especially for the long tail.”

## Slide 4 — Solution
“Advisor Pulse workflow: **Detect → Explain → Prioritize → Prepare → Act → Learn**. Differentiation is the combination: transparent factors, evidence-linked summaries, human-approved actions.”

## Slide 5 — How it works
“Analytics first, language second. Structured metrics feed prioritization; summaries only restate those facts. Honest data story: the supplied transaction CSV is cash-flow only; portfolio and goal analytics use **labeled SYNTHETIC DEMO data**. Security boundary: no sensitive data to external models without a DPA. Demo uses deterministic templates.”

## Slide 6 — 20 vs 200
“Greatest incremental value is the **200**, not replacing judgment on the **20**. Known clients get sharper meeting prep. Long-tail clients get proactive, thresholded signals. Numbers on this slide are illustrative unless labeled Cerulli.”

## Slide 7 — Product walkthrough
“These are **real prototype screens** from our React app — Overview and Attention queue. Dark navy, teal accents. DEMO badges are intentional. Walk the UI: book KPIs → ranked queue → open a client.”

## Slide 8 — Demo Priya + Arjun
“**Priya Sharma** — Critical, score 78, about **−20.9%** vs expected path, mid-cap underperformance and allocation drift. Escalate.  
**Arjun Mehta** — On Track, score 0, near path; absolute AUM dipped because of a **planned education withdrawal**. System does **not** escalate. We’re not a red-badge factory.”

## Slide 9 — Privacy
“SEBI makes the investment adviser responsible for AI tools and client data — Reg. **15(14)**; disclose AI use under **18(9)**. DPDP informs consent and purpose limitation. Prototype is local demo — not certified.”

## Slide 10 — Competitive positioning
“Point to the matrix: we win on explainable attention workflow; we do **not** claim deeper risk engines than Aladdin.”

## Slide 11 — Roadmap
“What’s real today vs what needs custodian/CRM integrations. Pilot metrics are a plan — no fake results. Note Globathon Round 2 rebuild rule: problem-specific logic must be built during the 12-hour finale.”

## Slide 12 — Close
“Return to the question. Less time searching. More time acting on the right clients. Thank you — happy to demo live or take questions.”

---

## Suggested answers to hard interruptions
See `judge_qa.md` for the full set. Short versions:

- **Why not CRM?** CRM stores relationships; we decide *who needs attention why* with evidence.
- **Alert fatigue?** Configurable thresholds, confidence, data-quality separated from financial risk.
- **AI hallucinations?** Numbers from analytics only; LLM optional paraphrase disabled by default.
- **Is the data real?** Transactions layer vs SYNTHETIC portfolio universe — we label both on-screen and on-slide.
