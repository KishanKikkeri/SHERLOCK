"""
SHERLOCK — PDF Investigation Report Generator (Phase 7A; Stage D Sprint 4).

Converts a `final_report` dict (from SherlockState) into a professional,
formatted PDF investigation report. The design mirrors real law-enforcement
report aesthetics: monospace case metadata, ruled sections, confidence
color-coding, and a full reasoning-path trail.

Usage:
    from backend.reporting.pdf_export import generate_investigation_pdf
    pdf_bytes = generate_investigation_pdf(final_report, audit_trail)
    with open("report.pdf", "wb") as f:
        f.write(pdf_bytes)

Stage D, Sprint 4 — Localized PDF Export
-----------------------------------------
`generate_investigation_pdf` grew one new, optional, keyword-only
argument: `language` ("en" default / "kn" / "bilingual"). Per this
sprint's Golden Rules ("Maintain current export route. Only extend
it."), every existing call with no `language` argument takes the exact
same code path as before this sprint (`render_kn` is `False`, `T()` is
the identity function, no font substitution happens) — see
`validate_stage_d4.py`'s byte-identical regression check.

Unicode support is real, not faked: Noto Sans Kannada (Regular + Bold)
is bundled in `backend/reporting/fonts/` and registered with ReportLab
via `pdfmetrics.registerFont`/`registerFontFamily` at import time. This
was validated with `pdffonts` (poppler-utils) against real generated
PDFs — confirms the font is actually embedded (not just referenced) —
and with `pdftotext`, confirming the extracted text round-trips to
correct Kannada, not mangled/mapped-wrong glyphs. See the Sprint D4
report for the actual command output.

`language="kn"` reads `final_report["localized"]` — the block Sprint
D2's `_localize_report()` already attaches to a report when the
investigation ran with `language="kn"`. If that block is missing (e.g.
the report came from an English-only investigation but a Kannada PDF
was requested anyway), the PDF is rendered in English with a visible
notice explaining why. `language="bilingual"` renders the English
narrative/findings followed by their Kannada equivalent for each
section.

Mixed-script text is the normal case, not an edge case: Sprint D1's
glossary deliberately keeps some terms (FIR, IPC, Chargesheet, agent
names, FIR/case codes) in their original Latin form inside otherwise-
Kannada sentences, and "bilingual" mode literally puts English and
Kannada paragraphs next to each other. Checked with `fontTools` against
the bundled font rather than assumed: **Noto Sans Kannada's cmap has no
Latin letters at all** — 164 glyphs total (Kannada script, digits, and
common punctuation only). Rendering mixed text with only that font
silently drops every Latin letter (this was caught in testing —
"[CrimeRecords]" rendered as "[]" — before the fix below). The fix,
`_mixed_script_markup()`: every string inserted into a Kannada-font
paragraph is scanned for runs of ASCII letters, each wrapped in an
explicit `<font name="Helvetica">` tag so Latin runs render in
Helvetica while the surrounding Kannada renders in Noto Sans Kannada,
in the same paragraph. Digits/punctuation don't need this — the
Kannada font has those.

Per this sprint's handover ("avoid translating stored evidence...
database remains canonical English"), evidence bullet lines under each
finding are intentionally NOT translated in any mode, and are rendered
in plain Courier (not the Kannada font) since they're guaranteed
English/ASCII by construction.
"""

import io
import logging
import os
import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)

from backend.language.resources import get_resources

logger = logging.getLogger(__name__)

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

SUPPORTED_PDF_LANGUAGES = ("en", "kn", "bilingual")

# ── Kannada font registration (Stage D, Sprint 4) ───────────────────────────
# Bundled in-repo rather than relying on the host OS having it installed —
# a PDF-generation server shouldn't depend on a Noto Kannada package being
# apt-installed on whatever box it runs on.
_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_KANNADA_REGULAR_PATH = os.path.join(_FONTS_DIR, "NotoSansKannada-Regular.ttf")
_KANNADA_BOLD_PATH = os.path.join(_FONTS_DIR, "NotoSansKannada-Bold.ttf")

KANNADA_FONT_NAME = "NotoKannada"
KANNADA_FONT_BOLD_NAME = "NotoKannada-Bold"
KANNADA_FONT_AVAILABLE = False
KANNADA_FONT_ERROR = None

