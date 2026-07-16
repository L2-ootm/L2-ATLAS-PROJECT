#!/usr/bin/env python3
"""Insert the GitHub/worktree learning model into the Cashflow collaboration PDF."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[3]
PDF = ROOT / "output" / "pdf" / "L2-Cashflow-Guia-de-Colaboracao-Paralela.pdf"
TMP = ROOT / "tmp" / "pdfs" / "cashflow-worktree-update.pdf"
TMP_INTRO = ROOT / "tmp" / "pdfs" / "cashflow-collaboration-intro.pdf"
TMP_FINAL = ROOT / "tmp" / "pdfs" / "cashflow-collaboration-final.pdf"

NAVY = HexColor("#102A43")
BLUE = HexColor("#2563EB")
TEAL = HexColor("#0F766E")
INK = HexColor("#243B53")
MUTED = HexColor("#627D98")
LINE = HexColor("#D9E2EC")
PALE = HexColor("#F0F4F8")
PALE_BLUE = HexColor("#EFF6FF")

W, H = A4
MARGIN = 18 * mm
CONTENT = W - 2 * MARGIN
base = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=NAVY, spaceAfter=3 * mm)
H2 = ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=TEAL, spaceBefore=3 * mm, spaceAfter=1.5 * mm)
BODY = ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.4, leading=13.6, textColor=INK, spaceAfter=2.5 * mm)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.8, leading=10.5, textColor=MUTED)
CALLOUT = ParagraphStyle("callout", parent=BODY, backColor=PALE_BLUE, borderColor=HexColor("#BFDBFE"), borderWidth=0.7, borderPadding=8, textColor=NAVY, spaceAfter=4 * mm)
TH = ParagraphStyle("th", parent=SMALL, fontName="Helvetica-Bold", textColor=white)
TD = ParagraphStyle("td", parent=SMALL, textColor=INK)


def p(text, style=BODY):
    return Paragraph(text, style)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN, 14 * mm, W - MARGIN, 14 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 9 * mm, "L2 Cashflow · material de colaboração · julho 2026")
    canvas.drawRightString(W - MARGIN, 9 * mm, "modelo de trabalho")
    canvas.restoreState()


def make_table(rows, widths):
    cooked = [[p(cell, TH if i == 0 else TD) for cell in row] for i, row in enumerate(rows)]
    t = Table(cooked, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, PALE]),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def build_update_page():
    TMP.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(TMP), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=17 * mm, bottomMargin=20 * mm)
    story = [
        p("O MODELO DE TRABALHO", H1),
        p("Cashflow como produto compartilhado e fundação prática de desenvolvimento", H2),
        p("A colaboração acontecerá diretamente no Cashflow por GitHub. Cada módulo, correção ou pesquisa aplicada terá sua própria branch e uma Git worktree isolada. Isso permite conduzir várias frentes - inclusive com agentes - ao mesmo tempo, sem trocar arquivos, esconder mudanças ou bloquear outras entregas.", CALLOUT),
        p("Como o trabalho circula", H2),
        make_table([
            ["Etapa", "Prática", "Resultado"],
            ["Escolher", "Selecionar um módulo pequeno e definir problema, escopo e critérios.", "Uma entrega compreensível e limitada."],
            ["Isolar", "Criar branch no GitHub e worktree própria para a frente.", "Trabalho paralelo sem interferir na branch estável."],
            ["Construir", "A frente produz spec, código, testes e documentação com apoio de agentes.", "Artefatos reais, não apenas conversa."],
            ["Validar", "Revisão financeira dos números e revisão técnica da implementação.", "Erros de domínio e engenharia são encontrados cedo."],
            ["Integrar", "Abrir pull request pequeno; corrigir feedback; executar os gates.", "Histórico rastreável e merge seguro."],
            ["Aprender", "Registrar decisões, falhas e padrões reutilizáveis.", "A próxima entrega começa com mais conhecimento."],
        ], [CONTENT * .16, CONTENT * .47, CONTENT * .37]),
        Spacer(1, 3 * mm),
        p("Por que isso acelera o Cashflow", H2),
        p("As frentes deixam de ser sequenciais. Regras, cenários e métricas podem evoluir em paralelo com arquitetura e integração; agentes apoiam pesquisa, rascunhos, testes e documentação. Branches e worktrees mantêm cada entrega separada até a revisão."),
        p("Por que isso também desenvolve autonomia", H2),
        p("O Cashflow será um ambiente prático de aprendizado. Cada contribuição percorre uma parte maior do ciclo de software: requisitos, modelagem, Git, uso de agentes, testes, pull request, revisão, integração e release. A participação não exige formação prévia em desenvolvimento; a competência técnica cresce dentro de entregas reais."),
        make_table([
            ["Conhecimento adquirido", "Aplicação futura"],
            ["GitHub, branches, worktrees e pull requests", "Organizar seus próprios produtos e colaborar com segurança."],
            ["Modelagem de software financeiro", "Transformar conhecimento financeiro em entidades, regras e fluxos."],
            ["Prompts, contexto e revisão de agentes", "Usar IA para construir sem aceitar resultados como caixa-preta."],
            ["Testes e datasets sintéticos", "Validar automações sem expor dados reais."],
            ["Arquitetura modular", "Reutilizar fundações do Cashflow em softwares próprios."],
        ], [CONTENT * .41, CONTENT * .59]),
        Spacer(1, 3 * mm),
        p("O resultado é uma relação de mão dupla: a colaboração aumenta a velocidade e a qualidade do Cashflow, enquanto a experiência acumulada forma uma base concreta para novos softwares e automações financeiras.", CALLOUT),
    ]
    doc.build(story, onFirstPage=footer)


def build_intro_page():
    doc = SimpleDocTemplate(str(TMP_INTRO), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=17 * mm, bottomMargin=20 * mm)
    story = [
        p("1. Conhecimento de domínio como base de desenvolvimento", H1),
        p("Conhecimento de finanças, economia e operação é uma contribuição de primeira ordem. Agentes de IA ajudam a transformar esse conhecimento em especificações, cenários de teste, protótipos e código inicial. O trabalho decisivo continua sendo formular bem o problema, reconhecer exceções e validar os resultados."),
        p("A unidade de trabalho recomendada", H2),
        p("Cada contribuição deve terminar em um artefato verificável: uma regra com exemplos, uma tabela de decisão, um cenário financeiro, um schema, um teste, uma tela protótipo, um módulo pequeno ou uma revisão documentada. Conversas orientam; artefatos permitem integrar.", CALLOUT),
        p("2. O que pode ser compartilhado", H1),
        make_table([
            ["Categoria", "Exemplos", "Benefício"],
            ["Pesquisa", "Comparativos, regulação, APIs e padrões contábeis", "Evita duplicação de descoberta"],
            ["Modelos de domínio", "Conta, lançamento, fatura, pagamento e reconciliação", "Cria uma linguagem comum"],
            ["Cenários e testes", "Fechamento, atraso, estorno, split e competência", "Detecta erros antes da integração"],
            ["Componentes", "Forecast, importadores, categorização e relatórios", "Acelera módulos reutilizáveis"],
            ["Padrões de agentes", "Prompts, checklists, avaliações e handoffs", "Melhora consistência e autonomia"],
            ["Aprendizados", "Falhas, decisões, riscos e limites", "Reduz retrabalho nos dois projetos"],
        ], [CONTENT * .22, CONTENT * .44, CONTENT * .34]),
        p("3. O que não deve ser compartilhado por padrão", H1),
        p("- Segredos, credenciais, chaves, dados bancários ou dados pessoais reais."),
        p("- Dados de clientes ou amostras que permitam reidentificação."),
        p("- Código copiado sem confirmação de licença e autoria."),
        p("- Regras fiscais tratadas como definitivas sem fonte, vigência e revisão profissional."),
        p("- Mudanças amplas no repositório principal antes de testes e revisão."),
    ]
    doc.build(story, onFirstPage=footer)


def build_final_page():
    doc = SimpleDocTemplate(str(TMP_FINAL), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=17 * mm, bottomMargin=20 * mm)
    story = [
        p("7. Como trabalhar em paralelo com controle", H1),
        make_table([
            ["Mecanismo", "Prática"],
            ["Fonte única", "Cada módulo mantém uma spec curta, uma frente responsável e um status."],
            ["Contratos estáveis", "Entradas, saídas e invariantes são acordadas antes da divisão da implementação."],
            ["Branches e worktrees", "Cada frente opera isoladamente sem alterar o fluxo principal."],
            ["Entregas pequenas", "Cada integração adiciona uma capacidade demonstrável e reversível."],
            ["Datasets sintéticos", "Cenários úteis são compartilhados sem exposição de dados sensíveis."],
            ["Revisão cruzada", "Modelagem, números e implementação passam por validações independentes."],
            ["Log de decisões", "Motivos, alternativas, riscos e evidências permanecem registrados."],
        ], [CONTENT * .29, CONTENT * .71]),
        p("8. Como os dois projetos avançam mais rápido", H1),
        p("- A mesma pesquisa alimenta dois contextos reais e revela requisitos mais gerais."),
        p("- Casos de uso diferentes verificam se um módulo é realmente reutilizável."),
        p("- Regras e cenários evoluem em paralelo com arquitetura e integração."),
        p("- Agentes produzem rascunhos; a revisão concentra atenção em decisões e validação."),
        p("- Testes e datasets compartilhados reduzem regressões durante a transferência de código."),
        p("- Falhas descobertas em um projeto tornam-se prevenção documentada no outro."),
        p("9. Critério de pronto para uma contribuição", H1),
        make_table([
            ["Critério", "Pergunta de verificação"],
            ["Compreensível", "O objetivo pode ser explicado sem recuperar toda a conversa?"],
            ["Rastreável", "Fontes, premissas e decisões estão registradas?"],
            ["Testável", "Existem exemplos, invariantes e pelo menos um caso-limite?"],
            ["Seguro", "Dados sensíveis estão ausentes e ações de risco exigem aprovação?"],
            ["Integrável", "O contrato está claro, o escopo é pequeno e as dependências estão declaradas?"],
            ["Reutilizável", "Elementos genéricos estão separados das particularidades de cada empresa?"],
        ], [CONTENT * .27, CONTENT * .73]),
        p("Próximo passo", H2),
        p("Selecionar um módulo-piloto e produzir quatro artefatos: definição do problema, modelo de domínio, dataset sintético e critérios de aceite. Forecast ou reconciliação são bons candidatos. O General Ledger requer uma etapa de discovery mais cuidadosa antes da implementação.", CALLOUT),
        p("A colaboração preserva a autonomia de cada projeto e compartilha conhecimento em formatos verificáveis, reutilizáveis e integráveis. Interfaces claras conectam os trabalhos paralelos sem exigir sincronização permanente."),
    ]
    doc.build(story, onFirstPage=footer)


def insert_page():
    build_update_page()
    build_intro_page()
    build_final_page()
    original = PdfReader(str(PDF))
    update = PdfReader(str(TMP))
    intro = PdfReader(str(TMP_INTRO))
    final = PdfReader(str(TMP_FINAL))
    writer = PdfWriter()
    writer.add_page(original.pages[0])
    writer.add_page(update.pages[0])
    writer.add_page(intro.pages[0])
    # The current five-page guide already contains the old update and intro
    # pages at indexes 1 and 2. Preserve only the remaining content pages.
    writer.add_page(original.pages[3])
    writer.add_page(final.pages[0])
    with PDF.open("wb") as fh:
        writer.write(fh)
    print(f"{PDF} ({len(writer.pages)} pages, {PDF.stat().st_size} bytes)")


if __name__ == "__main__":
    insert_page()
