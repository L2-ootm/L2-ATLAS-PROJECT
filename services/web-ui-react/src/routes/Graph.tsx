import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph3D from '3d-force-graph';
import { Boxes, RefreshCw } from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel } from '../components/GlassFx';
import { getGraph, type GraphData, type GraphNode } from '../lib/api';

type Load = { s: 'loading' } | { s: 'ready'; data: GraphData } | { s: 'error'; message: string };

// Node color by kind — bronze for structural hubs, celestial/cyan/violet for content.
const NODE_COLOR: Record<string, string> = {
	root: '#E0A94E',
	group: '#9C6B2E',
	phase: '#4A5DBF',
	milestone: '#7F00FF',
	roadmap: '#00F0FF',
	state: '#00E5C8',
	project: '#E0A94E',
	requirements: '#4A5DBF',
	risks: '#FF4D7D',
	retro: '#46F0A0',
	prep: '#7F00FF',
	research: '#00E5C8',
	report: '#FFD600',
	intel: '#46F0E0',
	doc: '#8A93A6'
};
const colorFor = (kind: string): string => NODE_COLOR[kind] ?? '#8A93A6';

const LINK_COLOR: Record<string, string> = {
	contains: 'rgba(224,169,78,0.28)',
	link: 'rgba(0,240,255,0.55)',
	wikilink: 'rgba(0,229,200,0.55)',
	decision: 'rgba(127,0,255,0.45)',
	phase: 'rgba(74,93,191,0.5)'
};

type GraphHandle = {
	graphData: (d: { nodes: unknown[]; links: unknown[] }) => GraphHandle;
	nodeLabel: (fn: (n: unknown) => string) => GraphHandle;
	nodeColor: (fn: (n: unknown) => string) => GraphHandle;
	nodeVal: (fn: (n: unknown) => number) => GraphHandle;
	nodeOpacity: (v: number) => GraphHandle;
	nodeResolution: (v: number) => GraphHandle;
	linkColor: (fn: (l: unknown) => string) => GraphHandle;
	linkWidth: (v: number) => GraphHandle;
	linkOpacity: (v: number) => GraphHandle;
	backgroundColor: (c: string) => GraphHandle;
	showNavInfo: (v: boolean) => GraphHandle;
	width: (v: number) => GraphHandle;
	height: (v: number) => GraphHandle;
	onNodeClick: (fn: (n: unknown) => void) => GraphHandle;
	cameraPosition: (pos: { x: number; y: number; z: number }, lookAt?: unknown, ms?: number) => GraphHandle;
	_destructor?: () => void;
};

