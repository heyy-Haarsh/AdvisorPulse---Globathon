# Advisor Pulse — FinTech Research File (Pitch Deck Edition)

**Product working name:** Advisor Pulse  
**Problem:** Globathon 2026 FinTech — Advisor Dynamic Summary (*Where does this client stand?*)  
**Research date:** 17 October 2026  
**Deck path:** `deliverables/ppt/Globathon_Advisor_Dynamic_Summary.pptx`  
**Status:** Sources examined via official pages/PDFs where accessible. Claims below are labeled as verified, secondary-sourced, hypothesis, or design assumption.

> **Pitch-package note:** This file under `research/ppt/` is the research backbone for the ideation deck. It synthesizes (and where needed updates) `research/fintech_research.md` for slide citations. Do not invent stats; label assumptions.

---

## 1. Globathon 2026 — Official Requirements

### Primary source (authoritative)

| Field | Detail |
|---|---|
| Title | Globathon Quest Log (Rulebook) |
| Publisher | Globatech |
| URL | https://globathon.globatech.net/rulebook |
| Examined | 17 Oct 2026 (interactive rulebook sections expanded in browser) |

**Verified findings from official rulebook:**

1. **Format:** Two rounds — Round 1 Ideation (online submission via website); Round 2 Coding (offline, Globatech office, Pune).
2. **Team & eligibility:** Max 4 members; open to all college students; one team per participant; cross-college teams allowed.
3. **Round 1 submission must cover:** Problem statement; proposed solution; target audience & impact; key features & tech stack (Mobile/Web + backend); implementation plan & feasibility. Late submissions not accepted.
4. **Tech stack constraints:** Flutter for mobile; **React for web**; backend technology unrestricted.
5. **Round 2 (official site timeline on homepage: Saturday 15 Nov; rulebook Round 2 section lists Saturday 31 Oct — treat official site pages as primary and note the date discrepancy):** 12 hours; Mobile or Web app; Flutter/React accordingly; backend any; AI coding assistants allowed if reviewed/tested and major AI tools disclosed; open-source allowed with acknowledgment.
6. **Round 2 deliverables:** Working prototype/demo; source code (packaged & documented); run/deploy instructions; short demo presentation (**PPT, 2–4 slides** for the live pitch); live demo + Q&A.
7. **Reuse rule (critical):** Generic boilerplate/templates/libraries allowed, but **problem-specific solution, features, business logic, and integrations must be developed during the coding round**. Previously completed solutions to the problem statement are prohibited.
8. **IP:** Submitted code, prototypes, and ideas must be provided to Globatech for evaluation; **Globatech retains full ownership and rights** to submitted materials.
9. **Conduct:** Own laptops; internet provided; respectful conduct; plagiarism/unauthorized collaboration/pre-completed problem solutions → disqualification.

### Official homepage timeline (cross-check)

| Field | Detail |
|---|---|
| Title | Globathon |
| Publisher | Globatech |
| URL | https://globathon.globatech.net/ |
| Examined | 17 Oct 2026 |

Homepage milestones include: Kickoff 23 Sep 2026; Registrations open (Now); Idea Submission Starts (TBA); Registrations Close **08 Nov 2026**; Idea Submission Deadline (TBA); Finalist Announcement (TBA); Final Round **Saturday, 15 Nov**.

**Note:** Secondary aggregators (StartupGrantsIndia, Hackathon Radar) list different Round 1 window (5–11 Oct 2026) and finale (31 Oct 2026). Prefer official Globatech pages; record secondary dates as **unverified relative to official SPA content**.

### Round 1 judging criteria (secondary)

| Field | Detail |
|---|---|
| Title | Globathon (2026): Results & Updates |
| Publisher | StartupGrantsIndia |
| URL | https://www.startupgrantsindia.com/competitions/globathon |
| Examined | 17 Oct 2026 |

Reported Round 1 criteria: **innovation, feasibility, technical approach, impact, clarity of presentation**; top ~10–12 teams shortlisted. Prize pool ₹50,000; PPI/PPO opportunities. **Label as secondary** — not copied verbatim from official rulebook accordion text.

