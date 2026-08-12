import { useCallback, useEffect, useMemo, useState } from 'react';
import type * as React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Puzzle, Play } from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel } from '../components/GlassFx';
import { ChatMarkdown } from '../components/ChatMarkdown';
import {
	listModuleRecords,
	listModules,
	type Module,
	type ModulePage,
	type ModulePageBlock,
	type ModuleRecord
} from '../lib/api';

/**
 * ModuleHost — renders a manifest module's schema-driven pages.
 *
 * The visual constraint of the module framework: pages are declared as block
 * schemas in module.yaml and rendered exclusively by ATLAS-owned components.
 * No module code executes. Unknown block kinds render as labeled placeholders
 * so newer manifests degrade gracefully on older builds.
 *
 * Capability v2 adds three data-bound kinds — `tabs`, `records` and `stat_row`
 * — which read module_records through the gateway. They stay read-only here on
 * purpose: schema validation lives in module_data_service, so the write paths
 * are the agent's `atlas_module` tool and the CLI, never a second validator in
 * the browser.
 */
export default function ModuleHost() {
	const { moduleId } = useParams<{ moduleId: string }>();
	const [module, setModule] = useState<Module | null | undefined>(undefined);

	useEffect(() => {
		let alive = true;
		void (async () => {
			try {
				const { modules } = await listModules();
				if (!alive) return;
				setModule(modules.find((m) => m.id === moduleId) ?? null);
			} catch {
				if (alive) setModule(null);
			}
		})();
		return () => {
			alive = false;
		};
	}, [moduleId]);

	const pages: ModulePage[] = useMemo(
		() => module?.manifest?.capabilities?.pages ?? [],
		[module]
	);

	if (module === undefined) {
		return (
			<Page eyebrow="MODULE" title={moduleId ?? 'Module'}>
				<div style={mutedStyle}>Loading module…</div>
			</Page>
		);
	}
	if (module === null || module.status !== 'active' || module.missing) {
		return (
			<Page eyebrow="MODULE" title={moduleId ?? 'Module'}>
				<GlassPanel data-topo="atlas" style={{ padding: 28 }}>
					<div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
						<Puzzle size={16} strokeWidth={1.6} style={{ color: 'var(--atlas-bronze)' }} />
						<span style={labelStyle}>MODULE UNAVAILABLE</span>
					</div>
					<div style={mutedStyle}>
						{module === null
							? `No module registered under “${moduleId}”. Run atlas module sync after installing it.`
							: module.missing
								? 'The module source directory is missing on disk. Its state is preserved; restore the directory and re-sync.'
								: 'This module is deactivated. Activate it under Control → System, or run atlas module activate.'}
					</div>
				</GlassPanel>
			</Page>
		);
	}

	return (
		<Page eyebrow={`MODULE · v${module.version || '0'}`} title={module.name}>
			<div style={{ display: 'grid', gap: 18 }}>
				{pages.length === 0 && (
					<GlassPanel data-topo="atlas" style={{ padding: 28 }}>
						<div style={mutedStyle}>
							This module declares no pages. Its commands remain available in the palette and slash surfaces.
						</div>
					</GlassPanel>
				)}
				{pages.map((page) => (
					<GlassPanel key={page.id} data-topo="atlas" style={{ padding: 28, display: 'grid', gap: 16 }}>
						{page.blocks.map((block, i) => (
							<ModuleBlock key={i} block={block} moduleId={module.id} />
						))}
					</GlassPanel>
				))}
			</div>
		</Page>
	);
}

function ModuleBlock({ block, moduleId }: { block: ModulePageBlock; moduleId: string }) {
	const navigate = useNavigate();
	switch (block.kind) {
		case 'heading':
			return <h2 style={headingStyle}>{block.text ?? ''}</h2>;
		case 'markdown':
			return <ChatMarkdown text={block.text ?? ''} />;
		case 'divider':
			return <hr style={dividerStyle} />;
		case 'metrics':
			return (
				<div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
					{(block.items ?? []).map((item, i) => (
						<div key={i} style={metricStyle}>
							<div style={metricLabelStyle}>{item.label}</div>
							<div style={metricValueStyle}>{item.value ?? '—'}</div>
						</div>
					))}
				</div>
			);
		case 'stat_row':
			return <StatRow block={block} moduleId={moduleId} />;
		case 'records':
			return <RecordsTable block={block} moduleId={moduleId} />;
		case 'tabs':
			return <TabsBlock block={block} moduleId={moduleId} />;
		case 'actions':
			return (
				<div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
					{(block.items ?? []).map((item, i) => (
						<button
							key={i}
							type="button"
							style={actionStyle}
							onClick={() => {
								if (item.command) {
									navigate(`/chat?draft=${encodeURIComponent(item.command)}`);
								}
							}}
						>
							<Play size={12} strokeWidth={2} />
							{item.label}
						</button>
					))}
				</div>
			);
		default:
			return (
				<div style={{ ...mutedStyle, fontStyle: 'italic' }}>
					[unsupported block kind: {block.kind}]
				</div>
			);
	}
}

