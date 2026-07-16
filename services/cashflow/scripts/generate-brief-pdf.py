#!/usr/bin/env python3
"""
Generate a styled PDF brief for L2 Cashflow - Professional Light Theme.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, HRFlowable, ListFlowable, ListItem, Frame, PageTemplate,
    FrameBreak, NextPageTemplate,
)
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import os

# ============================================================
# COLOR PALETTE (Professional Light Theme)
# ============================================================
WHITE = white
LIGHT_GRAY = HexColor("#F8F9FA")
GRAY_100 = HexColor("#F1F3F5")
GRAY_200 = HexColor("#E9ECEF")
GRAY_300 = HexColor("#DEE2E6")
GRAY_350 = HexColor("#D1D5DB")
GRAY_400 = HexColor("#CED4DA")
GRAY_500 = HexColor("#ADB5BD")
GRAY_600 = HexColor("#6C757D")
GRAY_700 = HexColor("#495057")
GRAY_800 = HexColor("#343A40")
GRAY_900 = HexColor("#212529")

BLUE_500 = HexColor("#3B82F6")
BLUE_600 = HexColor("#2563EB")
BLUE_700 = HexColor("#1D4ED8")

TEAL_500 = HexColor("#14B8A6")
TEAL_600 = HexColor("#0D9488")
TEAL_700 = HexColor("#0F766E")

GREEN_500 = HexColor("#10B981")
GREEN_600 = HexColor("#059669")
GREEN_700 = HexColor("#047857")

PURPLE_500 = HexColor("#8B5CF6")
PURPLE_600 = HexColor("#7C3AED")
PURPLE_700 = HexColor("#6D28D9")

RED_500 = HexColor("#EF4444")
RED_600 = HexColor("#DC2626")
RED_700 = HexColor("#B91C1C")

YELLOW_500 = HexColor("#FBBF24")
YELLOW_600 = HexColor("#F59E0B")
YELLOW_700 = HexColor("#D97706")

W, H = A4
LEFT_MARGIN = 20 * mm
RIGHT_MARGIN = 20 * mm
TOP_MARGIN = 25 * mm
BOTTOM_MARGIN = 25 * mm
CONTENT_WIDTH = W - LEFT_MARGIN - RIGHT_MARGIN

# ============================================================
# OUTPUT PATH
# ============================================================
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "compose", "reports")
os.makedirs(OUT_DIR, exist_ok=True)
OUTPUT = os.path.join(OUT_DIR, "L2-Cashflow-Brief.pdf")

# ============================================================
# STYLES
# ============================================================
styles = getSampleStyleSheet()

s_cover_title = ParagraphStyle(
    "CoverTitle", fontName="Helvetica-Bold", fontSize=28,
    leading=36, textColor=BLUE_700, alignment=TA_LEFT,
    spaceBefore=0, spaceAfter=8 * mm,
)
s_cover_subtitle = ParagraphStyle(
    "CoverSubtitle", fontName="Helvetica", fontSize=16,
    leading=22, textColor=BLUE_500, alignment=TA_LEFT,
    spaceBefore=0, spaceAfter=4 * mm,
)
s_cover_tagline = ParagraphStyle(
    "CoverTagline", fontName="Helvetica", fontSize=11,
    leading=16, textColor=GRAY_600, alignment=TA_LEFT,
    spaceBefore=0, spaceAfter=0,
)
s_section_h1 = ParagraphStyle(
    "H1", fontName="Helvetica-Bold", fontSize=20,
    leading=26, textColor=BLUE_800, alignment=TA_LEFT,
    spaceBefore=12 * mm, spaceAfter=4 * mm,
)
s_section_h2 = ParagraphStyle(
    "H2", fontName="Helvetica-Bold", fontSize=16,
    leading=22, textColor=BLUE_700, alignment=TA_LEFT,
    spaceBefore=8 * mm, spaceAfter=2 * mm,
)
s_section_h3 = ParagraphStyle(
    "H3", fontName="Helvetica-Bold", fontSize=13,
    leading=18, textColor=BLUE_600, alignment=TA_LEFT,
    spaceBefore=6 * mm, spaceAfter=1.5 * mm,
)
s_body = ParagraphStyle(
    "Body", fontName="Helvetica", fontSize=11,
    leading=16, textColor=GRAY_900, alignment=TA_JUSTIFY,
    spaceBefore=2 * mm, spaceAfter=3 * mm,
)
s_body_bold = ParagraphStyle(
    "BodyBold", fontName="Helvetica-Bold", fontSize=11,
    leading=16, textColor=GRAY_900, alignment=TA_JUSTIFY,
    spaceBefore=2 * mm, spaceAfter=3 * mm,
)
s_code = ParagraphStyle(
    "Code", fontName="Courier", fontSize=9,
    leading=13, textColor=BLUE_800, alignment=TA_LEFT,
    spaceBefore=2 * mm, spaceAfter=3 * mm,
    leftIndent=4 * mm, backColor=LIGHT_GRAY,
    borderColor=GRAY_300, borderWidth=0.5, borderPadding=3 * mm,
)
s_bullet = ParagraphStyle(
    "Bullet", fontName="Helvetica", fontSize=11,
    leading=16, textColor=GRAY_900, alignment=TA_LEFT,
    spaceBefore=1 * mm, spaceAfter=1 * mm,
    leftIndent=6 * mm,
)
s_bullet_strong = ParagraphStyle(
    "BulletStrong", fontName="Helvetica-Bold", fontSize=11,
    leading=16, textColor=BLUE_700, alignment=TA_LEFT,
    spaceBefore=1 * mm, spaceAfter=1 * mm,
    leftIndent=6 * mm,
)
s_table_header = ParagraphStyle(
    "TH", fontName="Helvetica-Bold", fontSize=10,
    leading=14, textColor=WHITE, alignment=TA_LEFT,
    spaceBefore=0, spaceAfter=0,
)
s_table_cell = ParagraphStyle(
    "TD", fontName="Helvetica", fontSize=9,
    leading=13, textColor=GRAY_900, alignment=TA_LEFT,
    spaceBefore=0, spaceAfter=0,
)
s_footer = ParagraphStyle(
    "Footer", fontName="Helvetica", fontSize=8,
    leading=12, textColor=GRAY_500, alignment=TA_CENTER,
)
s_caption = ParagraphStyle(
    "Caption", fontName="Helvetica-Oblique", fontSize=9,
    leading=13, textColor=GRAY_600, alignment=TA_CENTER,
    spaceBefore=1 * mm, spaceAfter=4 * mm,
)
s_meta = ParagraphStyle(
    "Meta", fontName="Helvetica", fontSize=10,
    leading=14, textColor=GRAY_700, alignment=TA_LEFT,
    spaceBefore=0, spaceAfter=1 * mm,
)
s_callout = ParagraphStyle(
    "Callout", fontName="Helvetica", fontSize=11,
    leading=16, textColor=TEAL_800, alignment=TA_LEFT,
    spaceBefore=3 * mm, spaceAfter=4 * mm,
    leftIndent=4 * mm, backColor=TEAL_50,
    borderColor=TEAL_300, borderWidth=0.5, borderPadding=3 * mm,
)

# ============================================================
# HELPERS
# ============================================================
def hbar(width=CONTENT_WIDTH, color=GRAY_300, thickness=0.5):
    return HRFlowable(width=width, thickness=thickness, color=color,
                       spaceBefore=0, spaceAfter=0, hAlign='LEFT')

def color_bar(color=TEAL_600, thickness=3):
    return HRFlowable(width=CONTENT_WIDTH, thickness=thickness, color=color,
                       spaceBefore=3 * mm, spaceAfter=4 * mm, hAlign='LEFT')

def bullet(text, style=s_bullet):
    return Paragraph(f"<bullet>&bull;</bullet> {text}", style)

def bullet_group(items, style_bullet_use=None):
    st = style_bullet_use or s_bullet
    return [bullet(item, st) for item in items]

def make_table(data, col_widths=None, header=True):
    """Cria uma tabela estilizada com tema profissional."""
    tbl = Table(data, colWidths=col_widths, hAlign="LEFT",
                repeatRows=1 if header else 0)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), BLUE_800),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY_300),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]
    tbl.setStyle(TableStyle(cmds))
    return tbl

def meta_line(label, value):
    return Paragraph(
        f'<font color="{BLUE_600.hexval()}">{label}:</font>  {value}',
        s_meta
    )

def bullet_table(lines):
    """Simple key-value table with two columns."""
    data = [[Paragraph(f'<font color="{BLUE_600.hexval()}">{k}</font>', s_table_cell),
             Paragraph(v, s_table_cell)] for k, v in lines]
    col_w = [CONTENT_WIDTH * 0.25, CONTENT_WIDTH * 0.75]
    tbl = Table(data, colWidths=col_w, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl

# ============================================================
# PAGE TEMPLATES (Header/Footer)
# ============================================================
def header_footer(canv, doc):
    canv.saveState()
    # thin top line
    canv.setStrokeColor(GRAY_300)
    canv.setLineWidth(0.3)
    canv.line(LEFT_MARGIN, H - TOP_MARGIN + 5*mm, W - RIGHT_MARGIN, H - TOP_MARGIN + 5*mm)
    # footer line
    canv.line(LEFT_MARGIN, BOTTOM_MARGIN - 3*mm, W - RIGHT_MARGIN, BOTTOM_MARGIN - 3*mm)
    # page number
    canv.setFont("Helvetica", 8)
    canv.setFillColor(GRAY_500)
    canv.drawRightString(W - RIGHT_MARGIN, BOTTOM_MARGIN - 9*mm, f"{doc.page}")
    canv.setFillColor(GRAY_500)
    canv.drawString(LEFT_MARGIN, BOTTOM_MARGIN - 9*mm, "L2 SYSTEMS — CONFIDENCIAL")
    canv.restoreState()

def cover_header_footer(canv, doc):
    canv.saveState()
    # Light blue header bar on cover
    canv.setFillColor(LIGHT_GRAY)
    canv.rect(0, H - TOP_MARGIN/2, W, TOP_MARGIN/2, fill=1, stroke=0)
    
    # Footer
    canv.setFont("Helvetica", 8)
    canv.setFillColor(GRAY_500)
    canv.drawRightString(W - RIGHT_MARGIN, BOTTOM_MARGIN - 9*mm, "Página 1")
    canv.drawString(LEFT_MARGIN, BOTTOM_MARGIN - 9*mm, "L2 SYSTEMS — CONFIDENCIAL")
    canv.restoreState()

def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=LEFT_MARGIN, rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN, bottomMargin=BOTTOM_MARGIN,
        title="L2 Cashflow — Brief Técnico",
        author="L2 Systems",
        subject="Brief do Módulo Cashflow — Arquitetura, Funcionalidades e Roadmap",
        keywords=["L2 Systems", "Cashflow", "FinOps", "BRIEF"],
    )

    story = []

    # ================================================================
    # COVER PAGE
    # ================================================================
    story.append(Spacer(1, 30 * mm))

    # Tag
    story.append(Paragraph("BRIEF TÉCNICO", ParagraphStyle(
        "CoverTag", fontName="Helvetica-Bold", fontSize=12,
        leading=16, textColor=BLUE_600, alignment=TA_LEFT,
        letterSpacing=2,
        spaceBefore=0, spaceAfter=6 * mm,
    )))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("L2 CASHFLOW", s_cover_title))
    story.append(Paragraph("Módulo de Gestão Financeira & FinOps", s_cover_subtitle))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Plataforma de FinOps para operações de IA — rastreamento de tokens, "
        "P&L por cliente, billing B2B2C, degradação ativa e integração com L2 ATLAS.",
        s_cover_tagline
    ))

    story.append(Spacer(1, 40 * mm))
    story.append(hbar(color=BLUE_600, thickness=2))
    story.append(Spacer(1, 8 * mm))

    meta_items = [
        ("Versão", "1.0"),
        ("Data", "Julho 2026"),
        ("Status", "Em produção"),
        ("Stack", "Next.js 16 · React 19 · TypeScript 5 · SQLite/Supabase"),
        ("Equipe", "Davi + Artur (L2 Systems)"),
        ("Classificação", "CONFIDENCIAL — uso interno e colaboradores autorizados"),
    ]
    data = [[Paragraph(f'<font color="{BLUE_600.hexval()}">{k}</font>', s_meta),
             Paragraph(v, s_meta)] for k, v in meta_items]
    meta_tbl = Table(data, colWidths=[CONTENT_WIDTH * 0.20, CONTENT_WIDTH * 0.80], hAlign="LEFT")
    meta_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(meta_tbl)

    story.append(PageBreak())

    # ================================================================
    # 1. O QUE É
    # ================================================================
    story.append(Paragraph("1. O QUE É", s_section_h1))
    story.append(color_bar())

    story.append(Paragraph(
        "O <b>L2 Cashflow</b> é o módulo de gestão financeira e FinOps da L2 Systems. "
        "Ele começou como um fluxo de caixa simples entre sócios e evoluiu para uma "
        "<b>plataforma de FinOps para operações de IA</b> — o tipo de sistema que uma "
        "empresa de tecnologia precisa para controlar quanto gasta com modelos de linguagem, "
        "quanto fatura por cliente, e quanto lucro sobra no final do mês.",
        s_body
    ))

    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "Hoje ele opera em produção dentro do ecossistema L2 ATLAS, integrado via "
        "protocolo MCP (Model Context Protocol) e webhooks em tempo real.",
        s_body
    ))

    # ================================================================
    # 2. O QUE JÁ FAZ
    # ================================================================
    story.append(Paragraph("2. O QUE JÁ FAZ (Estado Atual)", s_section_h1))
    story.append(color_bar(color=TEAL_600))

    # 2.1
    story.append(Paragraph("2.1 Gestão Financeira Base", s_section_h2))
    story.append(Spacer(1, 1*mm))

    fin_items = [
        ("<b>Clientes</b> — cadastro, contratos mensais, controle de pagamento recorrente, alertas de vencimento"),
        ("<b>Faturas</b> — emissão, acompanhamento (pendente, pago, atrasado), automação de status"),
        ("<b>Despesas</b> — categorizadas (Software, Marketing, Equipamento, Infraestrutura, Pessoal, Outros), recorrentes ou avulsas, vinculadas ou não a cliente"),
        ("<b>Carteira de Sócios</b> — injeções e retiradas de Artur e Davi com saldo atualizado em tempo real"),
        ("<b>Relatórios</b> — dashboard consolidado com gráficos de gastos, heatmap de uso e feed de atividades"),
    ]
    for item in fin_items:
        story.append(bullet(item))

    # 2.2
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("2.2 FinOps (Operações de IA)", s_section_h2))
    story.append(Spacer(1, 1*mm))

    finops_items = [
        ("<b>Rastreamento de tokens</b> — cada chamada a um modelo de IA é registrada com input tokens, output tokens, cache hit/miss, custo USD e BRL"),
        ("<b>Rate cards por modelo</b> — tabela com preço por 1M tokens input/output/cache, contexto máximo, flags de suporte (tools, caching, JSON)"),
        ("<b>Custo normalizado</b> — cálculo exato de cada evento usando rate cards do banco, com fallback se o modelo não estiver catalogado"),
        ("<b>Degradação ativa</b> — motor que monitora gasto por usuário e dispara webhooks para rebaixar modelos quando limites são excedidos (warning R$25 / hard cap R$35)"),
        ("<b>Forecasting</b> — projeção de custo mensal baseada na média diária, com alertas verde/amarelo/vermelho"),
    ]
    for item in finops_items:
        story.append(bullet(item))

    # 2.3
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("2.3 Billing B2B2C (Plus)", s_section_h2))
    story.append(Spacer(1, 1*mm))

    billing_items = [
        "Assinaturas premium de usuários finais com split de receita (gateway ~5%, L2 ~30%, cliente ~70%)",
        "Gateways suportados: Stripe, Hotmart",
        "Eventos de faturamento com rastreamento completo de taxas e repasses",
    ]
    for item in billing_items:
        story.append(bullet(item))

    # 2.4
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("2.4 Relatórios Enterprise", s_section_h2))
    story.append(Spacer(1, 1*mm))

    report_items = [
        "<b>P&L por cliente</b> — receita contratada vs custo de IA vs margem",
        "<b>Cost Explorer</b> — custo por modelo, top 10 usuários por gasto, taxa de cache hit",
        "<b>Forecast</b> — projeção de fim de mês + simulador de margem",
        "<b>Relatório Comercial</b> — receita total + Plus, margem bruta e líquida",
        "<b>Relatório Operacional</b> — sessões, tokens, custo médio por sessão, breakdown por modelo",
    ]
    for item in report_items:
        story.append(bullet(item))

    # ================================================================
    # 3. COMO FUNCIONA
    # ================================================================
    story.append(Paragraph("3. COMO FUNCIONA (Arquitetura)", s_section_h1))
    story.append(color_bar())

    # 3.1 Stack
    story.append(Paragraph("3.1 Stack Tecnológica", s_section_h2))
    stack_data = [
        ["Camada", "Tecnologia", "Versão"],
        ["Runtime", "Node.js", "20+"],
        ["Framework", "Next.js (App Router)", "16.1.6"],
        ["UI", "React + Tailwind CSS 4 + Framer Motion", "19.2.3"],
        ["Banco Local", "SQLite (better-sqlite3)", "12.6.2"],
        ["Banco Cloud", "PostgreSQL (Supabase)", "—"],
        ["Ícones", "Lucide React", "0.575"],
        ["Gráficos", "Recharts", "3.7"],
        ["Exportação", "jsPDF + docx", "—"],
        ["MCP SDK", "@modelcontextprotocol/sdk", "1.29"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(stack_data)],
        col_widths=[CONTENT_WIDTH * 0.22, CONTENT_WIDTH * 0.50, CONTENT_WIDTH * 0.28],
    )
    story.append(tbl)
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Dependências adicionais: clsx, tailwind-merge, jspdf-autotable, @opengsd/gsd-core.",
        s_caption
    ))

    # 3.2 Architecture
    story.append(Paragraph("3.2 Camadas da Aplicação", s_section_h2))
    arch_data = [
        ["Camada", "Onde", "Função"],
        ["Apresentação", "app/*/page.tsx + components/", "Páginas React com SSR/CSR"],
        ["Servidor", "app/actions.ts", "Server Actions com revalidatePath"],
        ["Dados", "lib/repositories/", "Interface + implementações SQLite/Supabase"],
        ["Banco", "lib/db/ + supabase/", "Schema SQLite + RPC functions PostgreSQL"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(arch_data)],
        col_widths=[CONTENT_WIDTH * 0.22, CONTENT_WIDTH * 0.30, CONTENT_WIDTH * 0.48],
    )
    story.append(tbl)

    # 3.3 Dual Backend
    story.append(Paragraph("3.3 Dual Backend (SQLite ↔ Supabase)", s_section_h2))
    story.append(Paragraph(
        "O sistema opera com dois backends intercambiáveis. A seleção é automática via variável de ambiente:",
        s_body
    ))
    dual_data = [
        ["ATLAS_CASHFLOW_DB=local", "Força SQLite (desenvolvimento local)"],
        ["ATLAS_CASHFLOW_DB=supabase", "Força Supabase (produção)"],
        ["Sem variável", "Auto-detect: Supabase se NEXT_PUBLIC_SUPABASE_URL + ANON_KEY existirem"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_cell) for cell in row] for row in dual_data],
        col_widths=[CONTENT_WIDTH * 0.35, CONTENT_WIDTH * 0.65],
        header=False,
    )
    story.append(tbl)
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "Ambos os backends são <b>non-destructive</b>: toda criação de tabela usa <font face='Courier' size='8'>IF NOT EXISTS</font>. "
        "Cada repositório existe em duas implementações em <font face='Courier' size='8'>lib/repositories/sqlite/</font> e "
        "<font face='Courier' size='8'>lib/repositories/supabase/</font>, ambas implementando a mesma interface TypeScript.",
        s_body
    ))

    # 3.4 Tables
    story.append(Paragraph("3.4 Tabelas do Banco (17)", s_section_h2))
    tbl_data = [
        ["Grupo", "Tabelas", "Propósito"],
        ["Base", "Client, Invoice, Expense, Partner, PartnerTransaction, AITokenLog", "Núcleo financeiro"],
        ["Enterprise", "client_accounts, contracts, plans, user_entitlements", "Clientes corporativos e planos"],
        ["FinOps", "usage_events, model_rate_cards, search_rate_cards", "Rastreamento de custos de IA"],
        ["Billing", "plus_subscriptions, billing_events, invoice_line_items", "Assinaturas e split de receita"],
        ["Pesquisa", "research_jobs", "ROI de pesquisa"],
        ["Sistema", "system_users, audit_log", "RBAC e auditoria"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(tbl_data)],
        col_widths=[CONTENT_WIDTH * 0.16, CONTENT_WIDTH * 0.36, CONTENT_WIDTH * 0.48],
    )
    story.append(tbl)
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "A tabela <b>usage_events</b> é o centro do FinOps — cada linha é um evento de uso de IA "
        "com custo breakdown completo (tokens, cache, modelo, usuário, custo USD/BRL).",
        s_body
    ))

    # 3.5 API Routes
    story.append(Paragraph("3.5 API Routes", s_section_h2))
    api_data = [
        ["Endpoint", "Método", "Função"],
        ["/api/atlas", "GET / POST", "REST API inbound para L2 Atlas"],
        ["/api/mcp", "GET / POST / DELETE", "Transport MCP com 7 ferramentas"],
        ["/api/webhooks/tokens", "POST", "Receiver de eventos de uso de IA"],
        ["/api/engine/evaluate", "POST", "Motor de degradação ativa"],
        ["/api/tokens", "GET / POST", "Log de tokens de IA (legacy)"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(api_data)],
        col_widths=[CONTENT_WIDTH * 0.28, CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.54],
    )
    story.append(tbl)

    # 3.6 Integração com ATLAS
    story.append(Paragraph("3.6 Integração com L2 ATLAS", s_section_h2))
    story.append(Paragraph(
        "O Cashflow não é isolado — ele conversa com o ATLAS por dois canais complementares:",
        s_body
    ))
    integ_data = [
        ["Canal", "Como funciona", "Uso"],
        ["MCP (Model Context Protocol)", "ATLAS chama ferramentas via HTTP+JSON tipado com Zod",
         "Queries: listar clientes, resumo financeiro, uso de IA"],
        ["Webhooks", "Cashflow dispara eventos push para o ATLAS",
         "Notificações: fatura paga, orçamento excedido, usuário degradado"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(integ_data)],
        col_widths=[CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.42, CONTENT_WIDTH * 0.40],
    )
    story.append(tbl)

    # ================================================================
    # 4. VISION: O QUE VAMOS FAZER
    # ================================================================
    story.append(Paragraph("4. O QUE VAMOS FAZER (Roadmap)", s_section_h1))
    story.append(color_bar(color=TEAL_600))
    story.append(Paragraph(
        "A visão de longo prazo é evoluir o Cashflow de uma ferramenta interna de FinOps para "
        "uma <b>plataforma financeira universal e modular</b>, capaz de atender qualquer tipo "
        "de negócio brasileiro — do MEI emitindo sua primeira NFS-e à empresa multi-entidade "
        "consolidando demonstrativos IFRS.",
        s_body
    ))
    story.append(Paragraph(
        "O master plan completo está em <font face='Courier' size='8'>research/master-plan/MASTER-PLAN.md</font>. "
        "Abaixo, a síntese das 7 fases organizadas por ordem de dependência.",
        s_body
    ))

    # Phase 1
    story.append(Paragraph("4.1 Fase 1 — Fundações", s_section_h2))
    story.append(Paragraph(
        "Antes de qualquer módulo novo, o sistema atual precisa de fundamentos que hoje estão fracos ou inexistentes:",
        s_body
    ))
    p1_items = [
        "<b>Auth + RBAC</b> — sistema de autenticação e permissões por função (admin, contador, visualizador, AP clerk, AR clerk)",
        "<b>Chart of Accounts</b> — plano de contas estruturado para contabilidade",
        "<b>General Ledger</b> — livro razão com lançamentos em partidas dobradas (débito = crédito). É a peça mais crítica: 28 módulos dependem dela",
        "<b>Multi-Tenancy</b> — isolamento por tenant via PostgreSQL Row Level Security. O <font face='Courier' size='8'>client_accounts</font> já é a entidade de tenant",
        "<b>Plugin System</b> — esqueleto para módulos carregáveis dinamicamente com manifesto TOML",
        "<b>Event Sourcing (prototype)</b> — journal append-only como trilha de auditoria no GL",
    ]
    for item in p1_items:
        story.append(bullet(item))

    # Phase 2
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("4.2 Fase 2 — Módulos Core", s_section_h2))
    p2_items = [
        "<b>Accounts Payable</b> — contas a pagar com state machine (draft → finalized → sent → paid → voided)",
        "<b>Accounts Receivable</b> — contas a receber com os mesmos estados",
        "<b>Invoicing</b> — geração de notas fiscais com itens de linha detalhados",
        "<b>Fiscal Year</b> — gestão de exercícios com travas de período",
        "<b>Expenses</b> — reescrita sobre o GL com categorização avançada e fluxo de aprovação",
        "<b>Payments (initial)</b> — execução de pagamentos via Pix, boleto",
    ]
    for item in p2_items:
        story.append(bullet(item))

    # Phase 3
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("4.3 Fase 3 — Compliance Brasil", s_section_h2))
    story.append(Paragraph(
        "Esta é a fase mais longa e de maior valor estratégico. É onde o Cashflow se diferencia "
        "de qualquer sistema genérico — compliance profundo com o ecossistema fiscal brasileiro.",
        s_body
    ))
    p3_items = [
        "<b>Tax Engine</b> — motor de impostos com regras versionadas por data de vigência (IRPJ, CSLL, INSS, Simples Nacional, PIS/COFINS)",
        "<b>NFS-e (São Paulo primeiro)</b> — integração com municípios via padrão ABRASF 2.03",
        "<b>NFe</b> — integração com SEFAZ (SVRS, expandindo para demais estados)",
        "<b>SPED</b> — geração de EFD-Contribuições, EFD-ICMS/IPI, ECD, ECF",
        "<b>eSocial</b> — S-1200 (remuneração) + S-1299 (fechamento)",
        "<b>LGPD</b> — consentimento, retenção programada, erasure",
    ]
    for item in p3_items:
        story.append(bullet(item))

    # Phase 4
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("4.4 Fase 4 — Pagamentos e Reconciliação", s_section_h2))
    p4_items = [
        "<b>Bank Reconciliation</b> — matching automático de transações com regras de confiança (60% valor + 25% data + 15% descrição)",
        "<b>Payment Gateways</b> — Asaas, PagSeguro, Mercado Pago, Stripe",
        "<b>Banking Integration</b> — via Belvo para agregação de contas",
        "<b>CNAB 240/400 + OFX</b> — importação de extratos bancários",
        "<b>Recurring Billing</b> — faturamento recorrente automático",
    ]
    for item in p4_items:
        story.append(bullet(item))

    # Phase 5
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("4.5 Fase 5 — Enterprise e Multi-Entidade", s_section_h2))
    p5_items = [
        "<b>Multi-Entity</b> — consolidação de múltiplas empresas com intercompany reconciliation",
        "<b>Analytics/BI</b> — dashboards operacionais e comerciais (DuckDB embedded + Metabase SDK)",
        "<b>Security Hardening</b> — envelope encryption AES-256-GCM, PCI SAQ A-EP, pentest",
        "<b>Performance</b> — otimização de queries, materialized views, PgBouncer",
    ]
    for item in p5_items:
        story.append(bullet(item))

    # Phase 6
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("4.6 Fase 6 — Crescimento e Marketplace", s_section_h2))
    p6_items = [
        "<b>Marketplace SDK</b> — sistema de plugins público para terceiros",
        "<b>Seed plugins (15-20)</b> — primeira leva de plugins próprios",
        "<b>PLG Engine</b> — invoice-as-viral-vector (cada fatura emitida é um canal de aquisição)",
        "<b>Onboarding Wizard</b> — wizard de 5 etapas para novos tenants em menos de 5 minutos",
        "<b>Pricing</b> — Free / R$79 / R$199 / R$499 + módulos adicionais",
    ]
    for item in p6_items:
        story.append(bullet(item))

    # Phase 7
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("4.7 Fase 7 — Escala e Otimização", s_section_h2))
    p7_items = [
        "<b>Full Test Suite</b> — suite completa de testes (ver Seção 5)",
        "<b>Load Testing</b> — 100K entradas de journal, 10 tenants simultâneos",
        "<b>Multi-Currency</b> — suporte a múltiplas moedas com fontes de câmbio (BCB, ECB, Fed)",
        "<b>Rust Cementation</b> — componentes críticos migrados para Rust (decisão D-022)",
    ]
    for item in p7_items:
        story.append(bullet(item))

    # Critical Path
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("4.8 Critical Path", s_section_h2))
    story.append(Paragraph(
        "A cadeia de dependências crítica que determina a ordem de construção:",
        s_body
    ))
    cp_data = [
        ["Etapa", "Módulos", "Nível de Dependência"],
        ["1", "Auth → General Ledger", "Fundação (0 dependências externas)"],
        ["2", "GL → Tax Engine", "Nível 1 (depende do GL)"],
        ["3", "Tax Engine → NFe / SPED", "Nível 2 (depende do Tax Engine)"],
        ["4", "NFe/SPED → Multi-Entity", "Nível 3"],
        ["5", "Multi-Entity → Marketplace", "Nível 4 (terminal)"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(cp_data)],
        col_widths=[CONTENT_WIDTH * 0.12, CONTENT_WIDTH * 0.50, CONTENT_WIDTH * 0.38],
    )
    story.append(tbl)
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "42 módulos no total, sendo 10 de complexidade XL. "
        "O <b>General Ledger</b> é o gargalo #1: 28 módulos dependem dela. "
        "Se ela estiver errada, 70% do sistema está errado.",
        s_callout
    ))

    # ================================================================
    # 5. TESTES
    # ================================================================
    story.append(PageBreak())
    story.append(Paragraph("5. ESTRATÉGIA DE TESTES", s_section_h1))
    story.append(color_bar(color=YELLOW_600))

    story.append(Paragraph(
        "<b>Zero testes existem hoje. Este é o maior risco do projeto.</b> "
        "Todo o código está em produção sem nenhuma cobertura automatizada. "
        "A estratégia completa está em <font face='Courier' size='8'>research/master-plan/batch4/B4-testing-strategy.md</font>.",
        s_callout
    ))

    # Pyramid
    story.append(Paragraph("5.1 Pirâmide de Testes", s_section_h2))
    pyramid_data = [
        ["Camada", "Cobertura", "Ferramenta", "O que cobre"],
        ["Unit (80%)", ">90% em lib/", "Vitest + fast-check", "Cálculos financeiros, invariantes, bordas"],
        ["Integration (15%)", ">80% rotas + repos", "Vitest + SQLite in-memory", "Wiring entre módulos, API contracts"],
        ["E2E (5%)", "100% fluxos críticos", "Playwright", "Caminhos felizes de cada domínio"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(pyramid_data)],
        col_widths=[CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.22, CONTENT_WIDTH * 0.42],
    )
    story.append(tbl)

    story.append(Paragraph("5.2 Prioridade de Implementação", s_section_h2))
    priority_data = [
        ["Prioridade", "Arquivo", "Justificativa"],
        ["P0", "lib/tax.ts", "Cálculos de MEI com implicação legal"],
        ["P0", "lib/engine/normalizer.ts", "Custo de IA por modelo — impacto financeiro direto"],
        ["P0", "lib/engine/degradation.ts", "Lógica de degradação — previne custos explosivos"],
        ["P1", "lib/forecast.ts", "Projeções de fluxo de caixa usadas em decisões de negócio"],
        ["P1", "lib/webhooks/dispatcher.ts", "Payload shape e comportamento de retry"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(priority_data)],
        col_widths=[CONTENT_WIDTH * 0.12, CONTENT_WIDTH * 0.28, CONTENT_WIDTH * 0.60],
    )
    story.append(tbl)

    # Property-based testing
    story.append(Paragraph("5.3 Property-Based Testing", s_section_h2))
    story.append(Paragraph(
        "Módulos financeiros usarão <b>fast-check</b> para verificar invariantes automaticamente "
        "em vez de depender apenas de exemplos fixos. Exemplos de propriedades:",
        s_body
    ))
    prop_data = [
        ["Função", "Propriedade"],
        ["calculateMEITax", "percentUsed sempre em [0, 100]"],
        ["calculateMEITax", "remaining sempre ≥ 0"],
        ["calculateUsageCost", "costBrl === costUsd × fxRate"],
        ["calculateUsageCost", "todos os custos ≥ 0"],
        ["generateCashFlowProjection", "cumulativeBalance é soma cumulativa de estimatedProfit"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(prop_data)],
        col_widths=[CONTENT_WIDTH * 0.40, CONTENT_WIDTH * 0.60],
    )
    story.append(tbl)

    # Golden Masters
    story.append(Paragraph("5.4 Golden Master (Snapshot) Tests", s_section_h2))
    story.append(Paragraph(
        "Relatórios financeiros e outputs de forecast usarão golden masters — snapshots do "
        "output esperado que falham em qualquer drift não intencional:",
        s_body
    ))
    gm_items = [
        "Mudança intencional → executar com <font face='Courier' size='8'>UPDATE_GOLDEN_MASTERS=1 vitest</font> para regenerar",
        "Commit do snapshot atualizado + justificativa no PR",
        "CI sem o flag → falha se output mudou inesperadamente",
    ]
    for item in gm_items:
        story.append(bullet(item))

    # Contract Tests
    story.append(Paragraph("5.5 Contract Tests (Dual-Backend)", s_section_h2))
    story.append(Paragraph(
        "Cada implementação de repositório (SQLite e Supabase) roda os mesmos testes de contrato, "
        "garantindo que ambas as versões se comportam identicamente para quem as consome.",
        s_body
    ))
    ct_items = [
        "Round-trip CRUD: create → getById → update → getById → delete",
        "Filtros: getByStatus, getByMonth, getByClient aplicam corretamente",
        "Foreign keys: cascade e set null funcionam como esperado",
    ]
    for item in ct_items:
        story.append(bullet(item))

    # E2E
    story.append(Paragraph("5.6 Fluxos E2E (Playwright)", s_section_h2))
    e2e_data = [
        ["Fluxo", "Etapas"],
        ["Fatura → pagamento → reconciliação", "Criar cliente → criar fatura → marcar paga → verificar status"],
        ["Despesa recorrente → projeção", "Criar despesa recorrente → verificar projeção mensal"],
        ["Carteira de sócio", "Injeção → retirada → verificar saldo"],
        ["Degradação ativa", "Simular uso → exceder hard cap → verificar webhook"],
        ["Forecast", "Input clientes + despesas → verificar projeção de 6 meses"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(e2e_data)],
        col_widths=[CONTENT_WIDTH * 0.30, CONTENT_WIDTH * 0.70],
    )
    story.append(tbl)

    # Refactors
    story.append(Paragraph("5.7 Refactors Necessários Antes de Testar", s_section_h2))
    story.append(Paragraph(
        "O código atual tem dependências diretas que impedem testes isolados. "
        "Quatro refactors pequenos e não-breaking são necessários:",
        s_body
    ))
    ref_data = [
        ["Arquivo", "Mudança", "Por quê"],
        ["lib/db/index.ts", "Aceitar Database injetado em vez de singleton global", "SQLite in-memory nos testes"],
        ["lib/engine/normalizer.ts", "Aceitar Supabase client como parâmetro", "Mockar na unit test"],
        ["lib/engine/degradation.ts", "Aceitar client + dispatcher como parâmetros", "Mockar na unit test"],
        ["lib/webhooks/dispatcher.ts", "Aceitar fetch como parâmetro ou usar vi.stubGlobal", "Mockar requisições HTTP"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(ref_data)],
        col_widths=[CONTENT_WIDTH * 0.28, CONTENT_WIDTH * 0.42, CONTENT_WIDTH * 0.30],
    )
    story.append(tbl)

    # CI
    story.append(Paragraph("5.8 Pipeline CI/CD de Testes", s_section_h2))
    story.append(Paragraph(
        "Os testes serão executados em pipeline GitHub Actions com gates progressivos:",
        s_body
    ))
    ci_items = [
        "Unit → Integration → E2E (gates sequenciais, E2E só roda se unit passar)",
        "Cobertura mínima: 85% statements, 80% branches, 85% functions — PRs abaixo são bloqueados",
        "Security scan (ZAP Baseline) toda noite em staging",
    ]
    for item in ci_items:
        story.append(bullet(item))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Estimativa de Esforço — Testes", s_section_h2))
    effort_data = [
        ["Atividade", "Horas"],
        ["Setup (vitest + Playwright + CI pipeline)", "28h"],
        ["Unit tests — arquivos críticos (tax, normalizer, degradation)", "~20h"],
        ["Integration tests — repositories + API routes", "~20h"],
        ["E2E tests — 6 fluxos críticos", "~16h"],
        ["Contract tests + golden masters", "~10h"],
        ["Total — primeira rodada", "~94h"],
        ["Manutenção por sprint", "~9h"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(effort_data)],
        col_widths=[CONTENT_WIDTH * 0.55, CONTENT_WIDTH * 0.45],
        header=True,
    )
    story.append(tbl)

    # ================================================================
    # 6. DOCUMENTOS RELACIONADOS
    # ================================================================
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("6. DOCUMENTOS RELACIONADOS", s_section_h1))
    story.append(color_bar(color=GRAY_600))

    doc_data = [
        ["Documento", "Localização", "Conteúdo"],
        ["Master Plan", "research/master-plan/MASTER-PLAN.md", "Roadmap completo, 42 módulos, decisões arquiteturais, riscos"],
        ["Relatório Técnico", "docs/compose/reports/cashflow-code-report.md", "Análise detalhada do código-fonte"],
        ["Estratégia de Testes", "research/master-plan/batch4/B4-testing-strategy.md", "Plano completo de testes com estimativas"],
        ["Pesquisa Modular", "research/modular-cashflow/REPORT.md", "42 descobertas sobre módulos financeiros universais"],
        ["Schema SQL", "supabase/schema.sql", "DDL completo + 6 RPC functions PostgreSQL"],
    ]
    tbl = make_table(
        [[Paragraph(cell, s_table_header if i == 0 else s_table_cell) for cell in row]
         for i, row in enumerate(doc_data)],
        col_widths=[CONTENT_WIDTH * 0.20, CONTENT_WIDTH * 0.38, CONTENT_WIDTH * 0.42],
    )
    story.append(tbl)

    # ================================================================
    # FINAL PAGE
    # ================================================================
    story.append(Spacer(1, 20 * mm))
    story.append(hbar(color=BLUE_600, thickness=1))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "L2 SYSTEMS — Todos os direitos reservados.",
        ParagraphStyle("FinalNote", fontName="Helvetica-Oblique", fontSize=8,
                       leading=12, textColor=GRAY_700, alignment=TA_CENTER)
    ))
    story.append(Paragraph(
        "Este documento é confidencial e de uso interno da equipe L2 Systems "
        "e colaboradores autorizados. Não deve ser distribuído sem autorização.",
        ParagraphStyle("FinalNote2", fontName="Helvetica", fontSize=7,
                       leading=10, textColor=GRAY_600, alignment=TA_CENTER)
    ))

    # ================================================================
    # BUILD
    # ================================================================
    # Use the cover template for page 1, content template for the rest
    doc.build(story,
              onFirstPage=cover_header_footer,
              onLaterPages=header_footer)
    print(f"PDF gerado: {OUTPUT}")

if __name__ == "__main__":
    build_pdf()