### Implications for this repository

- Build a **React web** prototype (matches stack constraint).
- Produce a polished deck for ideation quality (10–12 slides) plus a **2–4 slide finale cut** if needed.
- Treat this build as **Round 1 ideation evidence + reference architecture**; for Round 2, problem-specific logic must be re-implemented during the 12-hour window per official reuse rules.
- Disclose major AI tools used.

---

## 2. Problem framing — Advisor Dynamic Summary

**Core question:** *Where does this client stand?*

Required advisor answers (product thesis):

1. Where does the investor stand today?
2. Is the investor on track vs stated goals?
3. What explains expectation-versus-actual gaps?
4. Why does this investor need attention *now*?
5. What should the advisor review or do next?

**Hypothesis (not surveyed locally):** Advisors already have CRMs and portfolio tools, but context is fragmented across holdings, goals, past advice, notes, and cash-flow signals — making continuous, explainable prioritization across a large book difficult.

---

## 3. Industry evidence (advisor capacity & AI)

### Cerulli — technology & productivity (verified press release, 2024)

| Field | Detail |
|---|---|
| Title | Financial Advisor Practices that Embrace Technology Surge in Productivity and Efficiency |
| Publisher | Cerulli Associates |
| URL | https://www.cerulli.com/press-releases/financial-advisor-practices-that-embrace-technology-surge-in-productivity-and-efficiency |
| Examined | 17 Oct 2026 |

**Verified claims:** Nearly **30%** of heavy technology users are higher-growth practices over the most recent three-year period vs **9%** of light users; heavy users show better clients-per-staff productivity metrics. Top efficiency tools cited: e-signature (65%), CRM (44%), video conferencing (29%). Adoption barriers include compliance restrictions (73%), lack of integration (71%), insufficient time to learn/implement (70%).

### Cerulli — AI expands capacity (verified press release)

| Field | Detail |
|---|---|
| Title | Advisor Headcount Set to Grow as AI Expands Capacity |
| Publisher | Cerulli Associates (with Vista Equity Partners) |
| Date | 9 September 2026 |
| URL | https://www.cerulli.com/press-releases/advisor-headcount-set-to-grow-as-ai-expands-capacity |

**Verified claims:**

- Survey of **68 RIA firms** (May–July 2026); ~$1.2T aggregate AUM.
- **64%** report AI reduced manual/administrative work; **46%** cite improved client-communication quality.
- Firms expect to add junior advisors (73%), CSAs (67%), senior advisors (56%) over next two years — AI framed as **capacity expansion**, not headcount replacement.
- Quote (Asher Cheses, Cerulli): firms succeed by automating admin work and freeing time for planning/relationship conversations.

### Cerulli — advisor capacity / client load (secondary + Institutional Investor summary)

| Field | Detail |
|---|---|
| Title | ‘Non-Ideal’ Clients Present Productivity Challenge for Advisors |
| Publisher | Institutional Investor (reporting Cerulli) |
| URL | https://www.institutionalinvestor.com/article/2bktrtd7h31nqi90pv7cw/ria-intel/non-ideal-clients-present-productivity-challenge-for-advisors |

Reported (via Institutional Investor summarizing Cerulli): advisors are effective around ~**100 clients**; senior advisors serve ~**160**; **29%** of senior advisors manage **>200** clients. Serving too many clients ranks as a top challenge.

| Field | Detail |
|---|---|
| Title | Constrained by Resources and Time, Advisors Need to Choose Their Clients Wisely |
| Publisher | Cerulli Associates press page / related press-release title |
| URL | https://www.cerulli.com/press-releases/constrained-by-resources-and-time-advisors-need-to-choose-their-clients-wisely |
| Note | Direct fetch on 17 Oct 2026 redirected to general press listing; earlier index snippet cited average **142 clients per producing advisor** and **69%** of advisors believe they can better use existing tech. Treat those figures as **snippet-attested pending full press-release body verification**. |

**Implication for 20 vs 200:** Incremental value is strongest in scaling high-quality review across the long tail while still supporting meeting prep for known high-touch clients. All client-book numerics in the deck are **illustrative** unless citing Cerulli figures above.

