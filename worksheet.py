from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def find_devanagari_font() -> Path | None:
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "Nirmala.ttf",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "NirmalaUI.ttf",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "mangal.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


class CountRow(Flowable):
    def __init__(self, symbol: str, count: int, width: float = 150 * mm, height: float = 16 * mm):
        super().__init__()
        self.symbol = symbol if symbol.isascii() else "*"
        self.count = count
        self.width = width
        self.height = height

    def draw(self) -> None:
        self.canv.setFont("Helvetica-Bold", 15)
        self.canv.setFillColor(colors.HexColor("#365b46"))
        self.canv.drawString(0, 4 * mm, f"Count {self.count} {self.symbol}  " + self.symbol * self.count)
        self.canv.setFillColor(colors.black)
        self.canv.setFont("Helvetica", 10)
        self.canv.drawString(125 * mm, 4 * mm, "Answer: __________")


def create_worksheet_pdf(
    words: list[dict[str, Any]],
    grade: str,
    subject: str,
    topic: str,
    language_name: str,
) -> bytes:
    if not words:
        raise ValueError("Add at least one approved vocabulary word before creating a worksheet.")
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"BoloBuddy {grade} worksheet",
        author="BoloBuddy",
    )

    styles = getSampleStyleSheet()
    font_name = "Helvetica"
    hindi_font = find_devanagari_font()
    if hindi_font:
        try:
            pdfmetrics.registerFont(TTFont("BoloBuddyDevanagari", str(hindi_font)))
            font_name = "BoloBuddyDevanagari"
        except (OSError, ValueError):
            hindi_font = None
    title_style = ParagraphStyle(
        "BoloTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=25,
        textColor=colors.HexColor("#315b46"),
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BoloBody", parent=styles["BodyText"], fontName=font_name, fontSize=11, leading=17
    )
    small_style = ParagraphStyle(
        "BoloSmall", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=13
    )

    story: list[Flowable] = [
        Paragraph("BoloBuddy Learning Adventure", title_style),
        Paragraph(f"<b>{grade}</b> · {subject} · {topic}", body_style),
        Spacer(1, 5 * mm),
        Paragraph("Name: ____________________________________    Date: ______________", body_style),
        Spacer(1, 7 * mm),
        Paragraph(f"<b>1. Match the words — {language_name}</b>", body_style),
        Paragraph("Draw a line from each English word to its matching word.", small_style),
        Spacer(1, 3 * mm),
    ]

    selected = words[: min(6, len(words))]
    english_rows = [[Paragraph(f"{index + 1}. {word['en'].title()}", body_style)] for index, word in enumerate(selected)]
    translated_words = [word["translation"] for word in selected]
    if len(translated_words) > 1:
        translated_words = translated_words[1:] + translated_words[:1]
    translated_rows = []
    for index, text in enumerate(translated_words):
        can_render_text = text.isascii() or (language_name == "Hindi" and hindi_font is not None)
        display_text = text if can_render_text else "________________"
        translated_rows.append(
            [Paragraph(f"{chr(65 + index)}. {display_text}", body_style if can_render_text else small_style)]
        )
    matching = Table(
        [[english_rows[index][0], translated_rows[index][0]] for index in range(len(selected))],
        colWidths=[82 * mm, 82 * mm],
        rowHeights=[13 * mm] * len(selected),
    )
    matching.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5faed")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c8ddba")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce8d2")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([matching, Spacer(1, 9 * mm), Paragraph("<b>2. Count and write</b>", body_style)])
    story.append(Paragraph("Count the groups. Write the number on the line.", small_style))
    for index, word in enumerate(selected[:4], start=1):
        story.append(CountRow(word["emoji"], index + 1))
    story.extend(
        [
            Spacer(1, 4 * mm),
            Paragraph("You did it! Keep practising a little every day.  ★  ★  ★", body_style),
            Spacer(1, 8 * mm),
            Paragraph(
                "Practice worksheet inspired by foundational literacy and numeracy learning. "
                "Not an official NIPUN Bharat assessment.",
                small_style,
            ),
        ]
    )
    doc.build(story)
    return buffer.getvalue()
