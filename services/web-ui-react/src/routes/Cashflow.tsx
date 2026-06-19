import { Children, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ExternalLink, Receipt, TrendingDown, TrendingUp, Users, Wallet } from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel, HudLabel } from '../components/hud';
import {
	GATEWAY,
	cashflowSummary,
	type CashflowClient,
	type CashflowExpense,
	type CashflowInvoice,
	type CashflowSummary
} from '../lib/api';

type Load = { s: 'loading' } | { s: 'ready'; data: CashflowSummary } | { s: 'error' };

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const COMPLETE_CASHFLOW_ENDPOINT = `${GATEWAY}/cashflow/full`;

function brl(value: number): string {
	return money.format(Number.isFinite(value) ? value : 0);
}

function dateLabel(value: string | null): string {
	if (!value) return '-';
	const d = new Date(`${value}T00:00:00`);
	return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString('pt-BR');
}

export default function Cashflow() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });

	useEffect(() => {
		let alive = true;
		cashflowSummary()
			.then((data) => alive && setLoad({ s: 'ready', data }))
			.catch(() => alive && setLoad({ s: 'error' }));
		return () => {
			alive = false;
		};
	}, []);

	const data = load.s === 'ready' ? load.data : null;
	const metrics = data?.metrics;
	const margin = useMemo(() => {
		if (!metrics || metrics.monthly_revenue <= 0) return 0;
		return (metrics.profit / metrics.monthly_revenue) * 100;
	}, [metrics]);

	return (
		<Page
			eyebrow="MODULE"
			title="Cashflow"
			max={null}
			actions={
				<div style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
					<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, letterSpacing: '0.14em', color: 'var(--l2-fg-3)' }}>
						{data?.available ? 'ATLAS NATIVE' : load.s === 'loading' ? 'SYNCING' : 'STORE ABSENT'}
					</span>
					<CashflowFullButton />
				</div>
			}
		>
			{load.s === 'loading' && (
				<GlassPanel style={{ padding: 32, display: 'grid', placeItems: 'center' }}>
					<HudLabel>LOADING CASHFLOW…</HudLabel>
				</GlassPanel>
			)}

			{load.s === 'error' && (
				<GlassPanel glow="bad" style={{ padding: 18 }}>
					<HudLabel style={{ color: 'var(--l2-error)' }}>CASHFLOW READMODEL UNAVAILABLE</HudLabel>
				</GlassPanel>
			)}

			{data && (
				<>
					<GlassPanel glow={data.available ? 'good' : 'warn'} style={{ padding: '14px 18px', marginBottom: 16 }}>
						<div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
							<span style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
								<Wallet size={15} strokeWidth={1.6} color={data.available ? 'var(--atlas-cyan)' : 'var(--l2-warn)'} />
								<HudLabel style={{ color: data.available ? 'var(--atlas-cyan)' : 'var(--l2-warn)' }}>
									{data.available ? 'CASHFLOW STORE ONLINE' : 'CASHFLOW STORE ABSENT'}
								</HudLabel>
							</span>
							<span
								title={data.db_path}
								style={{
									fontFamily: 'var(--l2-font-mono)',
									fontSize: 10,
									letterSpacing: '0.08em',
									color: 'var(--l2-fg-3)',
									maxWidth: 640,
									overflow: 'hidden',
									textOverflow: 'ellipsis',
									whiteSpace: 'nowrap'
								}}
							>
								{data.db_path || 'NO LOCAL DB PATH'}
							</span>
						</div>
					</GlassPanel>

					<div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
						<Metric icon={<TrendingUp size={15} />} label="REVENUE" value={brl(metrics?.monthly_revenue ?? 0)} tone="good" />
						<Metric icon={<TrendingDown size={15} />} label="EXPENSES" value={brl(metrics?.monthly_expenses ?? 0)} tone="bad" />
						<Metric icon={<Wallet size={15} />} label="PROFIT" value={brl(metrics?.profit ?? 0)} tone={(metrics?.profit ?? 0) >= 0 ? 'good' : 'bad'} sub={`${margin.toFixed(1)}% MARGIN`} />
						<Metric icon={<Users size={15} />} label="CLIENTS" value={String(metrics?.active_clients ?? 0)} tone="info" />
					</div>

					<div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, alignItems: 'start' }}>
						<div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
							<ClientTable clients={data.clients} />
							<ExpenseTable expenses={data.expenses} />
						</div>
						<div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
							<GlassPanel glow={(metrics?.overdue_invoices ?? 0) > 0 ? 'bad' : 'info'} style={{ padding: 18 }}>
								<div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 12 }}>
									<AlertTriangle size={15} color={(metrics?.overdue_invoices ?? 0) > 0 ? 'var(--l2-error)' : 'var(--atlas-celestial)'} />
									<HudLabel>INVOICE RISK</HudLabel>
								</div>
								<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
									<Mini label="OUTSTANDING" value={brl(metrics?.outstanding ?? 0)} />
									<Mini label="OVERDUE" value={String(metrics?.overdue_invoices ?? 0)} bad={(metrics?.overdue_invoices ?? 0) > 0} />
									<Mini label="DUE 7D" value={String(metrics?.due_soon_invoices ?? 0)} />
									<Mini label="SOURCE" value={data.available ? 'SQLITE' : 'NONE'} />
								</div>
							</GlassPanel>
							<InvoiceTable invoices={data.invoices} />
						</div>
					</div>
				</>
			)}
		</Page>
	);
}