---

## 4. Competitive landscape (fair, evidence-based)

See also `competitor_matrix.md`.

### Salesforce Financial Services / Agentforce for Wealth

| Field | Detail |
|---|---|
| Title | Wealth Management Software for Financial Advisors |
| Publisher | Salesforce |
| URL | https://www.salesforce.com/financial-services/wealth-management-software/ |
| Examined | 17 Oct 2026 |

**Verified marketing claims:** Unified household/CRM view; pre-built AI agents for meeting prep, briefs, call transcription, CRM tasks; personalized daily briefing (priorities, at-risk clients, life events, market triggers); goals/life-event centralization; integration with portfolio/custodial systems.

### Morningstar Advisor Workstation

| Field | Detail |
|---|---|
| Title | Advisor Workstation |
| Publisher | Morningstar |
| URL | https://www.morningstar.com/business/brands/data-analytics/products/advisor-workstation |
| Examined | 17 Oct 2026 (partial; page load limited) |

Public positioning: investment research, proposal creation, portfolio analysis for advisory firms. Support site describes modules for clients/portfolios, scenario building, portfolio/security reports. SoftwareAdvice (secondary) lists alerts, integrations with Salesforce Sales Cloud and Redtail — **secondary**.

### BlackRock Aladdin Wealth

| Field | Detail |
|---|---|
| Title | Wealth Management Services \| Aladdin by BlackRock |
| Publisher | BlackRock |
| URL | https://www.blackrock.com/aladdin/platforms/solutions/aladdin-wealth |
| Examined | 17 Oct 2026 (via search + official product pages) |

**Verified product positioning:** Whole-portfolio risk analytics; risk monitoring/alerts/outliers across book; model management & scaled rebalancing; proposal generation; stress testing; next-best-action / opportunity management; compliance/risk oversight. Enterprise-oriented.

### Yodlee / Envestnet (starting point)

| Field | Detail |
|---|---|
| Title | Yodlee (Envestnet) — account aggregation (starting point only) |
| URL | https://www.yodlee.com/ |
| Status | Not deeply product-dissected in this pass. Treat as **data-aggregation incumbent**, not a full advisor-attention copilot. |

**Differentiation thesis (product claim, not competitor denial):** Incumbents excel at CRM, research, risk, or portfolio construction in silos. Advisor Pulse targets the **cross-context attention workflow**: goal path vs actual + explainable drivers + transparent prioritization + evidence-linked briefs + human-approved actions — especially for clients outside daily attention — without replacing CRM/PMS.

---

## 5. Indian regulatory & privacy context

### SEBI Investment Advisers Regulations — AI & confidentiality

| Field | Detail |
|---|---|
| Title | Securities and Exchange Board of India (Investment Advisers) Regulations, 2013 (amended text) |
| Publisher | SEBI |
| URL (PDF examined) | https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/1785912187595.pdf |
| Related Master Circular PDF | https://www.sebi.gov.in/sebi_data/attachdocs/jun-2025/1751022988074.pdf |

**Verified (from IA Regulations PDF text):**

- IA shall not divulge confidential client information without prior permission, except as required by law.
- **Reg. 15(14):** An IA who uses AI tools (any scale) is **solely responsible** for security, confidentiality, integrity of client data; use of data to arrive at advice; advice based on AI output; and legal compliance.
- Records (KYC, advice-related) preserved minimum **five years** (physical or electronic).

**Verified (Master Circular guidance text):** Disclose to clients the **extent of AI use** in providing investment advice (Reg. 18(9) referenced in master circular).

**Design implication:** Advisor Pulse outputs are **advisor-review suggestions**, not autonomous trade instructions; AI use must be disclosable; client data must not leave approved processing boundaries.

### Digital Personal Data Protection Act, 2023 (DPDP)

| Field | Detail |
|---|---|
| Title | Digital Personal Data Protection Act, 2023 |
| Publisher | Ministry of Law and Justice / MeitY publication |
| URL | https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf |
| Examined | 17 Oct 2026 |

