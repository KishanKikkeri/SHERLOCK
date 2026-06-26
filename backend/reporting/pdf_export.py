"""
SHERLOCK — PDF Investigation Report Generator (Phase 7A).

Converts a `final_report` dict (from SherlockState) into a professional,
formatted PDF investigation report. The design mirrors real law-enforcement
report aesthetics: monospace case metadata, ruled sections, confidence
color-coding, and a full reasoning-path trail.

Usage:
    from backend.reporting.pdf_export import generate_investigation_pdf
    pdf_bytes = generate_investigation_pdf(final_report, audit_trail)
    with open("report.pdf", "wb") as f:
        f.write(pdf_bytes)
"""

import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)

# ── Brand colours (matching the frontend) ────────────────────────────────────
AMBER   = colors.HexColor("#f0a500")
CYAN    = colors.HexColor("#00c8d4")
RED     = colors.HexColor("#e84040")
GREEN   = colors.HexColor("#2dba6e")
BG_DARK = colors.HexColor("#0d1117")
SURFACE = colors.HexColor("#111820")
BORDER  = colors.HexColor("#1e2d3d")
TEXT    = colors.HexColor("#c9d8e8")
DIMTEXT = colors.HexColor("#4e6a84")
WHITE   = colors.white
BLACK   = colors.black

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def _conf_color(conf: float):
    if conf >= 0.8: return GREEN
    if conf >= 0.6: return AMBER
    return RED


def _conf_label(conf: float):
    if conf >= 0.8: return "HIGH"
    if conf >= 0.6: return "MEDIUM"
    return "LOW"


