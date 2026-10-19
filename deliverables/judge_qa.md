# Advisor Pulse — Judge Q&A

Honest, evidence-backed answers. Limitations stated where architecture proposes but does not prove a solution.

---

### 1. Why would an advisor use this instead of an existing CRM or portfolio tracker?
CRM stores relationships and tasks; portfolio tools analyze holdings and risk. Advisor Pulse sits **between** them as an attention layer: continuous expectation-vs-actual, explainable drivers, and a transparent review queue. Salesforce and Aladdin already advertise briefs/alerts — our job-to-be-done is the **cross-context why-now loop** for the long tail, with factors an advisor can audit.

### 2. What is genuinely differentiated?
The combination: goal-path deviation + qualified driver analysis + multi-factor transparent priority (financial vs data-quality separated) + evidence-bound summaries + meeting prep — wired as Detect → Explain → Prioritize → Prepare → Act → Learn. Individual pieces exist elsewhere; the integrated attention workflow is the product.

### 3. Why more valuable than a dashboard?
Dashboards wait to be opened. We push a **ranked, explained queue** and meeting briefs so advisors allocate scarce time without inspecting every portfolio daily.

### 4. How do we serve the 200 clients the advisor cannot review individually?
Proactive detection on the long-tail book with thresholds. Demo: 200 long-tail + 20 high-visibility synthetic clients; only Critical/High enter the action queue. Greatest incremental value is scaling quality attention across the long tail while still supporting prep for known clients. Book sizes are **illustrative** unless citing Cerulli capacity research.

### 5. How do we prevent alert fatigue?
Configurable thresholds, severity bands (Critical/High/Monitor/On Track), confidence levels, and explicit suppressions (e.g., planned withdrawal). Data-quality flags do not auto-escalate as financial distress.

### 6. How do we know a client is genuinely falling behind?
Compare mapped portfolio value to an **explicit expected path** (documented expected return + planned SIP), not raw balances. Also show TWR vs benchmark. Behind path + supporting factors + confidence — not a single opaque score.

### 7. Market-wide vs portfolio-specific underperformance?
Active return = portfolio TWR − benchmark TWR over the same window. Allocation drift vs policy is shown separately. Full Brinson attribution is **not** claimed in the prototype (data assumptions not fully met).

### 8. Missing or stale portfolio data?
Surfaced as a **data-quality** factor. Summaries warn; we do not invent valuations or imply distress from missing feeds alone.

### 9. Returns with contributions and withdrawals?
- **TWR:** chain-linked monthly period returns (timing-neutral vs benchmark).  
- **Modified Dietz:** approximate money-weighted return including SIP/withdrawals.  
Absolute AUM change is never treated as interchangeable with return.

### 10. Validating AI explanations?
Structured analytics are source of truth. Default summaries are **deterministic templates** restating those numbers. Optional LLM adapter is off by default and must not invent figures. Pilot metric: % of summary claims with cited source fields.

### 11. What investor information is sent to an external model?
**In this demo: none.** Deterministic templates only. Production design: no PII/portfolio payloads to external models without an approved DPA and firm policy.

### 12. Sensitive meeting transcripts?
Prototype uses a **mocked local** transcription path — no audio upload. Production: on-prem/local ASR, consent, retention limits, access audit.

### 13. Inappropriate investment recommendations?
Outputs are **advisor-review suggestions**, not trade instructions. Human approval required. SEBI IA Reg. 15(14): the adviser remains responsible for AI-assisted advice.

### 14. Monetization / workflow integration?
Position as a layer sold to RIAs/wealth platforms or embedded via CRM/PMS APIs (task push, SSO). Monetization is a proposal, not a validated business model.

### 15. What can we demonstrate today vs integrations still needed?
**Today:** React+FastAPI prototype, 220 DEMO investors, TWR/Modified Dietz, prioritization, briefs, notes, tests, research pack, deck.  
**Still needed:** live custodian/PMS feeds, CRM task sync, on-prem ASR, approved LLM, production security assessment, formal attribution.  
**Globathon Round 2:** problem-specific logic must be rebuilt during the 12-hour finale per official reuse rules.

---

## Known limitations (say out loud if asked)
- Synthetic portfolio data for investment analytics; transaction CSV is cash-flow only.
- Not SEBI/DPDP certified or production-secure.
- Attribution is simplified/qualified.
- Productivity gains not measured — pilot plan only.