function TabsBlock({ block, moduleId }: { block: ModulePageBlock; moduleId: string }) {
	const tabs = block.tabs ?? [];
	const [active, setActive] = useState(tabs[0]?.id ?? '');
	const current = tabs.find((t) => t.id === active) ?? tabs[0];
	if (tabs.length === 0) return null;
	return (
		<div style={{ display: 'grid', gap: 14 }}>
			<div role="tablist" style={tabBarStyle}>
				{tabs.map((tab) => (
					<button
						key={tab.id}
						type="button"
						role="tab"
						aria-selected={tab.id === current?.id}
						onClick={() => setActive(tab.id)}
						style={tab.id === current?.id ? tabActiveStyle : tabStyle}
					>
						{tab.label}
					</button>
				))}
			</div>
			<div style={{ display: 'grid', gap: 16 }}>
				{(current?.blocks ?? []).map((child, i) => (
					<ModuleBlock key={i} block={child} moduleId={moduleId} />
				))}
			</div>
		</div>
	);
}

/** Live counts per collection, optionally filtered by exact field match. */
function StatRow({ block, moduleId }: { block: ModulePageBlock; moduleId: string }) {
	const items = useMemo(() => block.items ?? [], [block.items]);
	const [counts, setCounts] = useState<number[] | null>(null);

	useEffect(() => {
		let alive = true;
		void (async () => {
			const resolved = await Promise.all(
				items.map(async (item) => {
					if (!item.collection) return 0;
					const records = await listModuleRecords(moduleId, item.collection, 500);
					if (!item.where) return records.length;
					return records.filter((record) =>
						Object.entries(item.where ?? {}).every(
							([key, value]) => String(record.data[key] ?? '') === String(value)
						)
					).length;
				})
			);
			if (alive) setCounts(resolved);
		})();
		return () => {
			alive = false;
		};
	}, [items, moduleId]);

	return (
		<div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
			{items.map((item, i) => (
				<div key={i} style={metricStyle}>
					<div style={metricLabelStyle}>{item.label}</div>
					<div style={metricValueStyle}>{counts ? counts[i] : '—'}</div>
				</div>
			))}
		</div>
	);
}

/** A module collection rendered as a table. Read-only by contract. */
function RecordsTable({ block, moduleId }: { block: ModulePageBlock; moduleId: string }) {
	const collection = block.collection ?? '';
	const [records, setRecords] = useState<ModuleRecord[] | null>(null);
	const [query, setQuery] = useState('');

	const load = useCallback(async () => {
		if (!collection) return;
		setRecords(await listModuleRecords(moduleId, collection));
	}, [collection, moduleId]);

	useEffect(() => {
		let alive = true;
		void (async () => {
			if (!collection) return;
			const rows = await listModuleRecords(moduleId, collection);
			if (alive) setRecords(rows);
		})();
		return () => {
			alive = false;
		};
	}, [collection, moduleId]);

	if (!collection) {
		return <div style={{ ...mutedStyle, fontStyle: 'italic' }}>[records block without a collection]</div>;
	}

	const columns = block.columns?.length ? block.columns : ['id'];
	const filtered = (records ?? []).filter((record) => {
		if (!query.trim()) return true;
		const haystack = [record.id, ...Object.values(record.data).map((v) => String(v ?? ''))]
			.join(' ')
			.toLowerCase();
		return haystack.includes(query.trim().toLowerCase());
	});

	return (
		<div style={{ display: 'grid', gap: 10 }}>
			<div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
				<input
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					placeholder={`Filter ${collection}…`}
					aria-label={`Filter ${collection}`}
					style={inputStyle}
				/>
				<button type="button" style={subtleButtonStyle} onClick={() => void load()}>
					Refresh
				</button>
				<span style={{ ...metricLabelStyle, marginBottom: 0 }}>
					{records === null ? 'LOADING' : `${filtered.length} / ${records.length}`}
				</span>
			</div>
			<div style={{ overflowX: 'auto' }}>
				<table style={tableStyle}>
					<thead>
						<tr>
							{columns.map((column) => (
								<th key={column} style={thStyle}>
									{column.replace(/_/g, ' ')}
								</th>
							))}
						</tr>
					</thead>
					<tbody>
						{filtered.map((record) => (
							<tr key={record.id}>
								{columns.map((column) => (
									<td key={column} style={tdStyle}>
										{renderCell(record, column)}
									</td>
								))}
							</tr>
						))}
						{records !== null && filtered.length === 0 && (
							<tr>
								<td colSpan={columns.length} style={{ ...tdStyle, ...mutedStyle }}>
									{records.length === 0
										? 'No records yet. The agent writes them as the work happens.'
										: 'No records match this filter.'}
								</td>
							</tr>
						)}
					</tbody>
				</table>
			</div>
		</div>
	);
}

