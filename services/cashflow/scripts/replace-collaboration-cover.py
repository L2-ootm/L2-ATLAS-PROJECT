#!/usr/bin/env python3
"""Replace the collaboration guide cover with a clean institutional cover."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[3]
PDF = ROOT / "output" / "pdf" / "L2-Cashflow-Guia-de-Colaboracao-Paralela.pdf"
TMP = ROOT / "tmp" / "pdfs" / "collaboration-cover.pdf"

NAVY = HexColor("#102A43")
BLUE = HexColor("#2563EB")
TEAL = HexColor("#0F766E")
MUTED = HexColor("#627D98")
LINE = HexColor("#D9E2EC")
W, H = A4
MARGIN = 18 * mm


def make_cover():
    TMP.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(TMP), pagesize=A4)
    c.setTitle("L2 Cashflow - Guia de Colaboração Paralela")
    c.setAuthor("L2 Systems")

    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN, H - 56 * mm, "GUIA PRÁTICO")

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(MARGIN, H - 72 * mm, "COLABORAÇÃO PARALELA")

    c.setFillColor(BLUE)
    c.setFont("Helvetica", 13)
    c.drawString(MARGIN, H - 84 * mm, "Desenvolvimento compartilhado do L2 Cashflow")
    c.drawString(MARGIN, H - 91 * mm, "com GitHub, branches e worktrees isoladas")

    c.setStrokeColor(BLUE)
    c.setLineWidth(2)
    c.line(MARGIN, H - 103 * mm, W - MARGIN, H - 103 * mm)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, H - 125 * mm, "PESQUISA  /  PRODUTO  /  ENGENHARIA  /  APRENDIZADO")

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(MARGIN, H - 138 * mm, "Um modelo de colaboração para acelerar entregas, compartilhar conhecimento")
    c.drawString(MARGIN, H - 145 * mm, "e construir fundações reutilizáveis para softwares financeiros.")

    c.setStrokeColor(LINE)
    c.setLineWidth(0.4)
    c.line(MARGIN, 14 * mm, W - MARGIN, 14 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN, 9 * mm, "L2 Cashflow · guia de colaboração · julho 2026")
    c.drawRightString(W - MARGIN, 9 * mm, "1")
    c.showPage()
    c.save()


def replace_cover():
    make_cover()
    original = PdfReader(str(PDF))
    cover = PdfReader(str(TMP))
    writer = PdfWriter()
    writer.add_page(cover.pages[0])
    for page in original.pages[1:]:
        writer.add_page(page)
    with PDF.open("wb") as fh:
        writer.write(fh)
    print(f"{PDF} ({len(writer.pages)} pages, {PDF.stat().st_size} bytes)")


if __name__ == "__main__":
    replace_cover()
