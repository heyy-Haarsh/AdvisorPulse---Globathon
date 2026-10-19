# Advisor Pulse — Globathon 2026 FinTech

**AI-powered advisor intelligence platform** for investment advisors.

> *Where does this client stand?*

**Detect → Prioritize → Explain → Recommend a review action → Record the decision → Track the outcome**

Advisor Pulse is an **investor-intelligence and action-prioritization layer** — not another CRM or chart-only dashboard. It helps advisors cover the long tail of a client book while still preparing high-quality conversations for known relationships.

---

## Quick start

### 1. Generate / refresh demo data (optional)

```bash
python data/generate_synthetic.py
python data/validate_data.py
```

### 2. Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

- Health: http://127.0.0.1:8000/api/health  
- Docs: http://127.0.0.1:8000/docs  

### 3. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173/

### 4. Meeting Intelligence (Gemini)

```bash
# Project root or backend/.env
copy .env.example .env
# Set GEMINI_API_KEY=...

```

Nav: **Meeting Intelligence**. Prep briefs work without Gemini (deterministic analytics). Audio transcription and MoM generation require `GEMINI_API_KEY`. Recordings store under `data/runtime/recordings/` (not publicly served).

### 5. Tests

```bash
python -m pytest backend/tests -q
```

---

## Navigation

| Screen | Role |
|---|---|
| **Overview** | Command center + Attention Engine queue (review / dismiss / follow-up) |
| **Clients** | Searchable directory + evidence-backed profiles |
| **Meetings & Memory** | Pre-meeting pack, notes, mocked local transcription, commitments |
| **Meeting Intelligence** | Gemini-backed prep → record/upload → transcript → MoM → approve → commitments |
| **Insights** | Cross-client pattern cohorts + Layer-1 cash-flow signals |
| **Settings** | Weights, thresholds, privacy posture, audit log |

Contextual panels (not separate nav tabs): **Copilot**, evidence/confidence badges, what-if simulator, drift actions, timeline/feedback.

UI: light Zarss-inspired workspace (dark sidebar, pastel KPI cards, soft panels).

---

## Features implemented

All twelve differentiators below are wired end-to-end on the demo stack (API feature flags on `/api/health`).

### 1. AI Client Attention Engine
- Ranks the full DEMO book (~220 clients) with a **configurable, explainable weighted score**
- Factors include goal deviation, active underperformance, time-to-goal urgency, overdue follow-ups, stale reviews, and data-quality flags
- Shows **severity vs confidence**, supporting evidence, and factor point breakdowns
- Advisors can **Mark reviewed / Follow-up / Dismiss**; decisions persist so resolved items stop dominating the queue
- Filters by priority and tier (high-visibility vs long-tail)

### 2. Advice-to-Outcome Intelligence
- Structured advice history with original recommendation, intended outcome, and follow-up status
- Deterministic comparison of expected vs actual where valuation/return data exists
- Returns **Insufficient data** instead of inventing results when inputs are missing
- Historical advice is treated as immutable demo records (not overwritten by new notes)

### 3. Evidence-Backed Dynamic Client Summary
- 10-part structured summary on each client profile (position, changes, goals, performance, advice, notes, priority reasons, questions, next steps, etc.)
- Every part can expand into **evidence**: sources, dates, confidence, missing fields, limitations

### 4. Private Advisor Memory
- Manual notes add/view/edit (runtime notes)
- **Mocked local** transcription path (clearly labeled — no audio upload)
- Structured extractions from notes/transcripts require **advisor confirmation** before becoming authoritative
- Confirmed items can feed commitments / attention follow-ups

### 5. Hidden Financial Drift Detector
- Deterministic multi-signal rules (e.g. allocation drift + risk mismatch, overdue review + unresolved advice)
- Missing data is marked unavailable — **not** treated as financial distress
- Advisors can confirm / dismiss / resolve alerts

### 6. Multi-Agent Financial Analysis
- Modular agents: Portfolio, Goal, Cash-Flow, Advice Outcome, Client Context, plus Insight Verification
- Coordinator merges findings; verification rejects unsupported claims
- Financial numbers remain **deterministic** (not LLM-invented)

### 7. Natural-Language Advisor Copilot
- Contextual assistant maps questions → **validated analysis functions** only
- No arbitrary SQL; no invented metrics
- Returns citations / evidence; optional `accessible_clients` ACL in Settings

### 8. Financial What-If Simulator
- Interactive SIP / contribution scenario on the client profile
- Explicit formulas; baseline vs alternative; assumptions disclosed
- Outputs labeled **Hypothetical** — not advice or guaranteed returns

### 9. Cross-Client Pattern Discovery
- Insights page with explainable cohorts (counts, rule definition, drill-down to clients)
- Layer-1 transaction cash-flow signals kept separate from portfolio returns