try:
    pdfmetrics.registerFont(TTFont(KANNADA_FONT_NAME, _KANNADA_REGULAR_PATH))
    pdfmetrics.registerFont(TTFont(KANNADA_FONT_BOLD_NAME, _KANNADA_BOLD_PATH))
    pdfmetrics.registerFontFamily(
        KANNADA_FONT_NAME,
        normal=KANNADA_FONT_NAME,
        bold=KANNADA_FONT_BOLD_NAME,
        italic=KANNADA_FONT_NAME,
        boldItalic=KANNADA_FONT_BOLD_NAME,
    )
    KANNADA_FONT_AVAILABLE = True
except Exception as e:  # pragma: no cover - exercised in validate_stage_d4.py's fallback test
    KANNADA_FONT_ERROR = str(e)
    logger.warning("Kannada font registration failed; kn/bilingual PDF export will fall back to English.",
                    exc_info=True)


def _conf_color(conf: float):
    if conf >= 0.8: return GREEN
    if conf >= 0.6: return AMBER
    return RED


def _conf_label(conf: float, labels: dict):
    if conf >= 0.8: return labels["high"]
    if conf >= 0.6: return labels["medium"]
    return labels["low"]


_LATIN_RUN = re.compile(r"[A-Za-z]+")


def _mixed_script_markup(text) -> str:
    """
    Wraps every run of ASCII Latin letters in `text` with an explicit
    `<font name="Helvetica">` ReportLab inline tag and XML-escapes
    everything else. See module docstring for why this exists — the
    bundled Kannada font has zero Latin glyphs, verified with fontTools.
    """
    text = text or ""
    if not text:
        return text
    out = []
    last = 0
    for m in _LATIN_RUN.finditer(text):
        if m.start() > last:
            out.append(_xml_escape(text[last:m.start()]))
        out.append(f'<font name="Helvetica">{_xml_escape(m.group())}</font>')
        last = m.end()
    out.append(_xml_escape(text[last:]))
    return "".join(out)


