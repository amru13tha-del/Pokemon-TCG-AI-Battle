"""Renders docs/writeup/strategy.md to strategy.pdf via reportlab.

Deliberately a focused renderer, not a general Markdown engine: it handles
exactly the constructs strategy.md uses -- headings, paragraphs, bullets,
numbered lists, pipe tables, fenced code, images, rules, and inline
bold/code. Anything else is passed through as plain text rather than
silently dropped.

Usage: python docs/writeup/figures/md_to_pdf.py
"""

import html
import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, Image,
                                ListFlowable, ListItem, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
WRITEUP_DIR = os.path.dirname(HERE)
MD_PATH = os.path.join(WRITEUP_DIR, "strategy.md")
PDF_PATH = os.path.join(WRITEUP_DIR, "strategy.pdf")

INK = colors.HexColor("#0b0b0b")
INK2 = colors.HexColor("#3d3c3a")
MUTED = colors.HexColor("#6b6a66")
RULE = colors.HexColor("#d8d7d0")
HDR_BG = colors.HexColor("#f2f2ef")
CODE_BG = colors.HexColor("#f7f7f5")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

ss = getSampleStyleSheet()


def style(name, **kw):
    base = dict(fontName="Helvetica", fontSize=9.3, leading=13.6,
                textColor=INK, alignment=TA_LEFT, spaceAfter=6)
    base.update(kw)
    return ParagraphStyle(name, **base)


S = {
    "title": style("t", fontName="Helvetica-Bold", fontSize=17, leading=21,
                   spaceAfter=4),
    "subtitle": style("st", fontSize=9.6, textColor=MUTED, spaceAfter=10),
    "h1": style("h1", fontName="Helvetica-Bold", fontSize=13.2, leading=17,
                spaceBefore=13, spaceAfter=6),
    "h2": style("h2", fontName="Helvetica-Bold", fontSize=10.8, leading=14.5,
                spaceBefore=9, spaceAfter=4),
    "h3": style("h3", fontName="Helvetica-Bold", fontSize=9.8, leading=13,
                spaceBefore=7, spaceAfter=3),
    "body": style("b"),
    "bullet": style("bu", spaceAfter=3),
    "code": style("c", fontName="Courier", fontSize=7.6, leading=10.2,
                  textColor=INK2, backColor=CODE_BG, borderPadding=6,
                  spaceBefore=4, spaceAfter=8),
    "cellh": style("ch", fontName="Helvetica-Bold", fontSize=8.0, leading=10.4,
                   spaceAfter=0),
    "cell": style("cl", fontSize=8.0, leading=10.4, spaceAfter=0),
    "caption": style("cap", fontSize=7.8, textColor=MUTED, spaceBefore=2,
                     spaceAfter=9),
}


def inline(text):
    """Markdown inline -> reportlab mini-HTML.

    Images can't be embedded mid-paragraph here, so an inline ![alt](src)
    degrades to its alt text in italics rather than leaking raw markup into
    the PDF (which is exactly what an earlier version did)."""
    text = re.sub(r"!\[(.*?)\]\((.*?)\)", r"*\1*", text)
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier" size="8.4">\1</font>', text)
    # italics: single * not adjacent to another *
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)
    return text


def image_flowable(path, max_w, max_h=190 * mm):
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        iw, ih = im.size
    scale = min(max_w / iw, max_h / ih)
    return Image(path, width=iw * scale, height=ih * scale)


def build_table(rows):
    header, body = rows[0], rows[1:]
    data = [[Paragraph(inline(c), S["cellh"]) for c in header]]
    for r in body:
        data.append([Paragraph(inline(c), S["cell"]) for c in r])
    ncols = len(header)
    # first column gets more room; the rest split evenly
    if ncols > 2:
        first = CONTENT_W * 0.32
        rest = (CONTENT_W - first) / (ncols - 1)
        widths = [first] + [rest] * (ncols - 1)
    else:
        widths = [CONTENT_W / ncols] * ncols
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HDR_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, RULE),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def parse(md):
    flow = []
    lines = md.split("\n")
    i = 0
    first_heading = True

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()

        # fenced code
        if line.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            code = html.escape("\n".join(buf)).replace(" ", "&nbsp;")
            flow.append(Paragraph(code.replace("\n", "<br/>"), S["code"]))
            continue

        # image (may sit inside a paragraph line)
        m = re.match(r"^!\[(.*?)\]\((.*?)\)\s*$", line)
        if m:
            alt, src = m.group(1), m.group(2)
            path = os.path.normpath(os.path.join(WRITEUP_DIR, src))
            if os.path.exists(path):
                flow.append(Spacer(1, 3))
                flow.append(image_flowable(path, CONTENT_W))
                if alt:
                    flow.append(Paragraph(inline(alt), S["caption"]))
            i += 1
            continue

        # table
        if line.startswith("|") and i + 1 < len(lines) and re.match(
                r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:|-]+$", "".join(cells)):
                    rows.append(cells)
                i += 1
            flow.append(Spacer(1, 2))
            flow.append(build_table(rows))
            flow.append(Spacer(1, 8))
            continue

        # horizontal rule
        if re.match(r"^---+\s*$", line):
            flow.append(Spacer(1, 3))
            flow.append(HRFlowable(width="100%", thickness=0.6, color=RULE,
                                   spaceBefore=2, spaceAfter=7))
            i += 1
            continue

        # headings
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level, text = len(m.group(1)), m.group(2)
            if level == 1 and first_heading:
                flow.append(Paragraph(inline(text), S["title"]))
                first_heading = False
            else:
                key = {1: "h1", 2: "h1", 3: "h2", 4: "h3"}[level]
                flow.append(Paragraph(inline(text), S[key]))
            i += 1
            continue

        # bullet / numbered list block
        if re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
            items = []
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            while i < len(lines) and (re.match(r"^\s*[-*]\s+", lines[i])
                                      or re.match(r"^\s*\d+\.\s+", lines[i])):
                txt = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", lines[i].rstrip())
                items.append(ListItem(Paragraph(inline(txt), S["bullet"]),
                                      leftIndent=12))
                i += 1
            flow.append(ListFlowable(
                items, bulletType="1" if ordered else "bullet",
                bulletFontSize=8, leftIndent=14, bulletOffsetY=-1,
                spaceAfter=7))
            continue

        # blank
        if not line.strip():
            i += 1
            continue

        # paragraph (accumulate until blank / structural line)
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|\||```|---+\s*$|!\[|\s*[-*]\s|\s*\d+\.\s)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            flow.append(Paragraph(inline(" ".join(buf)), S["body"]))
        else:
            i += 1

    return flow


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.4)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 11 * mm,
                      "PTCG AI Battle Challenge - Strategy Track writeup")
    canvas.drawRightString(PAGE_W - MARGIN, 11 * mm, f"Page {doc.page}")
    canvas.restoreState()


def main():
    md = open(MD_PATH, encoding="utf-8").read()
    doc = BaseDocTemplate(PDF_PATH, pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=20 * mm,
                          title="PTCG AI Battle Challenge - Strategy Writeup",
                          author="amru13tha-del")
    frame = Frame(MARGIN, 20 * mm, CONTENT_W, PAGE_H - MARGIN - 20 * mm,
                  id="main")
    doc.addPageTemplates([PageTemplate(id="t", frames=[frame], onPage=footer)])
    doc.build(parse(md))
    size_kb = os.path.getsize(PDF_PATH) / 1024
    print(f"wrote {PDF_PATH} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
