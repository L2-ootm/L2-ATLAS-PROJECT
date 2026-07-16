#!/usr/bin/env python3
"""Generate ATLAS X outreach PDF into the user's Downloads folder."""

from __future__ import annotations

import os

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_PATH = os.path.join(os.path.expanduser("~"), "Downloads", "ATLAS-X-Outreach-Collab-Devs.pdf")

NAVY = HexColor("#0B0D12")
BLUE = HexColor("#4F8BFF")
MUTED = HexColor("#5A6570")
LIGHT = HexColor("#F4F6F8")
BORDER = HexColor("#D0D5DD")
GREEN = HexColor("#1A7F4B")


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSub",
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=NAVY,
            spaceBefore=14,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=BLUE,
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=NAVY,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletPoint",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=NAVY,
            leftIndent=12,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=MUTED,
            spaceAfter=2,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Link",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=BLUE,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Quote",
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=HexColor("#1F2937"),
            leftIndent=10,
            rightIndent=10,
            spaceBefore=4,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Cell",
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=NAVY,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellBold",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10.5,
            textColor=NAVY,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Footer",
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=MUTED,
            alignment=TA_CENTER,
        )
    )
    return styles


def link(url: str, label: str | None = None) -> str:
    lab = label or url
    return f'<link href="{url}" color="#4F8BFF"><u>{lab}</u></link>'


def cell_p(text: str, styles, bold: bool = False):
    return Paragraph(text, styles["CellBold"] if bold else styles["Cell"])


