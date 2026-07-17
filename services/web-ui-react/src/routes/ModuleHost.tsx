import { useEffect, useMemo, useState } from 'react';
import type * as React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Puzzle, Play } from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel } from '../components/GlassFx';
import { ChatMarkdown } from '../components/ChatMarkdown';
import { listModules, type Module, type ModulePage, type ModulePageBlock } from '../lib/api';

/**
 * ModuleHost — renders a manifest module's schema-driven pages.
 *
 * The visual constraint of the module framework: pages are declared as block
 * schemas in module.yaml and rendered exclusively by ATLAS-owned components.
 * No module code executes. Unknown block kinds render as labeled placeholders
 * so newer manifests degrade gracefully on older builds.
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
							<ModuleBlock key={i} block={block} />
						))}
					</GlassPanel>
				))}
			</div>
		</Page>
	);
}

function ModuleBlock({ block }: { block: ModulePageBlock }) {
	const navigate = useNavigate();
	switch (block.kind) {
		case 'heading':
			return <h2 style={headingStyle}>{block.text ?? ''}</h2>;
		case 'markdown':
			return <ChatMarkdown text={block.text ?? ''} />;
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
