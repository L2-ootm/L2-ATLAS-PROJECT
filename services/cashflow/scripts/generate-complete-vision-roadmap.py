#!/usr/bin/env python3
"""Generate the evidence-based L2 Cashflow vision and roadmap PDF."""

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "output" / "pdf" / "L2-Cashflow-Visao-e-Roadmap.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

NAVY = HexColor("#102A43")
BLUE = HexColor("#2563EB")
TEAL = HexColor("#0F766E")
GREEN = HexColor("#047857")
AMBER = HexColor("#B45309")
RED = HexColor("#B91C1C")
INK = HexColor("#243B53")
MUTED = HexColor("#627D98")
LINE = HexColor("#D9E2EC")
PALE = HexColor("#F0F4F8")
PALE_BLUE = HexColor("#EFF6FF")
PALE_GREEN = HexColor("#ECFDF5")
PALE_AMBER = HexColor("#FFFBEB")

W, H = A4
MARGIN = 17 * mm
CONTENT = W - 2 * MARGIN
base = getSampleStyleSheet()
TITLE = ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=27, leading=31, textColor=NAVY, alignment=TA_LEFT, spaceAfter=5 * mm)
SUBTITLE = ParagraphStyle("subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=13, leading=18, textColor=BLUE, spaceAfter=7 * mm)
H1 = ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=3 * mm)
H2 = ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=14.5, textColor=TEAL, spaceBefore=3 * mm, spaceAfter=1.5 * mm)
BODY = ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=9, leading=13, textColor=INK, spaceAfter=2.3 * mm)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.4, leading=9.8, textColor=MUTED)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=4.5 * mm, firstLineIndent=-3.2 * mm, spaceAfter=1.2 * mm)
CALLOUT = ParagraphStyle("callout", parent=BODY, backColor=PALE_BLUE, borderColor=HexColor("#BFDBFE"), borderWidth=.7, borderPadding=7, textColor=NAVY, spaceAfter=3 * mm)
CALLOUT_GREEN = ParagraphStyle("calloutgreen", parent=CALLOUT, backColor=PALE_GREEN, borderColor=HexColor("#A7F3D0"))
CALLOUT_AMBER = ParagraphStyle("calloutamber", parent=CALLOUT, backColor=PALE_AMBER, borderColor=HexColor("#FDE68A"))
TH = ParagraphStyle("th", parent=SMALL, fontName="Helvetica-Bold", textColor=white)
TD = ParagraphStyle("td", parent=SMALL, textColor=INK)


def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(items):
    return [p(f"- {item}", BULLET) for item in items]


def table(rows, widths, header=True):
    cooked = [[p(str(cell), TH if header and i == 0 else TD) for cell in row] for i, row in enumerate(rows)]
    t = Table(cooked, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), .35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [white, PALE]),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    t.setStyle(TableStyle(commands))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN, 13.5 * mm, W - MARGIN, 13.5 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.2)
    canvas.drawString(MARGIN, 8.8 * mm, "L2 Cashflow · visão funcional e roadmap · julho 2026")
    canvas.drawRightString(W - MARGIN, 8.8 * mm, str(doc.page))
    canvas.restoreState()


def section(story, title, intro=None):
    story.append(p(title, H1))
    story.append(HRFlowable(width=CONTENT, thickness=1.4, color=BLUE, spaceAfter=3 * mm))
    if intro:
        story.append(p(intro))


def page(story):
    story.append(PageBreak())