export default function Graph() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [nonce, setNonce] = useState(0);
	const containerRef = useRef<HTMLDivElement>(null);
	const graphRef = useRef<GraphHandle | null>(null);

	useEffect(() => {
		let alive = true;
		setLoad({ s: 'loading' });
		getGraph()
			.then((data) => alive && setLoad({ s: 'ready', data }))
			.catch((err) => alive && setLoad({ s: 'error', message: err instanceof Error ? err.message : String(err) }));
		return () => {
			alive = false;
		};
	}, [nonce]);

	const data = load.s === 'ready' ? load.data : null;

	useEffect(() => {
		const el = containerRef.current;
		if (!el || !data) return;

		const GraphCtor = ForceGraph3D as unknown as new (e: HTMLElement) => GraphHandle;
		const graph = new GraphCtor(el)
			.backgroundColor('rgba(7,8,12,0)')
			.showNavInfo(false)
			.nodeLabel((n) => {
				const node = n as GraphNode;
				return `<div style="font-family:var(--l2-font-mono);font-size:11px;letter-spacing:0.04em;color:#EDEAE0;background:rgba(7,8,12,0.92);border:1px solid rgba(74,93,191,0.4);padding:4px 8px;border-radius:2px"><b>${node.label}</b><br/><span style="opacity:0.6">${node.kind} · ${node.id}</span></div>`;
			})
			.nodeColor((n) => colorFor((n as GraphNode).kind))
			.nodeVal((n) => {
				const node = n as GraphNode;
				if (node.kind === 'group') return 6;
				return Math.max(1.2, Math.min(8, node.size / 2200));
			})
			.nodeOpacity(0.92)
			.nodeResolution(12)
			.linkColor((l) => LINK_COLOR[(l as { kind: string }).kind] ?? 'rgba(237,234,224,0.2)')
			.linkWidth(0.7)
			.linkOpacity(0.8)
			.width(el.clientWidth)
			.height(el.clientHeight)
			.onNodeClick((n) => {
				const node = n as unknown as { x: number; y: number; z: number };
				const distance = 90;
				const ratio = 1 + distance / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
				graph.cameraPosition(
					{ x: (node.x || 0) * ratio, y: (node.y || 0) * ratio, z: (node.z || 0) * ratio },
					node,
					900
				);
			})
			.graphData({ nodes: data.nodes as unknown[], links: data.links as unknown[] });

		graphRef.current = graph;

		const onResize = () => {
			graph.width(el.clientWidth).height(el.clientHeight);
		};
		const ro = new ResizeObserver(onResize);
		ro.observe(el);

		return () => {
			ro.disconnect();
			graph._destructor?.();
			graphRef.current = null;
			el.replaceChildren();
		};
	}, [data]);

	const counts = data?.counts;
	const legend = useMemo(
		() => [
			{ kind: 'phase', label: 'Phase' },
			{ kind: 'roadmap', label: 'Roadmap/State' },
			{ kind: 'research', label: 'Research' },
			{ kind: 'prep', label: 'Prep' },
			{ kind: 'report', label: 'Report' },
			{ kind: 'group', label: 'Folder' }
		],
		[]
	);

	return (
		<Page
			eyebrow="STRUCTURE · GRAPHIFY"
			title="Knowledge Graph"
			max={null}
			actions={
				<button
					type="button"
					onClick={() => setNonce((n) => n + 1)}
					title="Rebuild graph"
					style={rebuildButtonStyle}
				>
					<RefreshCw size={14} strokeWidth={1.8} />
					<span>REBUILD</span>
				</button>
			}
		>
			<GlassPanel
				data-topo="atlas"
				style={{ position: 'relative', height: 'calc(100vh - 142px)', minHeight: 560, overflow: 'hidden' }}
			>
				<div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />

				{load.s === 'loading' && <div style={overlayStyle}>Building knowledge graph…</div>}
				{load.s === 'error' && (
					<div style={overlayStyle}>
						<Boxes size={18} strokeWidth={1.6} style={{ color: 'var(--atlas-bronze)' }} />
						<div>Graph unavailable — {load.message}</div>
						<div style={{ fontSize: 11, opacity: 0.6 }}>Confirm the gateway is running.</div>
					</div>
				)}

				{counts && (
					<div style={hudStyle}>
						<span>{counts.nodes} NODES</span>
						<span>{counts.links} EDGES</span>
					</div>
				)}

				<div style={legendStyle}>
					{legend.map((item) => (
						<span key={item.kind} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
							<span style={{ width: 8, height: 8, borderRadius: 8, background: colorFor(item.kind) }} />
							{item.label}
						</span>
					))}
				</div>
			</GlassPanel>
		</Page>
	);
}

const overlayStyle: React.CSSProperties = {
	position: 'absolute',
	inset: 0,
	display: 'flex',
	flexDirection: 'column',
	alignItems: 'center',
	justifyContent: 'center',
	gap: 8,
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 12.5,
	letterSpacing: '0.05em',
	color: 'var(--l2-fg-2)',
	pointerEvents: 'none',
	textAlign: 'center',
	padding: 24
};

const hudStyle: React.CSSProperties = {
	position: 'absolute',
	top: 12,
	right: 14,
	display: 'flex',
	gap: 14,
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.16em',
	color: 'var(--l2-fg-3)',
	pointerEvents: 'none'
};

const legendStyle: React.CSSProperties = {
	position: 'absolute',
	bottom: 12,
	left: 14,
	display: 'flex',
	flexWrap: 'wrap',
	gap: 14,
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.1em',
	textTransform: 'uppercase',
	color: 'var(--l2-fg-3)',
	pointerEvents: 'none'
};

const rebuildButtonStyle: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	gap: 7,
	padding: '7px 11px',
	borderRadius: 2,
	border: '1px solid rgba(74,93,191,0.4)',
	background: 'rgba(74,93,191,0.12)',
	color: 'var(--atlas-celestial)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.14em',
	cursor: 'pointer'
};