def generate_investigation_pdf(final_report: dict, audit_trail: list = None,
                                case_id: str = None, language: str = "en") -> bytes:
    """
    Generate a PDF investigation report and return the raw bytes.

    Args:
        final_report: SherlockState["final_report"] dict
        audit_trail:  SherlockState["audit_trail"] list (for the timeline)
        case_id:      Optional case reference (auto-generated if None)
        language:     "en" (default, unchanged pre-Sprint-4 behavior),
                      "kn", or "bilingual". An unsupported value raises
                      ValueError rather than silently defaulting.
    """
    if language not in SUPPORTED_PDF_LANGUAGES:
        raise ValueError(f"language must be one of {SUPPORTED_PDF_LANGUAGES}, got {language!r}")

    warnings = []
    render_kn = language in ("kn", "bilingual")
    if render_kn and not KANNADA_FONT_AVAILABLE:
        warnings.append(f"Kannada font unavailable ({KANNADA_FONT_ERROR}); report rendered in English.")
        language = "en"
        render_kn = False

    localized = final_report.get("localized") or {}
    if render_kn and not localized:
        warnings.append(
            "Kannada PDF requested but final_report has no 'localized' block "
            "(the investigation likely ran without language='kn'). Rendering in English."
        )
        language = "en"
        render_kn = False

    en_labels = get_resources("en")["pdf"]
    kn_labels = get_resources("kn")["pdf"]
    # "kn" mode localizes chrome/labels too; "bilingual" keeps English
    # section headers (the reader sees both languages' body content
    # either way) and only doubles the narrative/finding text itself.
    labels = kn_labels if language == "kn" else en_labels

    FONT_REGULAR = KANNADA_FONT_NAME if render_kn else "Helvetica"
    FONT_BOLD = KANNADA_FONT_BOLD_NAME if render_kn else "Helvetica-Bold"
    # No dedicated Kannada monospace face is bundled; Courier can't render
    # Kannada glyphs at all, so monospace sections (case metadata,
    # reasoning path) use the Kannada regular face in kn/bilingual mode
    # instead of silently dropping to tofu boxes. This does lose the
    # fixed-width alignment those sections have in English-only PDFs —
    # documented in the Sprint D4 report rather than hidden.
    FONT_MONO = KANNADA_FONT_NAME if render_kn else "Courier"

    def T(text) -> str:
        """Mixed-script-safe markup in kn/bilingual mode; identity
        (raw text, unescaped, exactly as before Sprint D4) in English
        mode — every existing English PDF stays byte-for-byte the same."""
        return _mixed_script_markup(text) if render_kn else (text or "")

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
        kw.setdefault("fontName", FONT_REGULAR)
        return ParagraphStyle(name, parent=base, **kw)

    title_style = S("Title", fontSize=22, textColor=AMBER, fontName=FONT_BOLD,
                    spaceAfter=2)
    subtitle_style = S("Subtitle", fontSize=9, textColor=DIMTEXT, fontName=FONT_REGULAR,
                       spaceAfter=8)
    section_style = S("Section", fontSize=10, textColor=AMBER, fontName=FONT_BOLD,
                       spaceBefore=12, spaceAfter=4, leading=14)
    body_style = S("Body", fontSize=9, textColor=BLACK, fontName=FONT_REGULAR,
                   leading=14, spaceAfter=4)
    mono_style = S("Mono", fontSize=8, textColor=DIMTEXT, fontName=FONT_MONO,
                   leading=12, spaceAfter=2)
    notice_style = S("Notice", fontSize=8, textColor=RED, fontName=FONT_REGULAR,
                      leading=12, spaceAfter=6)

    # ── Header block ─────────────────────────────────────────────────────────
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    case_id = case_id or f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # Brand wordmark and the org tagline are always Latin-script by design
    # (a police letterhead's brand name isn't transliterated) — rendered in
    # plain Helvetica regardless of `language`, so they're never run through
    # the Kannada face (which would drop every letter) in the first place.
    header_data = [[
        Paragraph("<b>SHERLOCK</b>", ParagraphStyle("H1", fontSize=24, textColor=AMBER,
                   fontName="Helvetica-Bold")),
        Paragraph(
            f"<font color='#4e6a84'>CRIME INTELLIGENCE COMMAND CENTER</font><br/>"
            f"<font color='#4e6a84'>Karnataka Police - AI-Powered Investigation Platform</font>",
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

    # Translation / fallback notices — shown whenever this PDF isn't the
    # plain pre-Stage-D English render, so a reader knows exactly what
    # they're looking at.
    if language in ("kn", "bilingual") and render_kn:
        story.append(Paragraph(T(kn_labels["translation_notice"]), notice_style))
    for w in warnings:
        story.append(Paragraph(T(f"NOTICE: {w}"), notice_style))

    # Case metadata row
    meta_data = [[
        Paragraph(f"<b>{T(labels['case_id'])}</b>  {T(case_id)}", mono_style),
        Paragraph(f"<b>{T(labels['generated'])}</b>  {T(generated_at)}", mono_style),
        Paragraph(f"<b>{T(labels['status'])}</b>  {T(labels['classified'])}", mono_style),
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
    story.append(Paragraph(T(labels["investigation_query"]), section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 4))
    query_text = final_report.get("query", "(query not recorded)")
    story.append(Paragraph(f'"{T(query_text)}"',
                            S("Q", fontSize=10, fontName=FONT_REGULAR,
                              textColor=BLACK, leading=15, spaceAfter=8)))
    original_query = localized.get("original_query") if render_kn else None
    if original_query and original_query != query_text:
        story.append(Paragraph(
            f"<b>{T(kn_labels['original_query'])}:</b> \u201c{T(original_query)}\u201d",
            S("OQ", fontSize=9, fontName=FONT_REGULAR, textColor=DIMTEXT, leading=13, spaceAfter=8),
        ))

    # ── Investigation Timeline ─────────────────────────────────────────────
    story.append(Paragraph(T(labels["timeline"]), section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 4))

    trail = audit_trail or []
    if trail:
        for entry in trail:
            status = entry.get("status", "done")
            icon = "OK" if status == "done" else "-"
            agent = entry.get("agent", "Unknown")
            msg = entry.get("message", "")[:100]
            row_color = colors.HexColor("#f0fff4") if status == "done" else colors.HexColor("#f8f8f8")
            tbl = Table([[
                Paragraph(f"<font color='{'#2dba6e' if status=='done' else '#888'}'>{icon}</font>",
                          S("Icon", fontSize=9, fontName=FONT_BOLD)),
                Paragraph(f"<b>{T(agent)}</b>", S("AName", fontSize=8, fontName=FONT_BOLD, textColor=BLACK)),
                Paragraph(T(msg), S("AMsg", fontSize=8, fontName=FONT_REGULAR, textColor=DIMTEXT, leading=11)),
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
        story.append(Paragraph(T(labels["reasoning_path"]), section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 4))
        path_text = "  ->  ".join(agents_consulted) + "  ->  Evidence Validation  ->  Chief Synthesis"
        story.append(Paragraph(T(path_text), mono_style))
        story.append(Spacer(1, 8))

    # ── Narrative (Stage D Sprint 4: en / kn / bilingual) ──────────────────
    narrative_en = final_report.get("narrative") or ""
    narrative_kn = localized.get("narrative") if render_kn else None
    if narrative_en or narrative_kn:
        story.append(Paragraph(T(labels["summary"]), section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 4))
        if language == "kn" and narrative_kn:
            story.append(Paragraph(T(narrative_kn), body_style))
        elif language == "bilingual" and narrative_kn:
            story.append(Paragraph(T(narrative_en), body_style))
            story.append(Paragraph(T(narrative_kn), S("NarKn", fontSize=9, fontName=FONT_REGULAR,
                                                        textColor=colors.HexColor("#2a3f52"), leading=14, spaceAfter=4)))
        else:
            story.append(Paragraph(T(narrative_en), body_style))
        story.append(Spacer(1, 4))

    # ── Key Findings ───────────────────────────────────────────────────────
    findings = [f for f in final_report.get("findings", [])
                if f.get("finding_type") != "validation_summary"]
    findings_kn = [f for f in localized.get("findings", [])
                   if f.get("finding_type") != "validation_summary"] if render_kn else []

    story.append(Paragraph(T(f"{labels['key_findings']}  ({len(findings)} {labels['validated']})"), section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 4))

    for i, f in enumerate(findings, 1):
        conf = f.get("confidence", 0)
        ccolor = _conf_color(conf)
        clabel = _conf_label(conf, labels)
        finding_type = (f.get("finding_type") or "finding").replace("_", " ").upper()
        agent_name = f.get("agent_name", "Unknown")
        summary_en = f.get("summary", "")
        summary_kn = findings_kn[i - 1].get("summary", "") if i - 1 < len(findings_kn) else None
        evidence_list = f.get("evidence", [])  # intentionally never translated — see module docstring

        summary_flowables = []
        if language == "kn" and summary_kn:
            summary_flowables.append(Paragraph(T(summary_kn), S("FS", fontSize=8, fontName=FONT_REGULAR,
                                                                  textColor=BLACK, leading=12)))
        elif language == "bilingual" and summary_kn:
            summary_flowables.append(Paragraph(T(summary_en), S("FS", fontSize=8, fontName=FONT_REGULAR,
                                                                  textColor=BLACK, leading=12)))
            summary_flowables.append(Paragraph(T(summary_kn), S("FSkn", fontSize=8, fontName=FONT_REGULAR,
                                                                  textColor=colors.HexColor("#33475a"), leading=12)))
        else:
            summary_flowables.append(Paragraph(T(summary_en), S("FS", fontSize=8, fontName=FONT_REGULAR,
                                                                  textColor=BLACK, leading=12)))

        card_data = [
            [
                Paragraph(f"<b>#{i}  {T(finding_type)}</b>",
                          S("FT", fontSize=8, fontName=FONT_BOLD, textColor=WHITE)),
                Paragraph(f"<b>{conf:.0%}  {T(clabel)}</b>",
                          S("FC", fontSize=8, fontName=FONT_BOLD, textColor=WHITE)),
                Paragraph(f"<font color='#4e6a84'>{T(agent_name)}</font>",
                          S("FA", fontSize=7, fontName=FONT_REGULAR, textColor=WHITE)),
            ],
            [summary_flowables, "", ""],
        ]
        if evidence_list:
            # Evidence is never translated (canonical English, see module
            # docstring) and rendered in plain Courier — safe regardless of
            # `language`, so no T() needed here.
            ev_text = "<br/>".join(f"- {_xml_escape(e[:120])}" for e in evidence_list[:3])
            card_data.append([
                Paragraph(ev_text, S("FE", fontSize=7, fontName="Courier",
                                      textColor=DIMTEXT, leading=11)),
                "", "",
            ])

        card = Table(card_data, colWidths=[95*mm, 28*mm, 46*mm])
        card.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), BG_DARK),
            ("LEFTPADDING", (0,0), (-1,0), 6),
            ("RIGHTPADDING", (0,0), (-1,0), 6),
            ("TOPPADDING", (0,0), (-1,0), 5),
            ("BOTTOMPADDING", (0,0), (-1,0), 5),
            ("BACKGROUND", (1,0), (1,0), ccolor),
            ("TEXTCOLOR", (1,0), (1,0), BLACK if conf >= 0.6 else WHITE),
            ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#f5f7fa")),
            ("TOPPADDING", (0,1), (-1,-1), 5),
            ("BOTTOMPADDING", (0,1), (-1,-1), 5),
            ("LEFTPADDING", (0,1), (-1,-1), 6),
            ("SPAN", (0,1), (-1,1)),
            ("SPAN", (0,2), (-1,2)),
            ("BOX", (0,0), (-1,-1), 0.5, BORDER),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        story.append(KeepTogether([card, Spacer(1, 5)]))

    # ── Confidence Heatmap ─────────────────────────────────────────────────
    if findings:
        story.append(Spacer(1, 4))
        story.append(Paragraph(T(labels["confidence_heatmap"]), section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 4))

        heatmap_data = [[T(labels["finding_col"]), T(labels["agent_col"]),
                          T(labels["confidence_col"]), T(labels["status_col"])]]
        for f in findings:
            conf = f.get("confidence", 0)
            heatmap_data.append([
                T((f.get("finding_type") or "finding").replace("_", " ").title()),
                T(f.get("agent_name", "-")),
                T(f"{conf:.0%}"),
                T(_conf_label(conf, labels)),
            ])
        heatmap = Table(heatmap_data, colWidths=[65*mm, 48*mm, 25*mm, 31*mm])
        style_cmds = [
            ("BACKGROUND", (0,0), (-1,0), BG_DARK),
            ("TEXTCOLOR", (0,0), (-1,0), AMBER),
            ("FONTNAME", (0,0), (-1,0), FONT_BOLD),
            ("FONTNAME", (0,1), (-1,-1), FONT_REGULAR),
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
                ("FONTNAME", (2, row_i), (3, row_i), FONT_BOLD),
            ]))
        heatmap.setStyle(TableStyle(style_cmds))
        story.append(heatmap)

    # ── Recommended Actions ──────────────────────────────────────────────
    prevention_findings = [f for f in final_report.get("findings", [])
                            if f.get("finding_type") in
                            ("patrol_strategy", "surveillance_action", "prevention_recommendation")]
    if prevention_findings:
        story.append(Spacer(1, 8))
        story.append(Paragraph(T(labels["recommended_actions"]), section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 4))
        for i, f in enumerate(prevention_findings, 1):
            story.append(Paragraph(f"{i}.  {T(f.get('summary', ''))}", body_style))

    # ── Footer ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        T(f"{labels['footer']} - {generated_at} - "
          f"{labels['case_id']} {case_id} - {labels['official_use_only']}"),
        S("Footer", fontSize=7, textColor=DIMTEXT, fontName=FONT_REGULAR,
          alignment=1),
    ))

    doc.build(story)
    return buf.getvalue()


def pdf_export_warnings(final_report: dict, language: str) -> list:
    """
    Stage D, Sprint 4: same degrade-gracefully checks
    `generate_investigation_pdf` runs internally, exposed standalone so
    the API route can put them in a response header without needing
    `generate_investigation_pdf` to change its return type (would break
    every existing direct caller) or rely on shared mutable state on the
    function object (would race under concurrent requests).
    """
    warnings = []
    if language in ("kn", "bilingual") and not KANNADA_FONT_AVAILABLE:
        warnings.append(f"Kannada font unavailable ({KANNADA_FONT_ERROR}); report rendered in English.")
    elif language in ("kn", "bilingual") and not (final_report.get("localized") or {}):
        warnings.append(
            "Kannada PDF requested but final_report has no 'localized' block "
            "(the investigation likely ran without language='kn'). Rendering in English."
        )
    return warnings