**Verified themes relevant to design (not legal advice):** Consent for processing personal data must be free, specific, informed, unconditional, unambiguous; purpose limitation; Data Fiduciary obligations for security; rights including access/correction/erasure/withdrawal of consent (subject to law). Legitimate-use exceptions exist for certain legal/enforcement contexts — **not** a free pass for product analytics.

**Design considerations (not claimed compliance):** data minimization; purpose-bound processing; encryption in transit/at rest in production; audit trails; retention/deletion policies; no sending sensitive investor data to external models without approved DPA; local/mock transcription path.

**Honesty constraint:** This prototype is **not** claimed SEBI-compliant, DPDP-certified, or production-secure.

### NIST (security design reference)

| Field | Detail |
|---|---|
| Title | NIST cybersecurity / privacy frameworks (starting point) |
| URL | https://www.nist.gov/ |
| Use | High-level design reference for encryption, access control, audit — **not** a certification claim. |

---

## 6. Data strategy implications

The sample transaction CSV schema (`transaction_id, user_id, date, time, description, category, amount, currency, type, payment_mode, city`) supports **cash-flow / spending signals only**. It does **not** contain holdings, valuations, returns, goals, risk profiles, benchmarks, advice history, or advisor notes.

**Mandatory split:**

- **Layer 1:** Real/sample transactions → normalized cash-flow analytics only.
- **Layer 2:** Explicitly labeled **DEMO / SYNTHETIC** portfolio universe for goal/performance/prioritization demos.
- Never blend synthetic returns with real transactions as if they were one investor’s true performance.

---

## 7. Assumptions (explicit)

| ID | Assumption | Type |
|---|---|---|
| A1 | Target users are SEBI-registered IAs / wealth advisors or similar professionals in India (or analogous markets). | Design assumption |
| A2 | Advisors already use some CRM + portfolio reporting stack. | Hypothesis |
| A3 | Greatest incremental value is long-tail coverage + explainable prioritization, not replacing Aladdin/Morningstar analytics depth. | Product thesis |
| A4 | Illustrative book of ~220 demo clients (20 high-visibility + 200 long-tail) is for UX storytelling only. | Illustrative |
| A5 | Round 1 benefits from a working demo; Round 2 requires rebuilding problem-specific logic on-site. | Official-rule implication |
| A6 | Deterministic template summaries are acceptable when no LLM API key is present. | Engineering choice |

---

## 8. Product implications checklist

- Answer the five investor questions with **structured analytics first**, NL summary second.
- Transparent priority factors (not opaque AI score).
- Evidence + timestamps + data-confidence + missing-data warnings.
- Human-in-the-loop recommendations only.
- Security architecture on slides; no false compliance claims.
- Cite sources on slides with short footnotes.
- React + FastAPI prototype; screenshots from real app for the deck.

---

## 9. Source index (quick list)

1. https://globathon.globatech.net/ — Globatech, homepage, examined 17 Oct 2026  
2. https://globathon.globatech.net/rulebook — Globatech, rulebook, examined 17 Oct 2026  
3. https://www.startupgrantsindia.com/competitions/globathon — secondary event summary  
4. https://www.cerulli.com/press-releases/advisor-headcount-set-to-grow-as-ai-expands-capacity — Cerulli, 9 Sep 2026  
5. https://www.institutionalinvestor.com/article/2bktrtd7h31nqi90pv7cw/ria-intel/non-ideal-clients-present-productivity-challenge-for-advisors — Institutional Investor / Cerulli summary  
6. https://www.salesforce.com/financial-services/wealth-management-software/ — Salesforce  
7. https://www.morningstar.com/business/brands/data-analytics/products/advisor-workstation — Morningstar  
8. https://www.blackrock.com/aladdin/platforms/solutions/aladdin-wealth — BlackRock Aladdin Wealth  
9. https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/1785912187595.pdf — SEBI IA Regulations PDF  
10. https://www.sebi.gov.in/sebi_data/attachdocs/jun-2025/1751022988074.pdf — SEBI IA Master Circular PDF  
11. https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf — DPDP Act 2023  
12. https://www.sebi.gov.in/ — SEBI portal (context)  
13. https://www.nist.gov/ — NIST (design reference)  
