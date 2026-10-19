# Advisor Pulse — Globathon 2026 Pitch Package

**Primary deliverable:** [`Globathon_Advisor_Dynamic_Summary.pptx`](./Globathon_Advisor_Dynamic_Summary.pptx)

Product: **Advisor Pulse** — AI-powered investor intelligence & action-prioritization layer for the Globathon FinTech problem *Advisor Dynamic Summary* (“Where does this client stand?”).

---

## What’s in this folder

| File | Purpose |
|---|---|
| `Globathon_Advisor_Dynamic_Summary.pptx` | Editable ideation deck (~12 content slides + appendix) |
| `speaker_notes.md` | Talk track per slide + finale cut |
| `judge_qa.md` | Anticipated judge questions with honest answers |
| `slide_sources.md` | Citations, screenshot provenance, demo metrics |
| `screenshots/` | Prototype captures used in the deck |
| `README.md` | This file |

Related research (citations backbone):

- `research/ppt/fintech_research.md`
- `research/ppt/competitor_matrix.md`

Generator script (does **not** write outside `deliverables/ppt/` for the PPTX):

- `scripts/generate_ppt_deck.py`

---

## How to open the PowerPoint

1. Open File Explorer → `E:\Globathon\deliverables\ppt\`
2. Double-click `Globathon_Advisor_Dynamic_Summary.pptx`
3. Or from PowerShell:

```powershell
Start-Process "E:\Globathon\deliverables\ppt\Globathon_Advisor_Dynamic_Summary.pptx"
```

Requires Microsoft PowerPoint, LibreOffice Impress, or Google Slides (upload). Editable via `python-pptx` regeneration.

---

## Regenerate the deck

```powershell
cd E:\Globathon
python scripts\generate_ppt_deck.py
```

- Prefers live API metrics from `http://127.0.0.1:8000` when healthy.
- Falls back to recomputing from the DEMO data store (read-only import of backend analytics modules).
- Embeds screenshots from `deliverables/ppt/screenshots/` (falls back to `deliverables/prototype_screenshots/`).

---

## Slide structure

1. Product & promise  
2. Problem  
3. Why current workflows insufficient  
4. Solution (Detect→Explain→Prioritize→Prepare→Act→Learn)  
5. How it works technically  
6. 20-vs-200  
7. Product walkthrough (real screenshots)  
8. Demo: Priya + contrast Arjun  
9. Trust & privacy  
10. Competitive positioning  
11. Validation & roadmap  
12. Closing  
- Appendix A: Finale 2–4 slide cut  
- Appendix B: Principal sources  

---

## Globathon notes (verified / labeled)

- Round 1 ideation online; Round 2 = 12-hour offline coding (Pune) — see official rulebook.  
- React for web; Flutter for mobile; any backend.  
- Round 2 pitch PPT is **2–4 slides**; this ideation deck is fuller (10–12 + appendix).  
- Problem-specific code must be built during Round 2; Globatech retains IP of submissions (official rulebook).  
- Prefer official site dates (homepage Final Round listed Saturday **15 Nov 2026**); note any secondary-source date conflicts in research.

Sources: https://globathon.globatech.net/ · https://globathon.globatech.net/rulebook

---

## Visual system

- Dark navy / charcoal backgrounds (`#0B1220`, panels `#162033`)
- Teal accents (`#2DD4BF`)
- DEMO / SYNTHETIC labels on metrics and screenshots

---

## Scope confirmation

This pitch package **does not** modify frontend, backend, schemas, datasets, or env configs. Screenshots were captured from an already-running prototype when available; no app changes were made to obtain them.
