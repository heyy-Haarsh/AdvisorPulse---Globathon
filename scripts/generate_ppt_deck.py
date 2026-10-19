"""
Generate deliverables/ppt/Globathon_Advisor_Dynamic_Summary.pptx
for Advisor Pulse (Globathon 2026 FinTech — Advisor Dynamic Summary).

Writes ONLY under deliverables/ppt/. Does not modify frontend/backend/data.
Uses live API metrics when available; falls back to recomputing from DEMO data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "deliverables" / "ppt"
OUT = OUT_DIR / "Globathon_Advisor_Dynamic_Summary.pptx"
SHOTS = OUT_DIR / "screenshots"
# Prefer ppt screenshots; also allow sibling prototype_screenshots as fallback
ALT_SHOTS = ROOT / "deliverables" / "prototype_screenshots"

sys.path.insert(0, str(ROOT / "backend"))

NAVY = RGBColor(0x0B, 0x12, 0x20)
PANEL = RGBColor(0x16, 0x20, 0x33)
PANEL2 = RGBColor(0x1C, 0x2A, 0x40)
TEAL = RGBColor(0x2D, 0xD4, 0xBF)
WHITE = RGBColor(0xE8, 0xEE, 0xF8)
MUTED = RGBColor(0x94, 0xA3, 0xB8)
ACCENT2 = RGBColor(0x3B, 0x82, 0xF6)
CRIT = RGBColor(0xF8, 0x71, 0x71)
OK = RGBColor(0x34, 0xD3, 0x99)
AMBER = RGBColor(0xFB, 0xBF, 0x24)


def set_slide_bg(slide, color=NAVY):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_text(
    slide,
    left,
    top,
    width,
    height,
    text,
    size=18,
    bold=False,
    color=WHITE,
    align=PP_ALIGN.LEFT,
    font="Calibri",
):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = font
    p.alignment = align
    return box


def add_multiline(
    slide,
    left,
    top,
    width,
    height,
    lines,
    size=14,
    color=WHITE,
    bold_first=False,
    spacing=6,
):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.size = Pt(size)
        p.font.bold = bold_first and i == 0
        p.font.color.rgb = color
        p.font.name = "Calibri"
        p.space_after = Pt(spacing)
    return box


def add_footer(slide, text="Advisor Pulse · Globathon 2026 · DEMO / SYNTHETIC data · Citations on-slide"):
    add_text(slide, Inches(0.4), Inches(7.05), Inches(12.5), Inches(0.3), text, size=10, color=MUTED)


def add_cite(slide, text, top=Inches(6.65)):
    add_text(slide, Inches(0.4), top, Inches(12.5), Inches(0.4), text, size=9, color=MUTED)


def rect(slide, left, top, width, height, fill=PANEL):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    return shape


def accent_bar(slide):
    rect(slide, Inches(0), Inches(0), Inches(0.14), Inches(7.5), TEAL)


def resolve_shot(*names: str) -> Path | None:
    for name in names:
        for base in (SHOTS, ALT_SHOTS):
            p = base / name
            if p.exists() and p.stat().st_size > 1000:
                return p
    return None


def try_add_image(slide, path: Path | None, left, top, width, height=None):
    if path is None or not path.exists():
        return False
    kwargs = {"width": width}
    if height is not None:
        kwargs["height"] = height
    slide.shapes.add_picture(str(path), left, top, **kwargs)
    return True


def load_metrics():
    try:
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:8000/api/overview", timeout=3) as r:
            overview = json.loads(r.read().decode())
        with urllib.request.urlopen("http://127.0.0.1:8000/api/investors/DEMO-INV-001", timeout=3) as r:
            priya = json.loads(r.read().decode())
        with urllib.request.urlopen("http://127.0.0.1:8000/api/investors/DEMO-INV-002", timeout=3) as r:
            arjun = json.loads(r.read().decode())
        overview["_source"] = "live_api"
        return overview, priya, arjun
    except Exception:
        from analytics.portfolio import DataStore, investor_snapshot
        from prioritization.engine import overview_kpis, rank_book, score_investor
        from summaries.generator import generate

        store = DataStore.load()
        ranked = rank_book(store)
        overview = overview_kpis(ranked)
        overview["_source"] = "data_store_recompute"
        snap = investor_snapshot(store, "DEMO-INV-001")
        pri = score_investor(store, "DEMO-INV-001")
        priya = {"snapshot": snap, "priority": pri, "summary": generate(snap, pri)}
        snap2 = investor_snapshot(store, "DEMO-INV-002")
        pri2 = score_investor(store, "DEMO-INV-002")
        arjun = {"snapshot": snap2, "priority": pri2, "summary": generate(snap2, pri2)}
        return overview, priya, arjun


def build():
    overview, priya, arjun = load_metrics()
    dist = overview.get("priority_distribution", {})
    pr = priya["priority"]
    ps = priya["snapshot"]
    gp = ps["goal_progress"]
    ar_pr = arjun["priority"]
    ar_ps = arjun["snapshot"]
    ar_gp = ar_ps["goal_progress"]
    src_note = overview.get("_source", "unknown")

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # ========== 1. Product & promise ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.55), Inches(1.35), Inches(11), Inches(0.4), "ADVISOR PULSE", size=20, bold=True, color=TEAL)
    add_text(
        s,
        Inches(0.55),
        Inches(1.85),
        Inches(12),
        Inches(1.0),
        "Where does this client stand?",
        size=40,
        bold=True,
    )
    add_text(
        s,
        Inches(0.55),
        Inches(2.95),
        Inches(11.5),
        Inches(0.9),
        "AI-powered investor intelligence & action-prioritization layer —\nDetect → Explain → Prioritize → Prepare → Act → Learn",
        size=18,
        color=MUTED,
    )
    # KPI strip
    kpis = [
        (str(overview["total_clients"]), "DEMO clients"),
        (str(overview["clients_requiring_review"]), "Need review"),
        (f"{dist.get('Critical', 0)} / {dist.get('High', 0)}", "Critical / High"),
        (f"{overview['high_visibility_count']} + {overview['long_tail_count']}", "Visible + long-tail"),
    ]
    for i, (val, label) in enumerate(kpis):
        left = 0.55 + i * 3.1
        rect(s, Inches(left), Inches(4.2), Inches(2.9), Inches(1.35), PANEL)
        add_text(s, Inches(left + 0.2), Inches(4.35), Inches(2.5), Inches(0.55), val, size=26, bold=True, color=TEAL)
        add_text(s, Inches(left + 0.2), Inches(4.95), Inches(2.5), Inches(0.4), label, size=13, color=MUTED)
    add_text(
        s,
        Inches(0.55),
        Inches(5.8),
        Inches(12),
        Inches(0.4),
        "Globathon 2026 FinTech · Advisor Dynamic Summary · Team: [Name 1] · [Name 2] · [Name 3] · [Name 4]",
        size=13,
        color=MUTED,
    )
    add_cite(s, f"Metrics computed from SYNTHETIC DEMO book ({src_note}). Not real investors. Not investment advice.")
    add_footer(s)

    # ========== 2. Problem ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.3), Inches(12), Inches(0.55), "The problem: data exists — attention doesn't scale", size=28, bold=True)
    bullets = [
        ("Fragmented context", "Holdings, goals, past advice, and notes live in different systems — so “where does this client stand?” takes too long to answer."),
        ("Capacity cliff", "Advisors know their top ~20 deeply; the other ~200 rarely get proactive, evidence-backed review."),
        ("Wrong product gap", "Hypothesis: the gap is not another chart — it is continuous, explainable prioritization of whom to contact next."),
        ("Industry signal", "Cerulli (2026): 64% of surveyed RIAs say AI reduced admin work; firms use AI to expand capacity, not replace advice."),
    ]
    y = 1.05
    for title, body in bullets:
        rect(s, Inches(0.5), Inches(y), Inches(12.3), Inches(1.15), PANEL)
        add_text(s, Inches(0.75), Inches(y + 0.15), Inches(11.8), Inches(0.35), title, size=16, bold=True, color=TEAL)
        add_text(s, Inches(0.75), Inches(y + 0.5), Inches(11.8), Inches(0.5), body, size=14, color=WHITE)
        y += 1.25
    add_cite(
        s,
        "Sources: Globathon problem framing; Cerulli Associates press release, 9 Sep 2026 (AI capacity survey, n=68 RIAs). 20/200 book split = illustrative for demo storytelling.",
    )
    add_footer(s)

    # ========== 3. Why workflows insufficient ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.3), Inches(12), Inches(0.55), "Why CRM + portfolio tools still leave a gap", size=28, bold=True)
    cols = [
        ("Store & engage", "CRM (e.g. Salesforce FSC /\nAgentforce Wealth)\n\nHousehold 360, tasks,\nAI meeting prep & briefs", TEAL),
        ("Analyze & construct", "Morningstar Advisor Workstation\n· BlackRock Aladdin Wealth\n\nResearch, risk, proposals,\nrebalancing, stress tests", ACCENT2),
        ("Still missing", "Cross-context attention loop\n\nGoal path vs actual +\nexplainable why-now +\nlong-tail review queue", CRIT),
    ]
    for i, (h, body, accent) in enumerate(cols):
        left = 0.5 + i * 4.2
        rect(s, Inches(left), Inches(1.15), Inches(3.95), Inches(4.7), PANEL)
        rect(s, Inches(left), Inches(1.15), Inches(3.95), Inches(0.12), accent)
        add_text(s, Inches(left + 0.25), Inches(1.5), Inches(3.45), Inches(0.5), h, size=18, bold=True, color=accent)
        add_text(s, Inches(left + 0.25), Inches(2.2), Inches(3.45), Inches(3.3), body, size=15, color=WHITE)
    add_cite(
        s,
        "Sources: salesforce.com/financial-services/wealth-management-software; morningstar.com Advisor Workstation; blackrock.com/aladdin (Aladdin Wealth). Fair comparison — not capability denial.",
    )
    add_footer(s)

    # ========== 4. Solution ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.3), Inches(12), Inches(0.5), "Advisor Pulse — the attention layer", size=28, bold=True)
    steps = ["Detect", "Explain", "Prioritize", "Prepare", "Act", "Learn"]
    for i, step in enumerate(steps):
        left = 0.5 + i * 2.1
        fill = TEAL if i % 2 == 0 else ACCENT2
        rect(s, Inches(left), Inches(1.1), Inches(1.95), Inches(0.7), fill)
        add_text(
            s,
            Inches(left),
            Inches(1.22),
            Inches(1.95),
            Inches(0.5),
            step,
            size=16,
            bold=True,
            color=NAVY,
            align=PP_ALIGN.CENTER,
        )
    caps = [
        "Detect — Unified client context: holdings + goals + advice history + notes (+ optional cash-flow signals)",
        "Explain — Expectation-vs-actual with evidence-linked, qualified drivers (not fabricated narratives)",
        "Prioritize — Transparent multi-factor score → Critical / High / Monitor / On Track (configurable)",
        "Prepare — Meeting briefs & open questions grounded in structured facts",
        "Act — Advisor-review suggestions only; human approval; no autonomous trading",
        "Learn — Capture outcomes & notes so the next review starts smarter",
    ]
    y = 2.15
    for c in caps:
        rect(s, Inches(0.5), Inches(y), Inches(12.3), Inches(0.65), PANEL)
        add_text(s, Inches(0.7), Inches(y + 0.15), Inches(11.9), Inches(0.4), c, size=14)
        y += 0.72
    add_footer(s)

    # ========== 5. How it works technically ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.3), Inches(12), Inches(0.5), "How the intelligence works", size=28, bold=True)
    flow = [
        ("1. Ingest", "Txn CSV (cash-flow) +\nSYNTHETIC portfolio\nuniverse (labeled)"),
        ("2. Validate", "Schema checks,\nfreshness, missing-\ndata warnings"),
        ("3. Analytics", "Goal path, TWR,\nModified Dietz,\nallocation drift"),
        ("4. Attention", "Transparent factors +\nthresholds → book\npriority queue"),
        ("5. Summarize", "Structured facts →\ndeterministic brief\n(LLM optional, off)"),
        ("6. Human gate", "Advisor reviews &\napproves actions;\naudit trail ready"),
    ]
    for i, (h, body) in enumerate(flow):
        row, col = divmod(i, 3)
        left = 0.5 + col * 4.2
        top = 1.1 + row * 2.55
        rect(s, Inches(left), Inches(top), Inches(3.95), Inches(2.25), PANEL)
        add_text(s, Inches(left + 0.25), Inches(top + 0.25), Inches(3.45), Inches(0.4), h, size=18, bold=True, color=TEAL)
        add_text(s, Inches(left + 0.25), Inches(top + 0.85), Inches(3.45), Inches(1.2), body, size=14, color=WHITE)
    add_cite(
        s,
        "Honest data split: supplied CSV = transactions only. Portfolio/goal analytics use labeled SYNTHETIC DEMO data. SEBI IA Reg. 15(14): IA remains responsible for AI tools & client data.",
    )
    add_footer(s)

    # ========== 6. 20 vs 200 ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.3), Inches(12), Inches(0.5), "Where the value lies: 20 vs 200", size=28, bold=True)
    rect(s, Inches(0.5), Inches(1.05), Inches(6.0), Inches(5.0), PANEL)
    add_text(s, Inches(0.75), Inches(1.25), Inches(5.5), Inches(0.4), "Known clients (illustrative top 20)", size=18, bold=True, color=TEAL)
    add_multiline(
        s,
        Inches(0.75),
        Inches(1.85),
        Inches(5.5),
        Inches(3.8),
        [
            "• Meeting prep briefs in minutes, not hours",
            "• Changes since last review, surfaced",
            "• Goal progress + evidence-linked drivers",
            "• Conversation-ready open questions",
            "",
            "Supports depth — does not replace the",
            "relationship or professional judgment.",
        ],
        size=15,
    )
    rect(s, Inches(6.8), Inches(1.05), Inches(6.0), Inches(5.0), PANEL)
    add_text(s, Inches(7.05), Inches(1.25), Inches(5.5), Inches(0.4), "Long tail (illustrative ~200)", size=18, bold=True, color=TEAL)
    add_multiline(
        s,
        Inches(7.05),
        Inches(1.85),
        Inches(5.5),
        Inches(3.8),
        [
            f"• Demo book: {overview['long_tail_count']} long-tail clients",
            f"• {overview['clients_requiring_review']} total need review now",
            "• Proactive detection of material deviations",
            "• Configurable thresholds cut alert fatigue",
            "• Data-quality ≠ financial distress",
            "",
            "Greatest incremental value: scaling quality",
            "attention across clients outside daily focus.",
        ],
        size=15,
    )
    add_cite(
        s,
        "Illustrative book sizes. Context: Institutional Investor summarizing Cerulli — senior advisors ~160 clients; 29% manage >200. Not a measured productivity claim for Advisor Pulse.",
    )
    add_footer(s)

    # ========== 7. Product walkthrough ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.22), Inches(12), Inches(0.4), "Product walkthrough — live prototype screens", size=26, bold=True)
    overview_img = resolve_shot("01_overview.png", "overview.png")
    attention_img = resolve_shot("04_attention_queue.png", "attention_queue.png")
    left_ok = try_add_image(s, overview_img, Inches(0.4), Inches(0.75), Inches(6.2))
    right_ok = try_add_image(s, attention_img, Inches(6.8), Inches(0.75), Inches(6.1))
    if not left_ok:
        rect(s, Inches(0.4), Inches(0.75), Inches(6.2), Inches(5.5), PANEL)
        add_text(s, Inches(0.6), Inches(3.2), Inches(5.8), Inches(0.5), "[CONCEPT] Overview mockup — prototype screenshot unavailable", size=14, color=MUTED, align=PP_ALIGN.CENTER)
    if not right_ok:
        rect(s, Inches(6.8), Inches(0.75), Inches(6.1), Inches(5.5), PANEL)
        add_text(s, Inches(7.0), Inches(3.2), Inches(5.7), Inches(0.5), "[CONCEPT] Attention queue — screenshot unavailable", size=14, color=MUTED, align=PP_ALIGN.CENTER)
    add_text(
        s,
        Inches(0.4),
        Inches(6.35),
        Inches(12.5),
        Inches(0.3),
        "REAL PROTOTYPE screens (React @ :5173) · Labels: DEMO / SYNTHETIC · Not mockups unless marked CONCEPT",
        size=11,
        color=TEAL,
    )
    add_footer(s)

    # ========== 8. Demo Priya + Arjun ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.18), Inches(12), Inches(0.4), "Demo: Priya (escalate) vs Arjun (do not escalate)", size=24, bold=True)

    # Left Priya panel
    rect(s, Inches(0.4), Inches(0.65), Inches(6.2), Inches(5.85), PANEL)
    priya_img = resolve_shot("02_priya_investor.png", "investor_summary.png")
    if not try_add_image(s, priya_img, Inches(0.55), Inches(0.8), Inches(5.9)):
        add_text(s, Inches(0.6), Inches(2.5), Inches(5.8), Inches(0.5), "[Screenshot unavailable]", size=14, color=MUTED, align=PP_ALIGN.CENTER)
    add_text(
        s,
        Inches(0.55),
        Inches(5.55),
        Inches(5.9),
        Inches(0.8),
        f"Priya Sharma · {pr['priority']} · score {pr['score']}\n"
        f"Path {gp['deviation_pct_vs_expected']:+.1f}% · Active {ps['performance'].get('active_return_pct')} pp · ₹{ps['portfolio_value']/1e5:.1f}L",
        size=12,
        color=CRIT,
    )

    # Right Arjun panel
    rect(s, Inches(6.8), Inches(0.65), Inches(6.1), Inches(5.85), PANEL)
    arjun_img = resolve_shot("03_arjun_contrast.png", "advisor_pulse_arjun_contrast.png")
    if not try_add_image(s, arjun_img, Inches(6.95), Inches(0.8), Inches(5.8)):
        add_text(s, Inches(7.0), Inches(2.5), Inches(5.7), Inches(0.5), "[Screenshot unavailable]", size=14, color=MUTED, align=PP_ALIGN.CENTER)
    add_text(
        s,
        Inches(6.95),
        Inches(5.55),
        Inches(5.8),
        Inches(0.8),
        f"Arjun Mehta · {ar_pr['priority']} · score {ar_pr['score']}\n"
        f"Path {ar_gp['deviation_pct_vs_expected']:+.1f}% · Planned withdrawal explains AUM dip — NOT escalated",
        size=12,
        color=OK,
    )
    add_footer(s)

    # ========== 9. Trust & privacy ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.28), Inches(12), Inches(0.45), "Privacy, trust & human oversight", size=28, bold=True)
    items = [
        ("Human-in-the-loop", "Outputs are advisor-review suggestions — never autonomous trade instructions."),
        ("SEBI IA Reg. 15(14)", "IA solely responsible for AI tools, client-data integrity, and advice based on AI output; disclose AI use (Reg. 18(9))."),
        ("DPDP Act 2023", "Design considerations: free/specific/informed consent, purpose limitation, Data Fiduciary security duties. Not claimed compliance."),
        ("Data boundary", "Demo: no investor PII to external models — deterministic templates. Production: approved DPA or on-prem only."),
        ("Transcripts", "Prototype: mocked local path. Production: consent + on-prem ASR + retention limits."),
        ("Evidence discipline", "Summary numbers copied only from structured analytics; confidence + missing-data warnings shown."),
        ("Honest limit", "Prototype is NOT SEBI-compliant, DPDP-certified, or production-secure."),
    ]
    y = 0.9
    for title, body in items:
        rect(s, Inches(0.5), Inches(y), Inches(12.3), Inches(0.72), PANEL)
        add_text(s, Inches(0.7), Inches(y + 0.08), Inches(3.2), Inches(0.5), title, size=13, bold=True, color=TEAL)
        add_text(s, Inches(4.0), Inches(y + 0.12), Inches(8.5), Inches(0.5), body, size=13, color=WHITE)
        y += 0.78
    add_cite(
        s,
        "Sources: SEBI IA Regulations PDF (Reg. 15(14)); SEBI IA Master Circular (AI disclosure / 18(9)); MeitY DPDP Act 2023 PDF. Design considerations ≠ certification.",
    )
    add_footer(s)

    # ========== 10. Competitive positioning ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.28), Inches(12), Inches(0.45), "Competitive positioning", size=28, bold=True)
    headers = ["Capability", "Salesforce\nFSC/Agentforce", "Morningstar\nAWS", "Aladdin\nWealth", "Advisor\nPulse"]
    rows = [
        ["CRM / household 360", "Y", "P", "P", "Integrates"],
        ["Deep risk / stress", "NV", "P", "Y", "Not claimed"],
        ["Goal path vs expected", "P", "P", "P", "Core"],
        ["Explainable gap drivers", "NV", "P", "P", "Core*"],
        ["Transparent priority", "NV", "NV", "P", "Core"],
        ["Evidence-bound briefs", "Y", "NV", "NV", "Y"],
        ["Long-tail attention loop", "P", "NV", "P", "Primary JTBD"],
    ]
    # header row
    col_w = [3.4, 2.15, 2.15, 2.15, 2.15]
    x0 = 0.5
    y0 = 0.95
    x = x0
    for i, h in enumerate(headers):
        rect(s, Inches(x), Inches(y0), Inches(col_w[i] - 0.08), Inches(0.85), PANEL2)
        add_text(s, Inches(x + 0.08), Inches(y0 + 0.15), Inches(col_w[i] - 0.2), Inches(0.65), h, size=11, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
        x += col_w[i]
    for r_i, row in enumerate(rows):
        x = x0
        y = y0 + 0.9 + r_i * 0.65
        for c_i, cell in enumerate(row):
            bg = PANEL if r_i % 2 == 0 else PANEL2
            rect(s, Inches(x), Inches(y), Inches(col_w[c_i] - 0.08), Inches(0.58), bg)
            color = TEAL if c_i == 4 and cell in ("Core", "Core*", "Y", "Primary JTBD", "Integrates") else WHITE
            add_text(
                s,
                Inches(x + 0.08),
                Inches(y + 0.12),
                Inches(col_w[c_i] - 0.2),
                Inches(0.4),
                cell,
                size=12,
                bold=(c_i == 0 or c_i == 4),
                color=color,
                align=PP_ALIGN.CENTER if c_i else PP_ALIGN.LEFT,
            )
            x += col_w[c_i]
    add_cite(
        s,
        "Y=evidenced · P=partial · NV=not verified in sources examined. *Qualified drivers. Differentiation = combination + explainable attention loop. See research/ppt/competitor_matrix.md.",
    )
    add_footer(s)

    # ========== 11. Validation & roadmap ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.28), Inches(12), Inches(0.45), "Validation & roadmap", size=28, bold=True)
    blocks = [
        (
            "Built today",
            "• React + FastAPI prototype\n• SYNTHETIC DEMO book (220)\n• TWR + Modified Dietz\n• Transparent prioritization\n• Meeting briefs + notes\n• Deterministic summaries\n• Tests + research + this deck",
        ),
        (
            "Needs integration",
            "• Live custodian / PMS feeds\n• CRM task push / SSO\n• On-prem ASR (consent)\n• Approved LLM under DPA\n• Fuller Brinson attribution\n• Production security review\n• Firm-specific thresholds",
        ),
        (
            "Pilot metrics (plan)",
            "• Review prep time saved\n• % alerts advisor-validated\n• Missed events (retro)\n• False-positive rate\n• % claims with cited facts\n\nNo invented pilot results.",
        ),
    ]
    for i, (h, body) in enumerate(blocks):
        left = 0.5 + i * 4.2
        rect(s, Inches(left), Inches(1.0), Inches(3.95), Inches(5.2), PANEL)
        add_text(s, Inches(left + 0.25), Inches(1.2), Inches(3.45), Inches(0.4), h, size=17, bold=True, color=TEAL)
        add_text(s, Inches(left + 0.25), Inches(1.8), Inches(3.45), Inches(4.1), body, size=14)
    add_cite(
        s,
        "Globathon Round 2 rule: problem-specific logic must be built during the 12-hour finale; this repo is Round 1 ideation evidence + reference architecture.",
    )
    add_footer(s)

    # ========== 12. Closing ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.6), Inches(1.8), Inches(12), Inches(0.6), "Where does this client stand?", size=36, bold=True, color=TEAL)
    add_text(
        s,
        Inches(0.6),
        Inches(2.7),
        Inches(12),
        Inches(1.2),
        "Advisor Pulse helps advisors spend less time searching for signals —\nand more time acting on the right ones.",
        size=22,
    )
    add_text(
        s,
        Inches(0.6),
        Inches(4.2),
        Inches(12),
        Inches(0.9),
        "Detect → Explain → Prioritize → Prepare → Act → Learn",
        size=18,
        bold=True,
        color=WHITE,
    )
    add_text(
        s,
        Inches(0.6),
        Inches(5.2),
        Inches(12),
        Inches(0.7),
        "Globathon 2026 · React web prototype · SYNTHETIC DEMO data\nTeam: [Name 1] · [Name 2] · [Name 3] · [Name 4]",
        size=14,
        color=MUTED,
    )
    add_footer(s)

    # ========== Appendix A — Finale cut ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.3), Inches(12), Inches(0.5), "Appendix — Finale pitch cut (2–4 slides)", size=26, bold=True)
    add_multiline(
        s,
        Inches(0.7),
        Inches(1.1),
        Inches(12),
        Inches(5.2),
        [
            "Official Round 2 live pitch PPT is short (2–4 slides). Suggested cut from this deck:",
            "",
            "1) Title + promise + live KPIs                          → Slide 1",
            "2) Solution workflow + differentiation               → Slide 4 (+ one line from 3)",
            "3) Demo: Priya escalate / Arjun suppress            → Slide 8",
            "4) Trust + ask / close                                        → Slides 9 + 12",
            "",
            "Also required at finale: working prototype, source code, run instructions,",
            "live demo + Q&A.",
            "",
            "Reuse rule (official): problem-specific features & business logic must be",
            "developed during the coding round — treat this build as ideation evidence.",
        ],
        size=16,
    )
    add_cite(s, "Source: https://globathon.globatech.net/rulebook (examined 17 Oct 2026). Homepage final round listed Saturday 15 Nov 2026.")
    add_footer(s)

    # ========== Appendix B — Sources ==========
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(s)
    accent_bar(s)
    add_text(s, Inches(0.5), Inches(0.3), Inches(12), Inches(0.45), "Appendix — Principal sources", size=26, bold=True)
    add_multiline(
        s,
        Inches(0.7),
        Inches(0.95),
        Inches(12),
        Inches(5.8),
        [
            "1. https://globathon.globatech.net/ — Globatech homepage (timeline)",
            "2. https://globathon.globatech.net/rulebook — Official Quest Log / rulebook",
            "3. Cerulli: Advisor Headcount Set to Grow as AI Expands Capacity (9 Sep 2026)",
            "4. Institutional Investor / Cerulli — advisor client-load capacity summary",
            "5. Salesforce Financial Services — Wealth / Agentforce product pages",
            "6. Morningstar Advisor Workstation product pages",
            "7. BlackRock Aladdin Wealth product pages",
            "8. SEBI IA Regulations PDF — Reg. 15(14) AI responsibility",
            "9. SEBI IA Master Circular PDF — AI disclosure guidance (Reg. 18(9))",
            "10. MeitY — Digital Personal Data Protection Act, 2023 PDF",
            "",
            "Full citations & assumption labels: research/ppt/fintech_research.md",
            "Capability matrix: research/ppt/competitor_matrix.md",
        ],
        size=14,
    )
    add_footer(s)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print(f"Wrote {OUT}")
    print(f"Slides: {len(prs.slides)}")
    print(f"Metrics source: {src_note}")
    print(
        f"KPIs: clients={overview['total_clients']} review={overview['clients_requiring_review']} "
        f"Priya={pr['priority']}/{pr['score']} Arjun={ar_pr['priority']}/{ar_pr['score']}"
    )
    return OUT, len(prs.slides)


if __name__ == "__main__":
    build()