function renderCell(record: ModuleRecord, column: string): string {
	if (column === 'id') return record.id;
	const value = record.data[column];
	if (value === undefined || value === null || value === '') return '—';
	if (Array.isArray(value)) return value.join(', ');
	if (typeof value === 'boolean') return value ? 'yes' : 'no';
	const text = String(value);
	return text.length > 120 ? `${text.slice(0, 117)}…` : text;
}

const labelStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.16em',
	color: 'var(--l2-fg-3)'
};

const mutedStyle: React.CSSProperties = {
	color: 'var(--l2-fg-3)',
	fontSize: 13,
	lineHeight: 1.6
};

const headingStyle: React.CSSProperties = {
	margin: 0,
	fontSize: 18,
	fontWeight: 600,
	letterSpacing: '0.04em',
	color: 'var(--l2-fg-1)'
};

const dividerStyle: React.CSSProperties = {
	border: 0,
	borderTop: '1px solid rgba(237,234,224,0.10)',
	margin: '2px 0',
	width: '100%'
};

const metricStyle: React.CSSProperties = {
	border: '1px solid rgba(237,234,224,0.10)',
	background: 'rgba(237,234,224,0.03)',
	borderRadius: 2,
	padding: '10px 14px',
	minWidth: 140
};

const metricLabelStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9,
	letterSpacing: '0.14em',
	textTransform: 'uppercase',
	color: 'var(--l2-fg-3)',
	marginBottom: 4
};

const metricValueStyle: React.CSSProperties = {
	fontSize: 14,
	color: 'var(--l2-fg-1)'
};

const actionStyle: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	gap: 7,
	border: '1px solid rgba(79,139,255,0.35)',
	background: 'rgba(79,139,255,0.10)',
	color: 'var(--atlas-celestial)',
	borderRadius: 2,
	padding: '8px 14px',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	letterSpacing: '0.10em',
	textTransform: 'uppercase',
	cursor: 'pointer'
};

const tabBarStyle: React.CSSProperties = {
	display: 'flex',
	flexWrap: 'wrap',
	gap: 2,
	borderBottom: '1px solid rgba(237,234,224,0.10)'
};

const tabStyle: React.CSSProperties = {
	border: 'none',
	borderBottom: '2px solid transparent',
	background: 'transparent',
	color: 'var(--l2-fg-3)',
	padding: '8px 14px',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	letterSpacing: '0.12em',
	textTransform: 'uppercase',
	cursor: 'pointer'
};

const tabActiveStyle: React.CSSProperties = {
	...tabStyle,
	color: 'var(--l2-fg-1)',
	borderBottom: '2px solid var(--atlas-celestial)'
};

const tableStyle: React.CSSProperties = {
	width: '100%',
	borderCollapse: 'collapse',
	fontSize: 12.5
};

const thStyle: React.CSSProperties = {
	textAlign: 'left',
	padding: '8px 10px',
	borderBottom: '1px solid rgba(237,234,224,0.14)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.14em',
	textTransform: 'uppercase',
	color: 'var(--l2-fg-3)',
	whiteSpace: 'nowrap'
};

const tdStyle: React.CSSProperties = {
	padding: '8px 10px',
	borderBottom: '1px solid rgba(237,234,224,0.06)',
	color: 'var(--l2-fg-2)',
	verticalAlign: 'top'
};

const inputStyle: React.CSSProperties = {
	flex: '1 1 220px',
	border: '1px solid rgba(237,234,224,0.14)',
	background: 'rgba(237,234,224,0.03)',
	color: 'var(--l2-fg-1)',
	borderRadius: 2,
	padding: '7px 10px',
	fontSize: 12.5
};

const subtleButtonStyle: React.CSSProperties = {
	border: '1px solid rgba(237,234,224,0.14)',
	background: 'transparent',
	color: 'var(--l2-fg-2)',
	borderRadius: 2,
	padding: '7px 12px',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10.5,
	letterSpacing: '0.10em',
	textTransform: 'uppercase',
	cursor: 'pointer'
};