function CashflowFullButton() {
	return (
		<a
			href={COMPLETE_CASHFLOW_ENDPOINT}
			data-topo="good"
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				gap: 8,
				padding: '9px 14px',
				borderRadius: 2,
				border: '1px solid rgba(70,240,224,0.36)',
				background: 'rgba(70,240,224,0.09)',
				color: 'var(--atlas-cyan)',
				fontFamily: 'var(--l2-font-mono)',
				fontSize: 10.5,
				letterSpacing: '0.14em',
				textTransform: 'uppercase',
				textDecoration: 'none',
				boxShadow: '0 0 18px rgba(70,240,224,0.08)'
			}}
		>
			<ExternalLink size={14} strokeWidth={1.6} />
			Complete Cashflow
		</a>
	);
}

function Metric({
	icon,
	label,
	value,
	sub,
	tone
}: {
	icon: React.ReactNode;
	label: string;
	value: string;
	sub?: string;
	tone: 'info' | 'good' | 'bad';
}) {
	const color = tone === 'good' ? 'var(--atlas-cyan)' : tone === 'bad' ? 'var(--l2-error)' : 'var(--atlas-celestial)';
	return (
		<GlassPanel glow={tone} style={{ padding: 16, minHeight: 104 }}>
			<div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--l2-fg-3)', marginBottom: 12 }}>
				<span style={{ color }}>{icon}</span>
				<HudLabel style={{ fontSize: 9.5, color: 'var(--l2-fg-3)' }}>{label}</HudLabel>
			</div>
			<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 20, color, fontVariantNumeric: 'tabular-nums', lineHeight: 1.1 }}>
				{value}
			</div>
			{sub && <div style={{ marginTop: 8, fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.12em', color: 'var(--l2-fg-3)' }}>{sub}</div>}
		</GlassPanel>
	);
}

function Mini({ label, value, bad }: { label: string; value: string; bad?: boolean }) {
	return (
		<div style={{ border: '1px solid var(--l2-hairline)', borderRadius: 2, padding: 12, background: 'rgba(9,11,16,0.34)' }}>
			<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 9, letterSpacing: '0.16em', color: 'var(--l2-fg-3)', marginBottom: 8 }}>{label}</div>
			<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 15, color: bad ? 'var(--l2-error)' : 'var(--l2-fg-1)' }}>{value}</div>
		</div>
	);
}

function ClientTable({ clients }: { clients: CashflowClient[] }) {
	return (
		<Table title="CLIENTS" empty="NO CLIENTS RECORDED" columns="1.2fr 1fr 120px 76px">
			{clients.map((c) => (
				<Row key={c.id} columns="1.2fr 1fr 120px 76px">
					<Cell strong>{c.name}</Cell>
					<Cell>{c.service}</Cell>
					<Cell mono right>{brl(c.monthlyPayment)}</Cell>
					<Cell mono right tone={c.active ? 'good' : 'muted'}>{c.active ? 'ACTIVE' : 'OFF'}</Cell>
				</Row>
			))}
		</Table>
	);
}