def generate_investigation_pdf(final_report: dict, audit_trail: list = None,
                                case_id: str = None) -> bytes:
    """
    Generate a PDF investigation report and return the raw bytes.

    Args:
        final_report: SherlockState["final_report"] dict
        audit_trail:  SherlockState["audit_trail"] list (for the timeline)
        case_id:      Optional case reference (auto-generated if None)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title="SHERLOCK Investigation Report",
        author="SHERLOCK Crime Intelligence Platform",
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Styles ──────────────────────────────────────────────────────────────
    def S(name, **kw):
        base = styles["Normal"]
        return ParagraphStyle(name, parent=base, **kw)

    title_style = S("Title", fontSize=22, textColor=AMBER, fontName="Helvetica-Bold",
                    spaceAfter=2)
    subtitle_style = S("Subtitle", fontSize=9, textColor=DIMTEXT, fontName="Helvetica",
                       spaceAfter=8)
    section_style = S("Section", fontSize=10, textColor=AMBER, fontName="Helvetica-Bold",
                       spaceBefore=12, spaceAfter=4, leading=14)
    body_style = S("Body", fontSize=9, textColor=BLACK, fontName="Helvetica",
                   leading=14, spaceAfter=4)
    mono_style = S("Mono", fontSize=8, textColor=DIMTEXT, fontName="Courier",
                   leading=12, spaceAfter=2)
    finding_title_style = S("FindingTitle", fontSize=9, textColor=WHITE,
                             fontName="Helvetica-Bold", leading=12)
    finding_body_style = S("FindingBody", fontSize=8, textColor=TEXT,
                            fontName="Helvetica", leading=12)

    # ── Header block ─────────────────────────────────────────────────────────
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    case_id = case_id or f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # Dark header table
    header_data = [[
        Paragraph("<b>SHERLOCK</b>", ParagraphStyle("H1", fontSize=24, textColor=AMBER,
                   fontName="Helvetica-Bold")),
        Paragraph(
            f"<font color='#4e6a84'>CRIME INTELLIGENCE COMMAND CENTER</font><br/>"
            f"<font color='#4e6a84'>Karnataka Police · AI-Powered Investigation Platform</font>",
            ParagraphStyle("H2", fontSize=8, fontName="Helvetica", leading=13)
        ),
    ]]
    header_table = Table(header_data, colWidths=[80*mm, 90*mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BG_DARK),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING", (0,0), (0,-1), 12),
        ("LEFTPADDING", (1,0), (1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))

    # Case metadata row
    meta_data = [[
        Paragraph(f"<b>CASE ID</b>  {case_id}", mono_style),
        Paragraph(f"<b>GENERATED</b>  {generated_at}", mono_style),
        Paragraph(f"<b>STATUS</b>  CLASSIFIED", mono_style),
    ]]
    meta_table = Table(meta_data, colWidths=[57*mm, 67*mm, 45*mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), SURFACE),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("BOX", (0,0), (-1,-1), 0.5, BORDER),
        ("LINEAFTER", (0,0), (1,-1), 0.5, BORDER),
        ("TEXTCOLOR", (0,0), (-1,-1), DIMTEXT),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # ── Query ──────────────────────────────────────────────────────────────
    story.append(Paragraph("INVESTIGATION QUERY", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 4))
    query_text = final_report.get("query", "(query not recorded)")
    story.append(Paragraph(f'"{query_text}"',
                            S("Q", fontSize=10, fontName="Helvetica-Oblique",
                              textColor=BLACK, leading=15, spaceAfter=8)))

    # ── Investigation Timeline ─────────────────────────────────────────────
    story.append(Paragraph("INVESTIGATION TIMELINE", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 4))

    trail = audit_trail or []
    if trail:
        for entry in trail:
            status = entry.get("status", "done")
            icon = "✓" if status == "done" else "—"
            agent = entry.get("agent", "Unknown")
            msg = entry.get("message", "")[:100]
            row_color = colors.HexColor("#f0fff4") if status == "done" else colors.HexColor("#f8f8f8")
            tbl = Table([[
                Paragraph(f"<font color='{'#2dba6e' if status=='done' else '#888'}'>{icon}</font>",
                          S("Icon", fontSize=10, fontName="Helvetica-Bold")),
                Paragraph(f"<b>{agent}</b>", S("AName", fontSize=8, fontName="Helvetica-Bold", textColor=BLACK)),
                Paragraph(msg, S("AMsg", fontSize=8, fontName="Helvetica", textColor=DIMTEXT, leading=11)),
            ]], colWidths=[8*mm, 52*mm, 109*mm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,-1), row_color),
                ("TOPPADDING", (0,0), (-1,-1), 3),
                ("BOTTOMPADDING", (0,0), (-1,-1), 3),
                ("LEFTPADDING", (0,0), (0,-1), 4),
                ("LEFTPADDING", (1,0), (-1,-1), 4),
                ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
            ]))
            story.append(tbl)
    story.append(Spacer(1, 8))

    # ── Reasoning Path ─────────────────────────────────────────────────────
    agents_consulted = final_report.get("agents_consulted", [])
    if agents_consulted:
        story.append(Paragraph("REASONING PATH", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 4))
        path_text = "  →  ".join(agents_consulted) + "  →  Evidence Validation  →  Chief Synthesis"
        story.append(Paragraph(path_text, mono_style))
        story.append(Spacer(1, 8))

    # ── Key Findings ───────────────────────────────────────────────────────
    findings = [f for f in final_report.get("findings", [])
                if f.get("finding_type") != "validation_summary"]
    story.append(Paragraph(f"KEY FINDINGS  ({len(findings)} validated)", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 4))

    for i, f in enumerate(findings, 1):
        conf = f.get("confidence", 0)
        ccolor = _conf_color(conf)
        clabel = _conf_label(conf)
        finding_type = (f.get("finding_type") or "finding").replace("_", " ").upper()
        agent_name = f.get("agent_name", "Unknown")
        summary = f.get("summary", "")
        evidence_list = f.get("evidence", [])

        # Colour-coded finding card
        card_data = [
            [
                Paragraph(f"<b>#{i}  {finding_type}</b>",
                          S("FT", fontSize=8, fontName="Helvetica-Bold", textColor=WHITE)),
                Paragraph(f"<b>{conf:.0%}  {clabel}</b>",
                          S("FC", fontSize=8, fontName="Helvetica-Bold", textColor=WHITE)),
                Paragraph(f"<font color='#4e6a84'>{agent_name}</font>",
                          S("FA", fontSize=7, fontName="Helvetica", textColor=WHITE)),
            ],
            [
                Paragraph(summary, S("FS", fontSize=8, fontName="Helvetica",
                                      textColor=BLACK, leading=12)),
                "", "",
            ],
        ]
        if evidence_list:
            ev_text = "<br/>".join(f"• {e[:120]}" for e in evidence_list[:3])
            card_data.append([
                Paragraph(ev_text, S("FE", fontSize=7, fontName="Courier",
                                      textColor=DIMTEXT, leading=11)),
                "", "",
            ])

        card = Table(card_data, colWidths=[95*mm, 28*mm, 46*mm])
        card.setStyle(TableStyle([
            # Header row
            ("BACKGROUND", (0,0), (-1,0), BG_DARK),
            ("LEFTPADDING", (0,0), (-1,0), 6),
            ("RIGHTPADDING", (0,0), (-1,0), 6),
            ("TOPPADDING", (0,0), (-1,0), 5),
            ("BOTTOMPADDING", (0,0), (-1,0), 5),
            # Confidence cell accent
            ("BACKGROUND", (1,0), (1,0), ccolor),
            ("TEXTCOLOR", (1,0), (1,0), BLACK if conf >= 0.6 else WHITE),
            # Body rows
            ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#f5f7fa")),
            ("TOPPADDING", (0,1), (-1,-1), 5),
            ("BOTTOMPADDING", (0,1), (-1,-1), 5),
            ("LEFTPADDING", (0,1), (-1,-1), 6),
            ("SPAN", (0,1), (-1,1)),
            ("SPAN", (0,2), (-1,2)),
            # Border
            ("BOX", (0,0), (-1,-1), 0.5, BORDER),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        story.append(KeepTogether([card, Spacer(1, 5)]))

    # ── Confidence Heatmap ─────────────────────────────────────────────────
    if findings:
        story.append(Spacer(1, 4))
        story.append(Paragraph("CONFIDENCE HEATMAP", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 4))

        heatmap_data = [["Finding", "Agent", "Confidence", "Status"]]
        for f in findings:
            conf = f.get("confidence", 0)
            heatmap_data.append([
                (f.get("finding_type") or "finding").replace("_", " ").title(),
                f.get("agent_name", "—"),
                f"{conf:.0%}",
                _conf_label(conf),
            ])
        heatmap = Table(heatmap_data, colWidths=[65*mm, 48*mm, 25*mm, 31*mm])
        style_cmds = [
            ("BACKGROUND", (0,0), (-1,0), BG_DARK),
            ("TEXTCOLOR", (0,0), (-1,0), AMBER),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.3, BORDER),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("BACKGROUND", (0,1), (-1,-1), colors.white),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f7fa")]),
        ]
        for row_i, f in enumerate(findings, 1):
            conf = f.get("confidence", 0)
            heatmap.setStyle(TableStyle(style_cmds + [
                ("TEXTCOLOR", (2, row_i), (3, row_i), _conf_color(conf)),
                ("FONTNAME", (2, row_i), (3, row_i), "Helvetica-Bold"),
            ]))
        heatmap.setStyle(TableStyle(style_cmds))
        story.append(heatmap)

    # ── Recommended Actions (Prevention Intelligence findings if present) ───
    prevention_findings = [f for f in final_report.get("findings", [])
                            if f.get("finding_type") in
                            ("patrol_strategy", "surveillance_action", "prevention_recommendation")]
    if prevention_findings:
        story.append(Spacer(1, 8))
        story.append(Paragraph("RECOMMENDED ACTIONS", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 4))
        for i, f in enumerate(prevention_findings, 1):
            story.append(Paragraph(f"{i}.  {f.get('summary', '')}", body_style))

    # ── Footer ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Generated by SHERLOCK Crime Intelligence Platform · {generated_at} · "
        f"Case {case_id} · FOR OFFICIAL USE ONLY",
        S("Footer", fontSize=7, textColor=DIMTEXT, fontName="Helvetica",
          alignment=1),  # centre
    ))

    doc.build(story)
    return buf.getvalue()