### 10. AI Meeting Preparation & Follow-Through
- Pre-meeting brief from structured client data
- Post-meeting draft actions that require confirmation
- Open commitments tracked and linked back into the workflow

### 11. AI Confidence & Hallucination Guard
- Shared evidence layer: **Verified / Limited / Insufficient**
- Used across attention, summaries, agents, copilot, and patterns
- Important claims must be traceable; otherwise the system declines to assert them as fact

### 12. Advice Memory & Outcome Feedback Loop
- Chronological client timeline (advice, notes, observations, evaluations)
- Advisors can confirm / dismiss / correct generated insights
- Tracks association over time **without claiming false causality**

### P0 — Judge-facing proof chain (Detect → Prioritize → Explain → Act → Record → Track)

#### Blind Spot Radar
- Overview **Attention Engine → Blind Spot Radar** tab: attention need × review obscurity
- Segment filter **less-observed** surfaces overlooked long-tail clients (seeded hero: **Diya Iyer / DEMO-INV-L017**)
- Click opens factor evidence + **Next Best Review Action** pack

#### Alert Quality Lab
- Insights → **Alert Quality Lab** (`/insights/alert-quality`)
- Computed Precision@10/20, Recall@20, false-positive rate, evidence coverage on labeled DEMO scenarios
- Side-by-side Pulse vs CRM-ish baseline (high-visibility + stale review date)
- Explicit non-goal: no fabricated “94% precision” — only metrics from `data/eval/labeled_scenarios.json`

#### Next Best Review Action
- Unified pack API: verified facts, why escalated, questions, missing info, suggested action enum
- Wired in Overview drawer, Client profile header, and Meetings page
- Accept/edit/reject → commitment + attention decision + timeline; client message stays **draft** until approve

### P1 — Transaction Data Quality + correctness

#### Transaction DQ pipeline
- Dirty fixture `data/sample_transactions_dirty.csv` (currency amounts, DD-MM-YYYY, duplicates, missing fields)
- Insights → **Data Quality**: Upload → Validate → Exception review → Import → refresh Layer-1 signals
- UI disclaimer: cash-flow layer **not** linked to `DEMO-INV-*` portfolios; not spending baselines or distress

#### QuantStats cross-check + verification gate
- Optional QuantStats (Apache-2.0) on DEMO monthly returns only — Client performance cross-check panel
- Native drawdown/vol/Sharpe fallback if package absent
- Agent verification rejects fabricated numeric claims without sources

### Supporting platform capabilities
| Area | Status |
|---|---|
| Synthetic DEMO portfolio universe (goals, holdings, returns, advice) | Implemented & labeled |
| Transaction CSV ingestion (normalize, flag duplicates, invalid dates/amounts) | Implemented |
| Validate → Review → Import DQ pipeline | Implemented |
| TWR + Modified Dietz return methods | Implemented |
| Goal expected-path vs actual deviation | Implemented |
| Demo narrative: Priya (Critical) vs Arjun (not escalated) vs Diya (blind spot) | Implemented |
| Alert Quality Lab labeled eval set | Implemented |
| Local runtime persistence (`data/runtime/`) | Implemented |
| Pitch deck & research pack | `deliverables/ppt/`, `research/` |

---

## Demo walkthrough (judge path)

1. **Overview → Attention Engine → Blind Spot Radar** — switch segment to **less-observed** → overlooked long-tail **Diya Iyer** near top with evidence.
2. Open **Next Best Review Action** pack — evidence, confidence, missing data; contrast **Arjun Mehta** (planned withdrawal → not escalated / clarify context).
3. **Accept** the pack → commitment + decision recorded (message remains draft until approve).
4. **Insights → Alert Quality Lab** — Precision@20 / Recall@20 / FP handling vs CRM baseline on labeled DEMO (n from fixture).
5. Optional: **Insights → Data Quality** — validate dirty CSV → exception review → import → signals refresh (Layer-1 disclaimer).
6. Classic path: Priya Critical profile, Meetings prep, Settings weights, copilot *“Why is DEMO-INV-001 critical?”*

---

## Architecture

| Path | Purpose |
|---|---|
| `backend/analytics/` | Portfolio / goal / TWR / Modified Dietz / QuantStats bridge |
| `backend/prioritization/` | Attention scoring |
| `backend/services/` | Blind spot, review action, txn quality, drift, meetings, copilot, … |
| `backend/eval/` | Alert Quality Lab metrics |
| `backend/agents/` | Modular analysis agents + verification coordinator |
| `backend/domain/` | Evidence schemas + runtime persistence |
| `backend/ingestion/` | Transaction CSV pipeline |
| `data/` | Synthetic DEMO CSVs + sample / dirty transactions |
| `data/eval/` | Labeled alert-quality scenarios |
| `data/runtime/` | Decisions, notes, feedback, settings, audit, staged txns |
| `frontend/src/pages/` | Overview, Clients, MeetingsMemory, Insights, AlertQualityLab, Settings |
| `deliverables/ppt/` | Pitch deck + speaker notes + judge Q&A |