function InvoiceTable({ invoices }: { invoices: CashflowInvoice[] }) {
	return (
		<Table title="INVOICES" empty="NO INVOICES RECORDED" columns="1fr 92px 84px">
			{invoices.map((inv) => (
				<Row key={inv.id} columns="1fr 92px 84px">
					<span style={{ minWidth: 0 }}>
						<Cell strong>{inv.clientName}</Cell>
						<div style={{ color: 'var(--l2-fg-3)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
							{inv.description}
						</div>
					</span>
					<Cell mono right>{brl(inv.amount)}</Cell>
					<Cell mono right tone={inv.status === 'atrasado' ? 'bad' : inv.status === 'pago' ? 'good' : 'muted'}>{inv.status}</Cell>
				</Row>
			))}
		</Table>
	);
}

function ExpenseTable({ expenses }: { expenses: CashflowExpense[] }) {
	return (
		<Table title="EXPENSES" empty="NO EXPENSES RECORDED" columns="1fr 118px 96px">
			{expenses.map((e) => (
				<Row key={e.id} columns="1fr 118px 96px">
					<span style={{ minWidth: 0 }}>
						<Cell strong>{e.description}</Cell>
						<div style={{ color: 'var(--l2-fg-3)', fontSize: 11 }}>{e.category}{e.recurring ? ' / RECURRENT' : ''}</div>
					</span>
					<Cell mono right>{brl(e.amount)}</Cell>
					<Cell mono right>{dateLabel(e.date)}</Cell>
				</Row>
			))}
		</Table>
	);
}

function Table({ title, empty, columns, children }: { title: string; empty: string; columns: string; children: React.ReactNode }) {
	const count = Children.count(children);
	return (
		<GlassPanel style={{ overflow: 'hidden' }}>
			<header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '13px 16px', borderBottom: '1px solid var(--l2-hairline)' }}>
				<span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
					<Receipt size={14} strokeWidth={1.5} color="var(--atlas-bronze)" />
					<HudLabel style={{ color: 'var(--atlas-bronze)' }}>{title}</HudLabel>
				</span>
				<span style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10, letterSpacing: '0.12em', color: 'var(--l2-fg-3)' }}>{count} ROWS</span>
			</header>
			<div style={{ display: 'grid', gridTemplateColumns: columns, gap: 12, padding: '9px 16px', borderBottom: '1px solid var(--l2-hairline)', fontFamily: 'var(--l2-font-mono)', fontSize: 9, letterSpacing: '0.16em', color: 'var(--l2-fg-3)' }}>
				<span>NAME</span>
				<span style={{ textAlign: 'right' }}>VALUE</span>
				<span style={{ textAlign: 'right' }}>STATUS</span>
			</div>
			{count === 0 ? (
				<div style={{ padding: 24, color: 'var(--l2-fg-3)', fontFamily: 'var(--l2-font-mono)', fontSize: 11, letterSpacing: '0.12em' }}>{empty}</div>
			) : (
				children
			)}
		</GlassPanel>
	);
}

function Row({ columns, children }: { columns: string; children: React.ReactNode }) {
	return (
		<div
			data-topo="good"
			style={{
				display: 'grid',
				gridTemplateColumns: columns,
				gap: 12,
				alignItems: 'center',
				padding: '12px 16px',
				borderBottom: '1px solid rgba(237,234,224,0.04)'
			}}
		>
			{children}
		</div>
	);
}

function Cell({
	children,
	strong,
	mono,
	right,
	tone
}: {
	children: React.ReactNode;
	strong?: boolean;
	mono?: boolean;
	right?: boolean;
	tone?: 'good' | 'bad' | 'muted';
}) {
	const color = tone === 'good' ? 'var(--atlas-cyan)' : tone === 'bad' ? 'var(--l2-error)' : tone === 'muted' ? 'var(--l2-fg-3)' : strong ? 'var(--l2-fg-1)' : 'var(--l2-fg-2)';
	return (
		<span
			style={{
				display: 'block',
				minWidth: 0,
				color,
				fontFamily: mono ? 'var(--l2-font-mono)' : 'var(--l2-font-sans)',
				fontSize: strong ? 13.5 : 12,
				fontWeight: strong ? 600 : 400,
				textAlign: right ? 'right' : 'left',
				overflow: 'hidden',
				textOverflow: 'ellipsis',
				whiteSpace: 'nowrap',
				fontVariantNumeric: 'tabular-nums'
			}}
		>
			{children}
		</span>
	);
}