def post_table(rows_data, styles, header_color=BLUE):
    header = [
        cell_p("#", styles, True),
        cell_p("Fit / por que", styles, True),
        cell_p("Link", styles, True),
    ]
    data = [header]
    for num, why, url in rows_data:
        data.append(
            [
                cell_p(str(num), styles, True),
                cell_p(why, styles),
                Paragraph(link(url), styles["Link"]),
            ]
        )
    t = Table(data, colWidths=[1.0 * cm, 9.2 * cm, 7.0 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_color),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 1), (-1, -1), white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def main() -> None:
    styles = build_styles()
    story = []

    # Cover
    story.append(Spacer(1, 2.2 * cm))
    story.append(Paragraph("L2 ATLAS", styles["CoverTitle"]))
    story.append(
        Paragraph("Outreach no X — Colaboradores de Engenharia", styles["CoverSub"])
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        HRFlowable(
            width=480,
            thickness=1,
            color=BLUE,
            spaceBefore=4,
            spaceAfter=12,
            hAlign="CENTER",
        )
    )
    story.append(
        Paragraph(
            "Documento operacional: o que e o ATLAS, o que comentar, onde comentar (links), "
            "e o que postar no perfil.",
            styles["CoverSub"],
        )
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Destinatario: colaborador / operador L2", styles["Small"]))
    story.append(
        Paragraph(
            "Idioma: PT-BR · Uso: recruiting organico no X (sem postar automaticamente)",
            styles["Small"],
        )
    )
    story.append(
        Paragraph(
            "Gerado a partir da analise do monorepo L2-ATLAS-PROJECT + busca publica no X",
            styles["Small"],
        )
    )
    story.append(Spacer(1, 0.6 * cm))
    story.append(
        Paragraph(
            "<b>Escopo:</b> cockpit auditavel de agentes · Hermes foundation · multi-surface · "
            "MCP/policy · Cashflow modular · collab open research preview",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    # 1 ATLAS
    story.append(Paragraph("1. O que e o ATLAS (base para o pitch)", styles["H1"]))
    story.append(
        Paragraph(
            "O <b>L2 ATLAS</b> e um <b>cockpit de operador de IA</b> (open research preview, MIT). "
            "Nao e \"mais um chat agent\". Fecha o loop entre intencao do operador, execucao do "
            "agente e resultados auditaveis.",
            styles["Body"],
        )
    )
    story.append(Paragraph("Uma frase", styles["H2"]))
    story.append(
        Paragraph(
            "Cockpit de operador: missions/runs, runtime (Hermes-evolved + adapters), audit-first, "
            "policy/approvals, LLM Wiki, multi-surface (web, terminal, TUI, Discord), gateway Rust, "
            "modulos ativaveis (ex. Cashflow).",
            styles["Body"],
        )
    )
    story.append(Paragraph("Arquitetura em camadas", styles["H2"]))
    for line in [
        "<b>Foundation</b> — Hermes Agent vendored em foundation/atlas-hermes/ (plugins/skills/MCP/tools).",
        "<b>Runtime</b> — services/agent-runtime (Python): missions, policy, audit, context, adapters.",
        "<b>Schemas</b> — packages/atlas-core (Pydantic v2 frozen models).",
        "<b>Gateway</b> — native/atlas-core-rs (Rust REST + SQLite; writes via CLI).",
        "<b>Cockpit</b> — services/web-ui-react (React): Observatory, Missions, Runs, Ledger, Wiki…",
        "<b>Sidecars</b> — Discord bot; Cashflow (Next.js, modulo financeiro/FinOps, ativavel).",
    ]:
        story.append(Paragraph(f"• {line}", styles["BulletPoint"]))

    story.append(Paragraph("Diferenciais que devs de verdade se importam", styles["H2"]))
    for line in [
        "Audit-first: cada acao e um audit_event (Ledger forense).",
        "Approval-gated writes / permission broker multi-surface.",
        "LLM Wiki com proveniencia — nao so RAG efemero.",
        "Tool Manifest v0 (YAML + adapter) no mesmo choke point de policy.",
        "Python prototype + cementacao Rust no gateway (D-022).",
        "Modulos (Cashflow FinOps) plugaveis sem engordar o default.",
    ]:
        story.append(Paragraph(f"• {line}", styles["BulletPoint"]))

    story.append(Paragraph("O que NAO e (ainda)", styles["H2"]))
    story.append(
        Paragraph(
            "Nao e enterprise-ready, nao e fully autonomous production, nao substitui devs. "
            "E preview de pesquisa honesto — ver LIMITATIONS / known-failures no repo.",
            styles["Body"],
        )
    )

    # 2 Principle
    story.append(Paragraph("2. Principio de outreach no X", styles["H1"]))
    story.append(
        Paragraph(
            "Devs engajados respondem a <b>valor + curiosidade</b>, nao a \"venha pro meu projeto\". "
            "O comentario deve: (1) reagir ao post, (2) mostrar que voce constroi, "
            "(3) convite leve (DM / open problems).",
            styles["Body"],
        )
    )
    story.append(Paragraph("Formula de 3 linhas", styles["H2"]))
    story.append(
        Paragraph(
            "[Reacao especifica ao post]<br/>"
            "[O que o ATLAS e, em 1 punch]<br/>"
            "[Pergunta ou convite aberto — sem pressure]",
            styles["Quote"],
        )
    )
    story.append(Paragraph("Ritmo e higiene", styles["H2"]))
    for line in [
        "3–8 comentarios/dia bem feitos (nao 30 copy-paste).",
        "Bio clara + 1 pin do ATLAS.",
        "1 post proprio/semana (arquitetura, demo, open problems).",
        "Preferir threads 10–200 replies engajadas (nao so mega-viral).",
        "DM so se a pessoa engajar de volta.",
        "Evitar: ambassador Web3, giveaway, \"comenta PNG\", pure marketing no-code.",
    ]:
        story.append(Paragraph(f"• {line}", styles["BulletPoint"]))

    story.append(Paragraph("Hooks que batem com o ATLAS", styles["H2"]))
    for line in [
        "Hermes / agent harness",
        "MCP + tools + approvals",
        "Audit / governance / control plane",
        "Coding agents (Claude Code, Codex) + custo de tokens",
        "Cockpit UI / multi-agent supervision",
        "Open source + contributors",
        "BR: bolhadev, harness em Python, gasto com IA",
    ]:
        story.append(Paragraph(f"• {line}", styles["BulletPoint"]))

    story.append(PageBreak())

    # 3 Templates
    story.append(Paragraph("3. Templates de comentario", styles["H1"]))

    story.append(Paragraph("EN — thread Hermes / agents / OSS", styles["H2"]))
    story.append(
        Paragraph(
            "\"Solid take on tool-calling + evals — most stacks still skip auditability.<br/>"
            "We're building ATLAS: an operator cockpit (policy gates, MCP modules, FinOps) "
            "on an evolved Hermes runtime, not just chat.<br/>"
            "If you're into systems/runtime work and want a serious collab surface, happy to swap notes.\"",
            styles["Quote"],
        )
    )

    story.append(Paragraph("EN — governance / audit / control plane", styles["H2"]))
    story.append(
        Paragraph(
            "\"Agree — policy/audit can't live only in the prompt. ATLAS treats every tool action "
            "as an audit event + approval broker before it hits the wire. Happy to compare notes "
            "if you're into control planes for agents.\"",
            styles["Quote"],
        )
    )

    story.append(Paragraph("EN — token cost / routing", styles["H2"]))
    story.append(
        Paragraph(
            "\"Token burn is why we split operator cockpit from model spend tracking. ATLAS treats "
            "FinOps + agent actuation as first-class modules. Curious how others wire usage ledgers "
            "into the agent loop.\"",
            styles["Quote"],
        )
    )

    story.append(Paragraph("PT — bolhadev / harness", styles["H2"]))
    story.append(
        Paragraph(
            "\"Boa — esse tipo de stack (terminal/canvas + agentes) e o caminho.<br/>"
            "Estamos no ATLAS: cockpit de operador com runtime (fundacao Hermes), modulos "
            "(ex. cashflow/FinOps), MCP e audit trail.<br/>"
            "Se alguem curte infra/agents e quer colaborar de verdade, chama.\"",
            styles["Quote"],
        )
    )

    story.append(Paragraph("PT — pergunta \"harness tipo Hermes em Python?\"", styles["H2"]))
    story.append(
        Paragraph(
            "\"Se o gap e 'Hermes-level harness em Python com produto em volta', e exatamente o que "
            "o ATLAS esta empilhando: runtime Python + gateway Rust + cockpit. Se quiser trocar "
            "stack/open problems, DM.\"",
            styles["Quote"],
        )
    )

    story.append(Paragraph("PT — gasto com tokens", styles["H2"]))
    story.append(
        Paragraph(
            "\"Mesma dor — assinatura + overflow de token come margem.<br/>"
            "No ATLAS a gente trata FinOps de IA como modulo (ledger de usage, margem), nao planilha.<br/>"
            "Se rola interesse em colaborar no stack, DM.\"",
            styles["Quote"],
        )
    )

    # 4 Posts
    story.append(Paragraph("4. Posts no X — lista com links", styles["H1"]))
    story.append(
        Paragraph(
            "Snapshot de busca publica recente. Priorize threads Hermes + harness + audit "
            "(maior densidade de dev certo). Personalize a 1a linha antes de colar template.",
            styles["Body"],
        )
    )

    story.append(Paragraph("Tier S — fit alto (comente primeiro)", styles["H2"]))
    tier_s = [
        (1, "Hermes + security/approvals — policy do ATLAS", "https://x.com/tonbistudio/status/2075582060681388087"),
        (2, "Teknium RT masterclass Hermes (comunidade core)", "https://x.com/Teknium/status/2075759029654311304"),
        (3, "Hermes /steer — controle do operador sem matar a run", "https://x.com/tonbistudio/status/2075988494481043472"),
        (4, "Hermes Desktop ↔ Cloud — multi-surface / cockpit", "https://x.com/tonbistudio/status/2075691727571259473"),
        (5, "Hermes no rabbitOS — foundation no ecossistema real", "https://x.com/NousResearch/status/2075698031844818990"),
        (6, "BR: SDK harness tipo Hermes, em Python? — lead quente", "https://x.com/mindofjota/status/2075971470799360168"),
        (7, "Software factory UI — multi-agent + HITL (cockpit)", "https://x.com/lgrammel/status/2075613129308766597"),
        (8, "Production: budget, audit, permissions (control plane)", "https://x.com/MarMarLabs/status/2074170734377660577"),
        (9, "Microsoft agent governance (policy/approval/audit)", "https://x.com/_vmlops/status/2059207888393138556"),
        (10, "Plano proxy — routing, cost, observability", "https://x.com/alex_prompter/status/2076010365268451391"),
    ]
    story.append(post_table(tier_s, styles, BLUE))
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Tier A — bom fit (agent infra / collab)", styles["H2"]))
    tier_a = [
        (11, "Openhuman — memory local markdown (Wiki-like)", "https://x.com/Axel_bitblaze69/status/2076043102792658982"),
        (12, "repowise — token efficiency no coding agent", "https://x.com/srishticodes/status/2075849201523523729"),
        (13, "Self-evolving skills apos tasks", "https://x.com/rvaniaaaa/status/2076027144518398004"),
        (14, "OpenManus — OSS agent + MCP", "https://x.com/RodmanAi/status/2075923279907545413"),
        (15, "iFixAi — diagnosticar falhas de agentes", "https://x.com/im_dimneo/status/2076006839955681526"),
        (16, "TerminalOS Rust AI TUI", "https://x.com/panditdhamdhere/status/2075856141918360021"),
        (17, "MCP + Hermes/Claude (tool surface)", "https://x.com/SamJWasserman/status/2075973393950650499"),
        (18, "Agent Helper CLI (Hermes modules, open PRs)", "https://x.com/bepituLaz/status/2075182755910951049"),
        (19, "Looking for contributors — cultura OSS", "https://x.com/martian588/status/2073635906935017643"),
        (20, "wshobson/agents mega skill pack", "https://x.com/ArchitectHappy_/status/2075939322235146595"),
    ]
    story.append(post_table(tier_a, styles, HexColor("#334155")))
    story.append(Spacer(1, 0.35 * cm))

    story.append(PageBreak())
    story.append(Paragraph("Tier A BR — comunidade brasileira", styles["H2"]))
    tier_br = [
        (21, "Gasto com IA na programacao — FinOps angle", "https://x.com/feliperabeloep/status/2075984848997527571"),
        (22, "AI Engineer World's Fair — harness, evals, tokens", "https://x.com/eusouomatt/status/2075202348083757439"),
        (23, "Claude Code Loops — ciclos de agentes", "https://x.com/adriano_viana/status/2074476921161712074"),
        (24, "NarraTer canvas agentes Linux + #bolhadev", "https://x.com/devcortezia/status/2074598935050473614"),
        (25, "free-claude-code proxy multi-provider", "https://x.com/Nozelcode/status/2076020689669120356"),
        (26, "Claude for Open Source + como faco OSS?", "https://x.com/brunofaggion/status/2074635922683888112"),
        (27, "Rewrit — test engine Rust p/ agentes em legado", "https://x.com/leomarciano/status/2072157290409414672"),
    ]
    story.append(post_table(tier_br, styles, GREEN))
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Tier B — Hermes / operator (engajar com cuidado)", styles["H2"]))
    tier_b = [
        (28, "Hermes Atlas masterclass page — deixe claro L2 ATLAS", "https://x.com/KSimback/status/2076070240622887303"),
        (29, "Cron = Hermes as infrastructure", "https://x.com/tonysimons_/status/2076017835294294234"),
        (30, "Hermes desktop context management", "https://x.com/ericosiu/status/2076018000570785847"),
        (31, "Teknium: Hermes computer use any model", "https://x.com/Teknium/status/2076043327993237563"),
        (32, "Memory fungibility Hermes", "https://x.com/markjeffrey/status/2076014499774218525"),
    ]
    story.append(post_table(tier_b, styles, MUTED))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Evitar (ruido / zero collab dev)", styles["H2"]))
    for line in [
        "Ambassador / Web3 \"comenta PNG\" / farms de points",
        "Jobs YC cold \"founding engineer $140k\" (outro funil)",
        "Hype sem camada de sistema (so marketing no-code)",
    ]:
        story.append(Paragraph(f"• {line}", styles["BulletPoint"]))

    # 5 Order
    story.append(Paragraph("5. Ordem pratica (comecar por aqui)", styles["H1"]))
    order = [
        (1, "https://x.com/mindofjota/status/2075971470799360168", "BR, intent explicito (harness Hermes/Python)"),
        (2, "https://x.com/tonbistudio/status/2075582060681388087", "Hermes security / approvals"),
        (3, "https://x.com/lgrammel/status/2075613129308766597", "Factory UI multi-agent"),
        (4, "https://x.com/alex_prompter/status/2076010365268451391", "Cost / routing proxy"),
        (5, "https://x.com/feliperabeloep/status/2075984848997527571", "BR tokens"),
        (6, "https://x.com/MarMarLabs/status/2074170734377660577", "Production control plane"),
        (7, "https://x.com/srishticodes/status/2075849201523523729", "Coding agent efficiency"),
        (8, "https://x.com/bepituLaz/status/2075182755910951049", "OSS contrib Hermes tools"),
    ]
    for n, url, why in order:
        story.append(Paragraph(f"<b>{n}.</b> {why}<br/>{link(url)}", styles["BulletPoint"]))

    story.append(PageBreak())

    # 6 What to post
    story.append(Paragraph("6. O que postar no SEU perfil (nao so comentar)", styles["H1"]))
    story.append(
        Paragraph(
            "Comentar e inbound. <b>Post proprio</b> e o que converte colaborador serio. "
            "Meta: 1 pin + 1–2 posts/semana tecnicos.",
            styles["Body"],
        )
    )

    story.append(Paragraph("Bio sugerida", styles["H2"]))
    story.append(
        Paragraph(
            "Building ATLAS — AI operator cockpit · Hermes foundation · audit-first agents · open to collab",
            styles["Quote"],
        )
    )
    story.append(
        Paragraph(
            "Variante PT: Construindo ATLAS — cockpit de operador de IA · audit trail · modulos · aberto a collab",
            styles["Quote"],
        )
    )

    story.append(Paragraph("Pin-thread (estrutura EN ou PT)", styles["H2"]))
    for line in [
        "Hook: Most AI agents are chat with tools. Operators need a cockpit.",
        "Problema: sessoes esquecem estado; RAG rediscobre; dashboards nao operam; frameworks sem product surface.",
        "Solucao ATLAS: mission control + runtime + audit ledger + LLM Wiki + multi-surface + modulos.",
        "Stack: Hermes foundation, Python runtime, Rust gateway, React cockpit, SQLite/WAL, MCP/tools.",
        "O que ja roda: missions/runs, Ledger, Wiki, Tool Manifest, golden workflows, Cashflow opcional.",
        "Open problems (convite): permission broker polish, adapters, FinOps modular, surface UAT, docs.",
        "CTA: DM se curte systems/agents — compartilho open problems e arquitetura, nao pitch de hype.",
    ]:
        story.append(Paragraph(f"• {line}", styles["BulletPoint"]))

    story.append(Paragraph("Ideias de posts proprios (series)", styles["H2"]))
    posts_ideas = [
        ("Audit-first", "Por que cada tool call vira audit_event — screenshot do Ledger."),
        ("Multi-surface", "Mesma missao no web cockpit + terminal + Discord approvals."),
        ("Hermes foundation", "O que ATLAS herda vs o que e produto (cockpit, policy, wiki)."),
        ("Token / FinOps", "Cashflow module: usage ledger e margem de IA no operador."),
        ("Open problem sexta", "1 issue dificil da semana + stack exigida (Rust/Python/TS)."),
        ("Golden workflow", "Repo Triage ou Research Brief end-to-end em mock mode."),
        ("Build in public BR", "Thread curta em PT: o que e um cockpit de operador (sem jargao)."),
    ]
    for title, body in posts_ideas:
        story.append(Paragraph(f"• <b>{title}:</b> {body}", styles["BulletPoint"]))

    story.append(Paragraph("Rascunho de post EN (curto)", styles["H2"]))
    story.append(
        Paragraph(
            "\"Building ATLAS: an auditable AI operator cockpit on an evolved Hermes foundation.<br/><br/>"
            "Not another chat wrapper.<br/>"
            "Missions → runtime → tool actions → audit ledger → LLM Wiki → next action.<br/><br/>"
            "Rust gateway · Python harness · multi-surface (web/TUI/Discord) · modular services (e.g. FinOps).<br/><br/>"
            "Open research preview. Looking for collaborators who care about systems, policy, and real operator UX.<br/>"
            "Open problems in DM.\"",
            styles["Quote"],
        )
    )

    story.append(Paragraph("Rascunho de post PT (curto)", styles["H2"]))
    story.append(
        Paragraph(
            "\"Estamos construindo o ATLAS: cockpit de operador de IA com trilha de auditoria, "
            "runtime (fundacao Hermes), multi-surface e modulos (ex. Cashflow/FinOps).<br/><br/>"
            "Nao e so chat com tools — e missao, policy, ledger e conhecimento persistente (LLM Wiki).<br/><br/>"
            "Open research preview. Procurando devs que curtem systems/agents de verdade.<br/>"
            "Se fizer sentido, DM — mando open problems e arquitetura.\"",
            styles["Quote"],
        )
    )

    story.append(Paragraph("Funil simples", styles["H2"]))
    for line in [
        "1) Comentario util no post certo",
        "2) Se engajarem → DM com 1 paragrafo + 3 open problems",
        "3) Link do repo/brief so na DM ou no pin",
        "4) Quem responder com stack = conversa real",
    ]:
        story.append(Paragraph(f"• {line}", styles["BulletPoint"]))

    story.append(Paragraph("Open problems (exemplos para DM)", styles["H2"]))
    for line in [
        "Permission broker multi-surface + UAT real de approve/reject no terminal",
        "Tool Manifest adapters da comunidade (policy chokepoint)",
        "Cashflow modular: unificar dominio operacional vs enterprise + GL",
        "Gateway Rust / surface sessions / conformance cross-surface",
        "Eval harness live-LLM alem de mock mode",
    ]:
        story.append(Paragraph(f"• {line}", styles["BulletPoint"]))

    # 7 Cashflow
    story.append(Paragraph("7. Nota: modulo Cashflow (se vier a tona)", styles["H1"]))
    story.append(
        Paragraph(
            "Cashflow e modulo Next.js vendored em services/cashflow: financeiro L2 + FinOps de IA, "
            "MCP/webhooks, toggle SQLite/Supabase. Roadmap longo = plataforma financeira modular BR. "
            "No outreach, use como <b>exemplo de modulo ativavel</b>, nao como pitch principal do ATLAS.",
            styles["Body"],
        )
    )

    # 8 Limits
    story.append(Paragraph("8. Limites e honestidade", styles["H1"]))
    for line in [
        "Este assistente NAO posta na sua conta X — so leitura publica + rascunhos.",
        "Links sao snapshot; posts esfriam — re-busque Hermes/harness/audit se necessario.",
        "Nao prometa equity logo, proximo ChatGPT ou hiring urgente.",
        "ATLAS e research preview: diga o que falta com clareza (atrai o dev certo).",
    ]:
        story.append(Paragraph(f"• {line}", styles["BulletPoint"]))

    story.append(Spacer(1, 0.5 * cm))
    story.append(
        HRFlowable(width=600, thickness=0.5, color=BORDER, spaceBefore=8, spaceAfter=8)
    )
    story.append(
        Paragraph(
            "L2 ATLAS · Outreach X · Documento interno de recruiting organico · Nao e material de imprensa",
            styles["Footer"],
        )
    )

    def add_page_number(canvas, doc):
        canvas.saveState()
        page = canvas.getPageNumber()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f"L2 ATLAS · X Outreach · p. {page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        OUT_PATH,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
        title="L2 ATLAS — Outreach X Colaboradores",
        author="L2 Systems / ATLAS",
    )
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(OUT_PATH)
    print("bytes", os.path.getsize(OUT_PATH))


if __name__ == "__main__":
    main()
