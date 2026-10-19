# Slide Sources & Asset Map

**Deck:** `deliverables/ppt/Globathon_Advisor_Dynamic_Summary.pptx`  
**Generator:** `scripts/generate_ppt_deck.py`  
**Generated:** 17 October 2026

---

## Slide index

| # | Title | Key claims / metrics | Citations / notes |
|---|---|---|---|
| 1 | Product & promise | 220 DEMO clients; need-review + Critical/High counts from demo engine | Computed DEMO metrics; not real investors |
| 2 | Problem | Attention doesn't scale; Cerulli 64% AI reduced admin | Cerulli press release 9 Sep 2026 (n=68 RIAs) |
| 3 | Why workflows insufficient | CRM vs research/risk vs missing attention loop | Salesforce / Morningstar / Aladdin product pages |
| 4 | Solution | Detect→Explain→Prioritize→Prepare→Act→Learn | Product thesis |
| 5 | How it works | Analytics → priority → template summary; human gate | Data honesty: txn CSV vs SYNTHETIC portfolio; SEBI 15(14) |
| 6 | 20 vs 200 | Prep for known clients; proactive long-tail | Illustrative book; II/Cerulli capacity context |
| 7 | Product walkthrough | Overview + Attention screenshots | **REAL PROTOTYPE** screens |
| 8 | Demo Priya + Arjun | Priya Critical / Arjun On Track suppress | **REAL PROTOTYPE** screens + computed metrics |
| 9 | Trust & privacy | SEBI 15(14)/18(9); DPDP design; no false compliance | SEBI PDFs; MeitY DPDP 2023 PDF |
| 10 | Competitive positioning | Capability matrix | research/ppt/competitor_matrix.md |
| 11 | Validation & roadmap | Built / needs / pilot plan | Globathon Round 2 reuse rule |
| 12 | Closing | Promise restatement | — |
| A | Finale 2–4 slide cut | Mapping to slides 1,4,8,9/12 | Official rulebook Round 2 PPT length |
| B | Principal sources | URL list | Full research file |

---

## Screenshot provenance

| File under `deliverables/ppt/screenshots/` | Provenance | Notes |
|---|---|---|
| `01_overview.png` / `overview.png` | **REAL PROTOTYPE** | Captured from http://127.0.0.1:5173/ (Advisor Overview with live DEMO KPIs) |
| `04_attention_queue.png` / `attention_queue.png` | **REAL PROTOTYPE** | Attention Prioritization — ranked clients (Priya #1 Critical) |
| `02_priya_investor.png` / `investor_summary.png` | **REAL PROTOTYPE** | DEMO-INV-001 Priya Sharma Critical summary |
| `03_arjun_contrast.png` / `advisor_pulse_arjun_contrast.png` | **REAL PROTOTYPE** | DEMO-INV-002 Arjun Mehta On Track contrast |
| `meeting_prep.png` | **REAL PROTOTYPE** (sibling folder / merge) | Meeting brief screen when API available |
| Any future `*_mockup.png` | CONCEPT MOCKUP | Must be labeled on-slide; never presented as live feature |

Also mirrored from `deliverables/prototype_screenshots/` when present (other thread). Prefer ppt folder copies for the deck generator.

---

## Demo metrics used on slides (computed 17 Oct 2026)

Source: backend data store recompute (API may be unavailable / 500 due to numpy serialization — **not fixed by this pitch thread**).

| Metric | Value |
|---|---|
| Total DEMO clients | 220 |
| Need review | 16 |
| Critical / High / Monitor / On Track | 1 / 15 / 82 / 122 |
| High-visibility / Long-tail | 20 / 200 |
| Priya Sharma | Critical, score 78, path −20.9%, portfolio ₹72.0L, active −12.06 pp |
| Arjun Mehta | On Track, score 0, path +1.8%, portfolio ₹114.0L, active +2.98 pp; planned withdrawal suppression |

---

## How to regenerate

```powershell
cd E:\Globathon
python scripts/generate_ppt_deck.py
```

Output overwrites only `deliverables/ppt/Globathon_Advisor_Dynamic_Summary.pptx`.