def build():
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=16 * mm, bottomMargin=19 * mm, title="L2 Cashflow - Visão Funcional e Roadmap", author="L2 Systems")
    s = []

    s += [Spacer(1, 28 * mm), p("VISÃO FUNCIONAL E ROADMAP", ParagraphStyle("tag", parent=SMALL, fontName="Helvetica-Bold", fontSize=9, textColor=TEAL, spaceAfter=5 * mm)), p("L2 CASHFLOW", TITLE), p("Gestão financeira, FinOps de IA e plataforma modular para operações brasileiras", SUBTITLE), HRFlowable(width=CONTENT, thickness=2, color=BLUE, spaceAfter=10 * mm), p("Documento técnico-funcional baseado no código atual, no banco local, no build verificado e no master plan de evolução.", CALLOUT_GREEN), Spacer(1, 18 * mm), table([
        ["Escopo", "Estado analisado", "Estrutura"],
        ["Produto + arquitetura + execução", "Código em services/cashflow em 11/07/2026", "Atual, parcial, planejado e pesquisa"],
    ], [CONTENT*.32, CONTENT*.34, CONTENT*.34]), Spacer(1, 7 * mm), p("O documento diferencia evidência implementada de intenção planejada. Integrações externas, compliance fiscal e módulos enterprise só são tratados como concluídos quando existe implementação verificável.", SMALL)]
    page(s)

    section(s, "1. Resumo executivo", "O Cashflow é uma aplicação financeira funcional que combina operação básica de caixa com monitoramento de custos de IA. O produto atual já possui UI, persistência local/cloud, APIs, ferramentas MCP e módulos enterprise de análise. O objetivo de longo prazo é consolidar esse núcleo em uma plataforma financeira modular com contabilidade de partidas dobradas, compliance brasileiro, pagamentos, reconciliação e extensibilidade.")
    s += [p("Tese do produto", H2), p("Unificar receita, despesa, faturamento, uso de IA e margem em um sistema auditável, capaz de explicar o custo de servir cada cliente e acionar controles antes que a operação ultrapasse limites.", CALLOUT), p("Legenda de maturidade", H2), table([
        ["Status", "Definição"],
        ["IMPLEMENTADO", "Código, tela ou endpoint existe e o build de produção compila."],
        ["PARCIAL", "Base técnica existe, mas faltam controles, integração externa, testes ou operação completa."],
        ["PLANEJADO", "Incluído no master plan com dependências e ordem de execução."],
        ["PESQUISA", "Mapeado como possibilidade futura; ainda exige decisão e especificação."],
    ], [CONTENT*.24, CONTENT*.76]), p("Verificação desta edição", H2)]
    s += bullets([
        "Build Next.js de produção concluído com sucesso: 24 páginas/rotas geradas.",
        "Cinco endpoints de API identificados: Atlas, MCP, tokens, webhook de uso e avaliação de orçamento.",
        "Vinte tabelas de domínio encontradas no banco SQLite local.",
        "Sete ferramentas MCP verificadas no servidor Cashflow.",
        "O smoke test de rotas exige servidor ativo; executado sem servidor, reportou 15 falhas de conexão. Isso não contradiz o build, mas revela que o teste não inicia a aplicação automaticamente.",
    ])
    page(s)

    section(s, "2. Módulos operacionais implementados")
    s.append(table([
        ["Módulo", "Capacidades presentes", "Status / limite"],
        ["Clientes", "Cadastro, edição, exclusão, ativos, valor mensal e vínculo com despesas/faturas.", "IMPLEMENTADO; auth e tenant ainda não fechados."],
        ["Contratos", "Contas de cliente, planos, contrato, datas, status e receita contratada.", "PARCIAL; ciclo contratual e assinatura externa não comprovados."],
        ["Faturas", "Criação, status pendente/pago/atrasado, vencimento, filtros e alertas.", "IMPLEMENTADO; emissão fiscal e cobrança real são planejadas."],
        ["Despesas", "Categorias, recorrência, competência mensal e associação opcional a cliente.", "IMPLEMENTADO; aprovação, anexos e GL ainda ausentes."],
        ["Sócios", "Carteiras, aportes, retiradas, transações e saldos.", "IMPLEMENTADO como módulo interno legado."],
        ["Fluxo de caixa", "Projeção mensal, saldo acumulado, comparação entre meses e alertas.", "IMPLEMENTADO com modelo determinístico simples."],
        ["Relatórios base", "Receita, despesa, lucro, impostos MEI, clientes e visualizações operacionais.", "IMPLEMENTADO; não equivale a demonstrações contábeis."],
    ], [CONTENT*.18, CONTENT*.50, CONTENT*.32]))
    s += [p("Cálculo tributário atual", H2), p("O módulo tax.ts implementa uma estimativa específica de MEI: DAS mensal fixo, limite anual, percentual utilizado, saldo de limite e alertas. É uma calculadora operacional, não um motor tributário versionado e não deve ser confundida com apuração fiscal completa.", CALLOUT_AMBER), p("Principais telas", H2)]
    s += bullets(["Dashboard, clientes, contratos, faturas, despesas, fluxo de caixa, sócios e relatórios.", "As rotas base são pré-renderizadas; módulos enterprise com dados agregados usam renderização dinâmica quando necessário."])
    page(s)

    section(s, "3. FinOps de IA e módulos enterprise")
    s.append(table([
        ["Módulo", "Função real", "Maturidade"],
        ["Usage events", "Registra provedor, modelo, tokens, cache, tools, buscas, custo USD/BRL, receita e margem atribuída.", "IMPLEMENTADO"],
        ["Rate cards", "Preços por modelo e busca, capacidades e contexto; base para normalização.", "IMPLEMENTADO; atualização de preços precisa governança."],
        ["Normalizador", "Converte evento de uso em custo com rate card e fallback.", "IMPLEMENTADO; exige testes financeiros."],
        ["Budget/degradation", "Avalia gasto por usuário e produz decisão de risco/modelo.", "PARCIAL; execução depende de webhook/roteador externo."],
        ["P&L por cliente", "Confronta receita contratada, custo de IA e margem.", "IMPLEMENTADO para o modelo atual."],
        ["Cost Explorer", "Agrupa custo por modelo e usuário e calcula indicadores de cache/uso.", "IMPLEMENTADO"],
        ["Forecast enterprise", "Projeção de fim de mês e simulação de margem.", "IMPLEMENTADO; modelo ainda simples."],
        ["Billing Plus", "Assinaturas, eventos, taxas, repasses e métricas B2B2C.", "PARCIAL; Stripe/Hotmart ao vivo não comprovados."],
        ["Research Center", "Jobs, custo, valor estimado e ROI de pesquisa.", "IMPLEMENTADO como controle interno."],
        ["Audit", "Registro e visualização de ações em audit_log.", "PARCIAL; identidade e cobertura de eventos ainda limitadas."],
        ["Reports", "Relatórios comercial e operacional com exportação CSV.", "IMPLEMENTADO"],
    ], [CONTENT*.19, CONTENT*.50, CONTENT*.31]))
    s += [p("Valor diferencial", H2), p("A combinação mais madura do produto atual é FinOps + margem por cliente. O Cashflow já possui o caminho técnico para receber telemetria de IA, precificar o uso, agregar por cliente/usuário/modelo e apresentar impacto financeiro.", CALLOUT_GREEN)]
    page(s)

    section(s, "4. Fluxos funcionais reais")
    s += [p("Fluxo A - operação financeira", H2), table([
        ["Entrada", "Processamento", "Saída"],
        ["Cliente + valor mensal", "Cadastro e contrato", "Receita prevista e contexto de margem"],
        ["Fatura + vencimento", "Status e atualização", "Pendência, pagamento ou atraso"],
        ["Despesa + categoria", "Recorrência e vínculo opcional", "Custo mensal e custo por cliente"],
        ["Aporte/retirada", "Transação de carteira", "Saldo por sócio"],
    ], [CONTENT*.30, CONTENT*.35, CONTENT*.35]), p("Fluxo B - custo de IA", H2), table([
        ["Etapa", "Componente", "Resultado"],
        ["1. Receber", "POST /api/webhooks/tokens", "Evento de uso normalizado no payload"],
        ["2. Persistir", "usage_events", "Ledger operacional de uso e custo"],
        ["3. Precificar", "model_rate_cards + normalizer", "Custo por chamada em USD/BRL"],
        ["4. Agregar", "enterprise.ts", "P&L, explorer, forecast e reports"],
        ["5. Controlar", "engine/degradation", "Decisão de alerta ou redução de modelo"],
        ["6. Notificar", "webhook dispatcher", "Evento enviado ao ATLAS/roteador quando configurado"],
    ], [CONTENT*.18, CONTENT*.38, CONTENT*.44]), p("Fluxo C - consulta por agente", H2), p("O ATLAS acessa o Cashflow via MCP para listar clientes, buscar cliente, obter resumo financeiro, listar faturas, listar despesas, registrar despesa e consultar uso de IA. O transporte usa HTTP e validação de API key.", CALLOUT)]
    page(s)

    section(s, "5. Arquitetura atual")
    s += [table([
        ["Camada", "Implementação", "Responsabilidade"],
        ["Interface", "Next.js App Router + React", "Páginas base e dashboards enterprise"],
        ["Ações", "Server Actions", "CRUD e revalidação de páginas"],
        ["Domínio", "forecast, tax, normalizer, degradation", "Cálculos e decisões"],
        ["Dados", "Repository interfaces", "Contrato comum de acesso"],
        ["Persistência local", "better-sqlite3", "Desenvolvimento e operação local"],
        ["Persistência cloud", "Supabase/PostgreSQL", "Backend alternativo por configuração"],
        ["Integração", "REST, MCP e webhooks", "Consulta, ingestão e eventos"],
    ], [CONTENT*.20, CONTENT*.34, CONTENT*.46]), p("Seleção de backend", H2), p("ATLAS_CASHFLOW_DB define local ou supabase. Sem valor explícito, o código detecta a presença das variáveis Supabase. Cada domínio básico possui implementações SQLite e Supabase sob uma interface comum.", CALLOUT), p("Stack verificada", H2)]
    s += bullets(["Next.js 16.1.6, React 19.2.3 e TypeScript 5.", "SQLite via better-sqlite3 12.6.2 e Supabase JS 2.108.2.", "MCP SDK 1.29, Recharts 3.7, jsPDF 4.2, docx 9.7 e Tailwind CSS 4.", "Build estático/dinâmico de 24 rotas concluído com sucesso nesta revisão."])
    s += [p("Limite arquitetural atual", H2), p("O domínio base usa repositories, enquanto parte do enterprise acessa funções agregadas em lib/db/enterprise.ts. Antes da expansão, essas superfícies precisam convergir para contratos claros, transações e testes de paridade entre backends.", CALLOUT_AMBER)]
    page(s)

    section(s, "6. APIs, MCP e automações")
    s.append(table([
        ["Superfície", "Operações", "Observação"],
        ["/api/atlas", "GET resumo; POST ping, clientes, despesas, faturas, resumo e eventos", "API inbound protegida por key"],
        ["/api/mcp", "GET/POST/DELETE", "Transporte MCP streamable HTTP"],
        ["/api/webhooks/tokens", "POST telemetria de IA", "Aceita aliases de campos e metadata JSON"],
        ["/api/engine/evaluate", "POST avaliação por usuário/cliente", "Proteção por cron secret fora de dev"],
        ["/api/tokens", "GET/POST legado", "Superfície de compatibilidade"],
    ], [CONTENT*.25, CONTENT*.36, CONTENT*.39]))
    s += [p("Ferramentas MCP implementadas", H2)] + bullets(["get_clients", "get_client_by_id", "get_financial_summary", "get_invoices", "get_expenses", "add_expense", "get_ai_usage"])
    s += [p("Segurança existente e lacunas", H2), table([
        ["Existe", "Ainda necessário"],
        ["API key, cron secret, validação Zod no MCP, separação de backends", "Auth de usuário, RBAC real, tenants, rate limiting, secrets lifecycle, CSRF/session controls, RLS validado"],
    ], [CONTENT*.42, CONTENT*.58]), p("Nenhuma integração externa deve ser classificada como operacional apenas pela existência de tabelas ou nomes de gateway. Execução de pagamentos, emissão fiscal, Open Finance e sincronização contábil permanecem no roadmap até haver adapters, testes e evidência de ambiente.", CALLOUT_AMBER)]
    page(s)

    section(s, "7. Modelo de dados atual")
    s.append(table([
        ["Grupo", "Tabelas verificadas", "Uso"],
        ["Base", "Client, Invoice, Expense", "Clientes, cobrança e custos"],
        ["Sócios", "Partner, PartnerTransaction", "Carteira e movimentações internas"],
        ["FinOps legado", "AITokenLog", "Registro original de tokens"],
        ["Enterprise", "client_accounts, contracts, plans, user_entitlements", "Conta, contrato, plano e acesso"],
        ["Uso e preços", "usage_events, model_rate_cards, search_rate_cards", "Telemetria e precificação"],
        ["Billing", "plus_subscriptions, billing_events, invoice_line_items", "Assinatura, eventos e itens"],
        ["Pesquisa", "research_jobs", "Custo e ROI de pesquisa"],
        ["Sistema", "system_users, audit_log", "Identidade futura e auditoria"],
    ], [CONTENT*.18, CONTENT*.45, CONTENT*.37]))
    s += [p("Leitura correta do banco local", H2), p("O snapshot dev.db contém 20 tabelas. Na revisão, apenas Partner (2 registros) e research_jobs (2 registros) possuíam dados; as demais estavam vazias. Isso confirma schema e caminhos de código, mas não constitui evidência de operação com dados reais.", CALLOUT), p("Evolução de dados necessária", H2)]
    s += bullets(["Adicionar tenant_id e políticas RLS antes de multi-tenancy real.", "Introduzir Chart of Accounts, journal entries e journal lines para partidas dobradas.", "Definir idempotency keys para webhooks, billing e pagamentos.", "Versionar regras tributárias, rate cards e câmbio por vigência.", "Migrar relatórios para fontes contábeis reconciliadas quando o GL estiver ativo."])
    page(s)

    section(s, "8. Qualidade, riscos e dívidas atuais")
    s.append(table([
        ["Risco", "Evidência", "Tratamento"],
        ["Cálculo financeiro sem suíte", "package.json não possui runner unit/integration; apenas test:routes", "Vitest + fast-check + golden masters"],
        ["Smoke test dependente de servidor", "15 falhas fetch quando executado sem app ativa", "Fixture que inicia servidor ou teste contra handler"],
        ["Dual backend divergente", "Implementações SQLite/Supabase separadas", "Contract tests compartilhados"],
        ["Sem GL", "Relatórios derivam de entidades operacionais", "Partidas dobradas antes de compliance"],
        ["Auth/RBAC incompletos", "system_users existe, mas não fecha fluxo de identidade", "Auth, roles, tenant e RLS"],
        ["Webhooks e billing", "Adapters/entrega externa sem evidência end-to-end", "Idempotência, retry, DLQ e testes de contrato"],
        ["Regra MEI fixa", "Constantes no código", "Motor versionado com fontes e vigência"],
        ["Concentração em enterprise.ts", "Agregações e persistência no mesmo módulo", "Separar serviços, queries e repositories"],
    ], [CONTENT*.23, CONTENT*.39, CONTENT*.38]))
    s += [p("Gate mínimo antes de expansão", H2)] + bullets(["Testes P0 para tax, normalizer, degradation, forecast e dispatcher.", "Contrato de repository executado contra SQLite e Supabase.", "Autenticação e isolamento por tenant.", "Idempotência e auditoria em toda mutação financeira.", "Definição contábil do GL revisada antes de módulos fiscais."])
    page(s)

    section(s, "9. Roadmap real - fundações e ciclo financeiro")
    s.append(table([
        ["Onda", "Módulos", "Resultado verificável", "Dependência"],
        ["F1", "Auth, RBAC, tenant, RLS", "Usuários e dados isolados por empresa", "Base atual"],
        ["F2", "Chart of Accounts + General Ledger", "Débitos = créditos; períodos e auditoria", "F1"],
        ["F3", "AP, AR, invoicing, expenses", "Ciclo operacional refletido no GL", "F2"],
        ["F4", "Payments + reconciliation", "Pagamento e extrato conciliados de forma idempotente", "F3"],
        ["F5", "Fiscal year + closing", "Períodos bloqueáveis e fechamento reproduzível", "F2-F4"],
    ], [CONTENT*.13, CONTENT*.30, CONTENT*.39, CONTENT*.18]))
    s += [p("Critical path", H2), p("Auth/tenant -> General Ledger -> Tax Engine -> NFe/SPED -> Multi-Entity -> Marketplace. O General Ledger é o principal ponto de alavancagem: a pesquisa mapeia 28 módulos dependentes e 42 módulos no escopo total.", CALLOUT), p("Definição de pronto para o GL", H2)]
    s += bullets(["Journal imutável após posting, com reversão explícita.", "Cada transação balanceia débitos e créditos.", "Plano de contas versionado e contas de controle.", "Fechamento impede lançamentos retroativos sem processo autorizado.", "Relatórios reconciliam com journal e passam golden masters.", "Property-based tests cobrem invariantes e arredondamento monetário."])
    page(s)

    section(s, "10. Roadmap real - compliance Brasil")
    s.append(table([
        ["Módulo", "Escopo planejado", "Condição de entrada"],
        ["Tax Engine", "Regras versionadas para MEI, Simples, IRPJ, CSLL, INSS e PIS/COFINS", "GL + calendário + fontes oficiais"],
        ["NFS-e", "São Paulo primeiro, ABRASF/adapters municipais", "Tax engine + certificados + homologação"],
        ["NFe", "SEFAZ/SVRS, autorização, eventos e contingência", "Tax engine + XML + certificados"],
        ["SPED", "EFD-Contribuições, EFD-ICMS/IPI, ECD e ECF", "GL contábil + fiscal validado"],
        ["eSocial", "S-1200 e S-1299 no escopo inicial", "Dados de folha + eventos versionados"],
        ["LGPD", "Consentimento, retenção, exportação e erasure", "Mapa de dados + política de tenant"],
    ], [CONTENT*.20, CONTENT*.47, CONTENT*.33]))
    s += [p("Estratégia", H2), p("Cada obrigação entra como adapter versionado por jurisdição, layout e vigência. Homologação, certificados, filas, reprocessamento e evidência de entrega fazem parte do módulo; gerar um arquivo não basta para classificar compliance como concluído.", CALLOUT_AMBER), p("Riscos externos", H2)]
    s += bullets(["Mudança frequente de layouts e regras.", "Dependência de certificados e ambientes governamentais.", "Responsabilidade legal de cálculos incorretos.", "Necessidade de revisão contábil/fiscal independente.", "Reforma tributária e transição CBS/IBS exigem decisões específicas."])
    page(s)

    section(s, "11. Roadmap real - bancos, enterprise e ecossistema")
    s.append(table([
        ["Bloco", "Módulos", "Objetivo"],
        ["Bancos", "OFX, CNAB 240/400, Belvo/Open Finance", "Importar e normalizar transações"],
        ["Reconciliação", "Matching por valor, data, descrição e confiança", "Ligar extrato, pagamento e journal"],
        ["Gateways", "Asaas, PagSeguro, Mercado Pago, Stripe", "Cobrança, Pix, boleto, cartão e eventos"],
        ["Enterprise", "Multi-entidade, intercompany, multi-moeda", "Consolidar empresas e moedas"],
        ["Analytics", "DuckDB/BI, materialized views, métricas", "Escalar análise e relatórios"],
        ["Segurança", "Encryption, PCI scope, pentest, observabilidade", "Reduzir risco operacional"],
        ["Plugins", "Manifesto, SDK, permissões e marketplace", "Extensão sem inflar o núcleo"],
        ["Growth", "Onboarding, templates, pricing e PLG", "Distribuição e ativação"],
    ], [CONTENT*.18, CONTENT*.42, CONTENT*.40]))
    s += [p("Módulos mantidos como pesquisa", H2), p("Revenue recognition, ativos fixos, estoque, lease accounting, transfer pricing e verticais de indústria permanecem no catálogo de pesquisa. Só entram no roadmap de execução após demanda validada, especificação contábil e capacidade de manutenção.", CALLOUT), p("Princípio de modularidade", H2), p("O núcleo deve permanecer pequeno: identidade, tenant, contas, GL, eventos, auditoria e contratos. Compliance, bancos, gateways, verticais e automações entram por módulos com contratos e permissões explícitas.")]
    page(s)

    section(s, "12. Plano de execução e colaboração")
    s.append(table([
        ["Trilha paralela", "Entregas", "Gate de integração"],
        ["Domínio financeiro", "Regras, exemplos, exceções, lançamentos e critérios", "Revisão financeira"],
        ["Arquitetura", "Schemas, interfaces, ADRs e dependências", "Revisão técnica"],
        ["Implementação", "Código, migrations, adapters e observabilidade", "Build + testes"],
        ["Qualidade", "Datasets sintéticos, unit, contract, integration e E2E", "Evidência reproduzível"],
        ["Pesquisa", "Fontes, vigência, alternativas e riscos", "Decisão registrada"],
    ], [CONTENT*.24, CONTENT*.47, CONTENT*.29]))
    s += [p("Branches e worktrees", H2), p("Cada frente usa branch própria no GitHub e Git worktree isolada. Pull requests pequenos conectam os trabalhos paralelos ao núcleo estável. Mudanças financeiras exigem evidência de teste e revisão de domínio antes do merge.", CALLOUT_GREEN), p("Sequência de entrega recomendada", H2)]
    s += bullets(["1. Corrigir harness de testes e cobrir cálculos atuais.", "2. Fechar auth, RBAC, tenant e RLS.", "3. Especificar e implementar GL mínimo com invariantes.", "4. Migrar faturas/despesas/pagamentos para eventos contábeis.", "5. Implementar reconciliação e um gateway piloto.", "6. Iniciar Tax Engine versionado e NFS-e em ambiente de homologação.", "7. Expandir somente após dados reais, métricas e operação estável."])
    s += [p("Métrica de velocidade", H2), p("Velocidade não é quantidade de módulos iniciados. É o tempo entre regra acordada e capacidade integrada, testada, auditável e reversível.", CALLOUT)]
    page(s)

    section(s, "13. Critérios de sucesso e fontes internas")
    s.append(table([
        ["Dimensão", "Indicador"],
        ["Confiabilidade", "Zero journal desbalanceado; idempotência em mutações financeiras"],
        ["Qualidade", "Cobertura P0, contract tests dual-backend e E2E dos fluxos críticos"],
        ["FinOps", "Custo por evento reconciliado com rate card e P&L por cliente explicável"],
        ["Operação", "Faturas, despesas, pagamentos e extratos reconciliáveis"],
        ["Segurança", "Tenant isolation validado; secrets e permissões auditáveis"],
        ["Compliance", "Layouts versionados, homologação e evidência de transmissão"],
        ["Entrega", "PRs pequenos, rollback definido e decisões registradas"],
    ], [CONTENT*.25, CONTENT*.75]))
    s += [p("Fontes de verdade desta edição", H2)]
    s += bullets([
        "Código em services/cashflow/app, lib, supabase e scripts.",
        "services/cashflow/BRIEF.md.",
        "research/master-plan/MASTER-PLAN.md e batches 1-5.",
        "research/modular-cashflow/REPORT.md e 42 findings.",
        "package.json e resultado do build Next.js executado nesta revisão.",
        "dev.db inspecionado para inventário de tabelas e dados locais.",
    ])
    s += [p("Decisões que continuam abertas", H2)]
    s += bullets(["Arquitetura definitiva de centros de custo/lucro.", "Estratégia multi-GAAP e escopo de reporting contábil.", "Sequência de adapters bancários e gateway piloto.", "Transição CBS/IBS e fronteira de responsabilidade fiscal.", "Critério de promoção de módulos pesquisados para roadmap ativo."])
    s += [p("Síntese", H2), p("O Cashflow já possui uma base funcional relevante e um diferencial claro em FinOps de IA. O próximo salto não depende de adicionar mais dashboards: depende de testes, identidade, isolamento, General Ledger e integração auditável. A partir dessas fundações, compliance Brasil e módulos financeiros podem crescer sem transformar velocidade em dívida.", CALLOUT_GREEN)]

    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    print(f"{OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