**Data honesty:** Portfolio analytics use clearly labeled `DEMO-` / `is_demo=true` records. The transaction CSV supports **cash-flow signals only** and is never treated as investment returns.

**Positioning:** Advisor Pulse is the intelligence layer above CRM/PMS: it finds clients drifting from goals—including those not regularly reviewed—explains the evidence, and converts that into a tracked review action.

---

## How to enhance this further

Prioritized roadmap from “hackathon-ready” to “pilot-ready.” P0 Blind Spot / Alert Lab / Next Action items above are **implemented** for the demo.

### Near-term (1–2 sprints)

1. **Real custodian / PMS / CRM connectors**  
   Replace synthetic holdings, valuations, and advice with read-only feeds (e.g. portfolio APIs, Salesforce tasks). Keep the attention + evidence layer as the product surface. (OpenBB-style adapter sketch: fetch→normalize→timestamp→analytics — docs only for now.)

2. **Production authentication & RBAC**  
   Replace demo single-user auth with SSO / firm login, advisor–client entitlements, and audit that is reviewable by compliance.

3. **Alert quality loop**  
   Measure advisor-confirmed precision, false-positive rate, and time-to-review. Tune default weights from observed dismissals (still keep scores explainable).

4. **Richer advice-outcome attribution**  
   When security-level returns and beginning weights exist, add qualified Brinson-style or holdings contribution views — still decline when data is incomplete.

5. **Meeting workflow polish**  
   Calendar integration, one-click “schedule follow-up,” and CRM task push for confirmed commitments.

### Medium-term

6. **True on-device / on-prem ASR**  
   Wire Whisper.cpp, Vosk, or firm-approved speech stack behind the existing transcription interface. Keep consent, retention, and “local vs remote” labels honest.

7. **Approved LLM summarization under a DPA**  
   Optional paraphrase of *already computed* structured facts. Never let the model invent portfolio values. Prefer private/VPC models for Indian IA data.

8. **Household & multi-goal support**  
   Map clients to households, multiple goals per investor, and joint accounts in prioritization.

9. **Mobile companion (Flutter)**  
   Globathon allows Flutter for mobile — a lightweight attention inbox + meeting prep view for advisors on the go.

10. **Pilot instrumentation**  
    Track: review prep time, % alerts validated, missed material events in retrospective tests, summary evidence coverage. Publish only measured results.

### Longer-term / research

11. **Pattern discovery beyond rules**  
    Clustering or anomaly detection *only* after labeled validation sets exist; keep rule-based cohorts as the default explainable baseline.

12. **Goal-path Monte Carlo / cash-flow planning**  
    Stochastic projections with clear uncertainty bands — always hypothetical, never “suitability” automation.

13. **Compliance packs for SEBI IA + DPDP**  
    AI-use disclosure templates, retention policies, DPIA checklist, and data-processing agreements for any external model. Prototype today is **not** certified.

14. **Multi-firm / multi-tenant SaaS**  
    Isolation, encryption at rest, key management, and regional data residency suitable for Indian wealth platforms.

### Product principles to preserve while enhancing

- Analytics first, language second — **no LLM-invented numbers**
- Explain every alert — severity ≠ confidence ≠ data quality
- Human approval before consequential memory or client outreach
- Long-tail attention is the core incremental value vs CRM/PMS alone
- Label synthetic / hypothetical / insufficient data explicitly

---

## Privacy (honest)

- **Auth is demo-level** (`DEMO-ADV-USER-01`). Copilot can enforce optional `accessible_clients` in Settings.
- Transcription is **mocked/local only** — no audio upload.
- Audit log records actions without dumping note/transcript PII.
- **Not** production-secure, SEBI-compliant, or DPDP-certified without a proper assessment.

Relevant design references (not certifications): SEBI IA Reg. 15(14) / 18(9) AI responsibility & disclosure; DPDP Act 2023 purpose limitation & consent themes.

---

## Globathon notes

- Official web stack constraint: **React** (backend unrestricted)
- Round 2 may require rebuilding problem-specific logic during the onsite coding window — treat this repo as ideation + reference architecture; confirm current rulebook
- Pitch materials: `deliverables/ppt/Globathon_Advisor_Dynamic_Summary.pptx`
- Rulebook: https://globathon.globatech.net/rulebook

---

## Team placeholders

- [Name 1] · [Name 2] · [Name 3] · [Name 4]
