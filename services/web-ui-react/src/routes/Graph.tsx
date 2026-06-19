import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type * as React from 'react';
import ForceGraph3D from '3d-force-graph';
import * as THREE from 'three';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import SpriteText from 'three-spritetext';
import { Boxes, Crosshair, Lock, Maximize2, Minus, Plus, RefreshCw, Search, X } from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel } from '../components/GlassFx';
import Lightning from '../components/Lightning';
import { getGraph, getGraphFetchedAt, type GraphData, type GraphNode } from '../lib/api';

type Load = { s: 'loading' } | { s: 'ready'; data: GraphData } | { s: 'error'; message: string };
type SimNode = GraphNode & { x?: number; y?: number; z?: number };

// Node color by kind — bronze for structural hubs, celestial/cyan/violet/etc for
// content. Per-category (NOT heat) — clusters read as distinct communities.
const NODE_COLOR: Record<string, string> = {
	root: '#E0A94E',
	group: '#C98A3E',
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
	contains: 'rgba(224,169,78,0.18)',
	link: 'rgba(0,240,255,0.55)',
	wikilink: 'rgba(0,229,200,0.55)',
	decision: 'rgba(127,0,255,0.5)',
	phase: 'rgba(74,93,191,0.5)'
};
const linkColorFor = (kind: string): string => LINK_COLOR[kind] ?? 'rgba(237,234,224,0.18)';

// Minimal builder surface we use from 3d-force-graph (typed loosely on purpose).
type GraphHandle = {
	graphData: (d: { nodes: unknown[]; links: unknown[] }) => GraphHandle;
	nodeLabel: (fn: (n: unknown) => string) => GraphHandle;
	nodeColor: (fn: (n: unknown) => string) => GraphHandle;
	nodeVal: (fn: (n: unknown) => number) => GraphHandle;
	nodeOpacity: (v: number) => GraphHandle;
	nodeResolution: (v: number) => GraphHandle;
	nodeThreeObjectExtend: (v: boolean) => GraphHandle;
	nodeThreeObject: (fn: (n: unknown) => unknown) => GraphHandle;
	linkColor: (fn: (l: unknown) => string) => GraphHandle;
	linkWidth: (v: number) => GraphHandle;
	linkOpacity: (v: number) => GraphHandle;
	linkDirectionalParticles: (fn: (l: unknown) => number) => GraphHandle;
	linkDirectionalParticleWidth: (v: number) => GraphHandle;
	linkDirectionalParticleSpeed: (v: number) => GraphHandle;
	linkDirectionalParticleColor: (fn: (l: unknown) => string) => GraphHandle;
	backgroundColor: (c: string) => GraphHandle;
	showNavInfo: (v: boolean) => GraphHandle;
	width: (v: number) => GraphHandle;
	height: (v: number) => GraphHandle;
	onNodeClick: (fn: (n: unknown) => void) => GraphHandle;
	onEngineStop: (fn: () => void) => GraphHandle;
	cameraPosition: (pos?: Vec3, lookAt?: unknown, ms?: number) => Vec3;
	zoomToFit: (ms?: number, px?: number) => GraphHandle;
	postProcessingComposer: () => { addPass: (p: unknown) => void };
	scene: () => THREE.Scene;
	_destructor?: () => void;
};

type Vec3 = { x: number; y: number; z: number };

const TABS = [
	{ id: 'global', label: 'Global', live: true },
	{ id: 'projects', label: 'Projects', live: false },
	{ id: 'vault', label: 'Obsidian Vault', live: false },
	{ id: 'agent', label: 'Agent Context', live: false }
] as const;

export default function Graph() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [nonce, setNonce] = useState(0);
	const [selected, setSelected] = useState<GraphNode | null>(null);
	const [query, setQuery] = useState('');
	const [tab, setTab] = useState<(typeof TABS)[number]['id']>('global');
	const [electricity, setElectricity] = useState(true);
	const [storm, setStorm] = useState(true);
	const [, setClock] = useState(0); // ticks "Updated Xm ago"
	const containerRef = useRef<HTMLDivElement>(null);
	const minimapRef = useRef<HTMLCanvasElement>(null);
	const graphRef = useRef<GraphHandle | null>(null);
	const simNodesRef = useRef<SimNode[]>([]);
	const electricityRef = useRef(electricity);
	electricityRef.current = electricity;

	useEffect(() => {
		let alive = true;
		setLoad({ s: 'loading' });
		setSelected(null);
		getGraph(nonce > 0)
			.then((data) => alive && setLoad({ s: 'ready', data }))
			.catch((err) => alive && setLoad({ s: 'error', message: err instanceof Error ? err.message : String(err) }));
		return () => {
			alive = false;
		};
	}, [nonce]);

	// Re-render the "Updated Xm ago" label periodically.
	useEffect(() => {
		const t = setInterval(() => setClock((c) => c + 1), 30000);
		return () => clearInterval(t);
	}, []);

	const data = load.s === 'ready' ? load.data : null;

	// Adjacency + node index, captured from the raw (string-id) links.
	const { nodeById, neighbors } = useMemo(() => {
		const byId = new Map<string, GraphNode>();
		const adj = new Map<string, Set<string>>();
		if (data) {
			for (const node of data.nodes) {
				byId.set(node.id, node);
				adj.set(node.id, new Set());
			}
			for (const link of data.links) {
				adj.get(link.source)?.add(link.target);
				adj.get(link.target)?.add(link.source);
			}
		}
		return { nodeById: byId, neighbors: adj };
	}, [data]);

	const stats = useMemo(() => {
		if (!data) return null;
		const n = data.nodes.length;
		const e = data.links.length;
		const communities = new Set(data.nodes.map((node) => node.group)).size;
		const density = n > 1 ? (2 * e) / (n * (n - 1)) : 0;
		const avgDegree = n > 0 ? (2 * e) / n : 0;
		return { n, e, communities, density, avgDegree };
	}, [data]);

	const focusNode = useCallback((node: GraphNode) => {
		const graph = graphRef.current;
		const pos = node as unknown as Vec3;
		if (!graph || pos.x === undefined) return;
		const dist = 80;
		const hyp = Math.hypot(pos.x, pos.y, pos.z) || 1;
		const ratio = 1 + dist / hyp;
		graph.cameraPosition({ x: pos.x * ratio, y: pos.y * ratio, z: pos.z * ratio }, pos, 900);
	}, []);

	const selectAndFocus = useCallback(
		(node: GraphNode) => {
			setSelected(node);
			focusNode(node);
		},
		[focusNode]
	);

	useEffect(() => {
		const el = containerRef.current;
		if (!el || !data) return;

		const simNodes: SimNode[] = data.nodes.map((node) => ({ ...node }));
		simNodesRef.current = simNodes;

		const graph = new (ForceGraph3D as unknown as new (e: HTMLElement) => GraphHandle)(el)
			.backgroundColor('rgba(7,8,12,0)')
			.showNavInfo(false)
			.nodeLabel((n) => {
				const node = n as GraphNode;
				return `<div style="font-family:var(--l2-font-mono);font-size:11px;letter-spacing:0.04em;color:#EDEAE0;background:rgba(7,8,12,0.92);border:1px solid rgba(74,93,191,0.4);padding:4px 8px;border-radius:2px"><b>${node.label}</b><br/><span style="opacity:0.6">${node.kind} · ${node.id}</span></div>`;
			})
			.nodeColor((n) => colorFor((n as GraphNode).kind))
			.nodeVal((n) => {
				const node = n as GraphNode;
				if (node.id === 'root') return 11;
				if (node.kind === 'group') return 6;
				return Math.max(1.2, Math.min(6.5, node.size / 2600));
			})
			.nodeOpacity(0.92)
			.nodeResolution(16)
			.nodeThreeObjectExtend(true)
			.nodeThreeObject((n) => {
				const node = n as GraphNode;
				if (node.kind !== 'group') return undefined as unknown as THREE.Object3D;
				const sprite = new SpriteText(node.label);
				sprite.color = '#EDEAE0';
				sprite.textHeight = node.id === 'root' ? 7 : 4.5;
				sprite.fontFace = 'JetBrains Mono, ui-monospace, monospace';
				sprite.fontWeight = '600';
				sprite.backgroundColor = 'rgba(7,8,12,0.5)';
				sprite.padding = 2;
				sprite.borderRadius = 2;
				const mat = (sprite as unknown as { material: THREE.Material }).material;
				mat.depthWrite = false;
				sprite.position.set(0, node.id === 'root' ? 12 : 8, 0);
				return sprite;
			})
			.linkColor((l) => linkColorFor((l as { kind: string }).kind))
			.linkWidth(0.55)
			.linkOpacity(0.65)
			.linkDirectionalParticles((l) =>
				electricityRef.current && (l as { kind: string }).kind !== 'contains' ? 2 : 0
			)
			.linkDirectionalParticleWidth(1.4)
			.linkDirectionalParticleSpeed(0.01)
			.linkDirectionalParticleColor((l) => linkColorFor((l as { kind: string }).kind))
			.width(el.clientWidth)
			.height(el.clientHeight)
			.onNodeClick((n) => selectAndFocus(n as GraphNode))
			.graphData({ nodes: simNodes, links: data.links.map((link) => ({ ...link })) });

		// Center the layout once it settles.
		let fitted = false;
		graph.onEngineStop(() => {
			if (fitted) return;
			fitted = true;
			graph.zoomToFit(700, 80);
		});

		// Unreal bloom — tuned down from the earlier "melted glow": lower strength,
		// tighter radius, higher threshold so only bright cores bloom.
		try {
			const bloom = new UnrealBloomPass(new THREE.Vector2(el.clientWidth, el.clientHeight), 0.95, 0.55, 0.22);
			graph.postProcessingComposer().addPass(bloom);
		} catch {
			// postprocessing unavailable — fall back to flat nodes
		}

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
			simNodesRef.current = [];
			el.replaceChildren();
		};
	}, [data, selectAndFocus]);

	// Toggle link particles without rebuilding the layout.
	useEffect(() => {
		graphRef.current?.linkDirectionalParticles((l) =>
			electricity && (l as { kind: string }).kind !== 'contains' ? 2 : 0
		);
	}, [electricity]);

	// Minimap: project sim-node x/y onto a small canvas each frame, plus a viewport box.
	useEffect(() => {
		const canvas = minimapRef.current;
		if (!canvas || !data) return;
		const ctx = canvas.getContext('2d');
		if (!ctx) return;
		const dpr = Math.min(2, window.devicePixelRatio || 1);
		const W = 168;
		const H = 116;
		canvas.width = W * dpr;
		canvas.height = H * dpr;
		ctx.scale(dpr, dpr);

		let raf = 0;
		let last = 0;
		const draw = (t: number) => {
			raf = requestAnimationFrame(draw);
			if (t - last < 90) return; // ~11fps is plenty for a thumbnail
			last = t;
			const nodes = simNodesRef.current;
			ctx.clearRect(0, 0, W, H);
			if (!nodes.length) return;
			let minX = Infinity;
			let maxX = -Infinity;
			let minY = Infinity;
			let maxY = -Infinity;
			for (const node of nodes) {
				if (node.x === undefined || node.y === undefined) continue;
				if (node.x < minX) minX = node.x;
				if (node.x > maxX) maxX = node.x;
				if (node.y < minY) minY = node.y;
				if (node.y > maxY) maxY = node.y;
			}
			if (!isFinite(minX)) return;
			const pad = 10;
			const spanX = maxX - minX || 1;
			const spanY = maxY - minY || 1;
			const scale = Math.min((W - pad * 2) / spanX, (H - pad * 2) / spanY);
			const offX = (W - spanX * scale) / 2;
			const offY = (H - spanY * scale) / 2;
			const px = (x: number) => offX + (x - minX) * scale;
			const py = (y: number) => offY + (y - minY) * scale;
			for (const node of nodes) {
				if (node.x === undefined || node.y === undefined) continue;
				ctx.fillStyle = colorFor(node.kind);
				ctx.globalAlpha = node.kind === 'group' || node.id === 'root' ? 0.95 : 0.7;
				const r = node.id === 'root' ? 2.4 : node.kind === 'group' ? 1.8 : 1.1;
				ctx.beginPath();
				ctx.arc(px(node.x), py(node.y), r, 0, Math.PI * 2);
				ctx.fill();
			}
			ctx.globalAlpha = 1;
			// Viewport indicator from camera x/y (approximate pan position).
			const cam = graphRef.current?.cameraPosition();
			if (cam) {
				const cx = px(THREE.MathUtils.clamp(cam.x, minX, maxX));
				const cy = py(THREE.MathUtils.clamp(cam.y, minY, maxY));
				const bw = 44;
				const bh = 30;
				ctx.strokeStyle = 'rgba(74,93,191,0.85)';
				ctx.lineWidth = 1;
				ctx.strokeRect(
					THREE.MathUtils.clamp(cx - bw / 2, 0, W - bw),
					THREE.MathUtils.clamp(cy - bh / 2, 0, H - bh),
					bw,
					bh
				);
			}
		};
		raf = requestAnimationFrame(draw);
		return () => cancelAnimationFrame(raf);
	}, [data]);

	const zoomBy = (factor: number) => {
		const graph = graphRef.current;
		if (!graph) return;
		const c = graph.cameraPosition();
		graph.cameraPosition({ x: c.x * factor, y: c.y * factor, z: c.z * factor }, undefined, 240);
	};

	const fitView = () => graphRef.current?.zoomToFit(600, 70);

	const runSearch = (e: React.FormEvent) => {
		e.preventDefault();
		const q = query.trim().toLowerCase();
		if (!q || !data) return;
		const hit =
			data.nodes.find((node) => node.label.toLowerCase() === q) ??
			data.nodes.find((node) => node.label.toLowerCase().includes(q)) ??
			data.nodes.find((node) => node.id.toLowerCase().includes(q));
		if (hit) selectAndFocus(hit);
	};

	const selectedNeighbors = selected
		? Array.from(neighbors.get(selected.id) ?? [])
				.map((id) => nodeById.get(id))
				.filter((node): node is GraphNode => !!node)
		: [];

	const updatedAgo = updatedLabel();

	return (
		<Page eyebrow="STRUCTURE · GRAPHIFY" title="Knowledge Graph" max={null}>
			<GlassPanel
				data-topo="atlas"
				style={{ position: 'relative', height: 'calc(100vh - 142px)', minHeight: 560, overflow: 'hidden' }}
			>
				{/* Storm Activity — masked lightning behind the graph */}
				{storm && (
					<div style={stormLayerStyle} aria-hidden>
						<Lightning hue={252} speed={0.5} intensity={0.9} size={2.2} xOffset={0.3} />
					</div>
				)}

				<div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />

				{/* Top strip — source tabs + node/edge count + rebuild */}
				<div style={topStripStyle}>
					<div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
						{TABS.map((t) => {
							const active = t.id === tab;
							return (
								<button
									key={t.id}
									type="button"
									onClick={() => t.live && setTab(t.id)}
									disabled={!t.live}
									title={t.live ? undefined : 'Coming soon — wires to agent context, wiki, RAG & memory'}
									style={tabStyle(active, t.live)}
								>
									{!t.live && <Lock size={10} strokeWidth={1.8} style={{ opacity: 0.7 }} />}
									{t.label}
								</button>
							);
						})}
					</div>
					<div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
						{stats && (
							<span style={countChipStyle}>
								{stats.n} NODES <span style={{ opacity: 0.4 }}>·</span> {stats.e} EDGES
							</span>
						)}
						<button type="button" onClick={() => setNonce((n) => n + 1)} style={rebuildButtonStyle} title="Rebuild graph">
							<RefreshCw size={13} strokeWidth={1.8} />
							<span>REBUILD</span>
						</button>
					</div>
				</div>

				{/* Control panel — search, legend, toggles */}
				<div style={controlPanelStyle}>
					<form onSubmit={runSearch} style={searchWrapStyle}>
						<Search size={13} strokeWidth={1.8} style={{ color: 'var(--l2-fg-3)', flex: '0 0 auto' }} />
						<input
							value={query}
							onChange={(e) => setQuery(e.target.value)}
							placeholder="Search the graph…"
							style={searchInputStyle}
						/>
					</form>
					<div style={legendStyle}>
						{LEGEND.map((item) => (
							<span key={item.kind} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
								<span style={{ width: 8, height: 8, borderRadius: 8, background: colorFor(item.kind) }} />
								{item.label}
							</span>
						))}
					</div>
					<div style={toggleRowStyle}>
						<Toggle label="Electricity" on={electricity} onClick={() => setElectricity((v) => !v)} />
						<Toggle label="Storm Activity" on={storm} onClick={() => setStorm((v) => !v)} />
					</div>
				</div>

				{/* Stats */}
				{stats && (
					<div style={statsStyle}>
						<div style={statsTitleStyle}>GRAPH STATISTICS</div>
						<Stat label="Nodes" value={String(stats.n)} />
						<Stat label="Edges" value={String(stats.e)} />
						<Stat label="Communities" value={String(stats.communities)} />
						<Stat label="Density" value={stats.density.toFixed(3)} />
						<Stat label="Avg Degree" value={stats.avgDegree.toFixed(2)} />
						<div style={updatedRowStyle}>
							<span style={{ width: 6, height: 6, borderRadius: 6, background: 'var(--atlas-green, #46F0A0)' }} />
							{updatedAgo}
						</div>
					</div>
				)}

				{/* Minimap + camera controls */}
				<div style={minimapWrapStyle}>
					<div style={controlsColStyle}>
						<CtrlButton title="Fit view" onClick={fitView}>
							<Maximize2 size={14} strokeWidth={1.8} />
						</CtrlButton>
						<CtrlButton title="Zoom in" onClick={() => zoomBy(0.78)}>
							<Plus size={14} strokeWidth={1.8} />
						</CtrlButton>
						<CtrlButton title="Zoom out" onClick={() => zoomBy(1.28)}>
							<Minus size={14} strokeWidth={1.8} />
						</CtrlButton>
					</div>
					<div style={minimapFrameStyle}>
						<canvas ref={minimapRef} style={{ width: 168, height: 116, display: 'block' }} />
					</div>
				</div>

				{/* Node inspector */}
				{selected && (
					<div style={inspectStyle}>
						<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
							<span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
								<span style={{ width: 9, height: 9, borderRadius: 9, background: colorFor(selected.kind) }} />
								<span style={inspectKindStyle}>{selected.kind.toUpperCase()}</span>
							</span>
							<button type="button" onClick={() => setSelected(null)} style={inspectCloseStyle} title="Close">
								<X size={13} strokeWidth={1.8} />
							</button>
						</div>
						<div style={inspectTitleStyle}>{selected.label}</div>
						<div style={inspectPathStyle}>{selected.id}</div>
						<button type="button" onClick={() => focusNode(selected)} style={focusButtonStyle}>
							<Crosshair size={12} strokeWidth={1.8} />
							FOCUS
						</button>
						<div style={inspectSectionLabelStyle}>CONNECTIONS · {selectedNeighbors.length}</div>
						<div style={{ display: 'flex', flexDirection: 'column', gap: 3, overflow: 'auto', maxHeight: 220 }}>
							{selectedNeighbors.map((node) => (
								<button key={node.id} type="button" onClick={() => selectAndFocus(node)} style={neighborRowStyle}>
									<span style={{ width: 7, height: 7, borderRadius: 7, background: colorFor(node.kind), flex: '0 0 auto' }} />
									<span style={neighborLabelStyle}>{node.label}</span>
								</button>
							))}
						</div>
					</div>
				)}

				{load.s === 'loading' && <div style={overlayStyle}>Building knowledge graph…</div>}
				{load.s === 'error' && (
					<div style={overlayStyle}>
						<Boxes size={18} strokeWidth={1.6} style={{ color: 'var(--atlas-bronze)' }} />
						<div>Graph unavailable — {load.message}</div>
						<div style={{ fontSize: 11, opacity: 0.6 }}>Confirm the gateway is running.</div>
					</div>
				)}

				<div style={hintStyle}>Drag to orbit · Scroll to zoom · Click a node to inspect</div>
			</GlassPanel>
		</Page>
	);
}

function updatedLabel(): string {
	const at = getGraphFetchedAt();
	if (!at) return 'Updated just now';
	const mins = Math.floor((Date.now() - at) / 60000);
	if (mins <= 0) return 'Updated just now';
	if (mins === 1) return 'Updated 1m ago';
	if (mins < 60) return `Updated ${mins}m ago`;
	const hrs = Math.floor(mins / 60);
	return `Updated ${hrs}h ago`;
}

const LEGEND = [
	{ kind: 'phase', label: 'Phase' },
	{ kind: 'roadmap', label: 'Roadmap/State' },
	{ kind: 'research', label: 'Research' },
	{ kind: 'prep', label: 'Prep' },
	{ kind: 'report', label: 'Report' },
	{ kind: 'group', label: 'Folder' }
];

function Stat({ label, value }: { label: string; value: string }) {
	return (
		<div style={{ display: 'flex', justifyContent: 'space-between', gap: 14 }}>
			<span style={{ color: 'var(--l2-fg-3)' }}>{label}</span>
			<span style={{ color: 'var(--l2-fg-1)' }}>{value}</span>
		</div>
	);
}

function CtrlButton({ title, onClick, children }: { title: string; onClick: () => void; children: React.ReactNode }) {
	return (
		<button type="button" title={title} onClick={onClick} style={ctrlButtonStyle}>
			{children}
		</button>
	);
}

function Toggle({ label, on, onClick }: { label: string; on: boolean; onClick: () => void }) {
	return (
		<button type="button" onClick={onClick} style={toggleButtonStyle}>
			<span style={{ color: on ? 'var(--l2-fg-1)' : 'var(--l2-fg-3)' }}>{label}</span>
			<span style={{ ...trackStyle, background: on ? 'rgba(74,93,191,0.7)' : 'rgba(237,234,224,0.14)' }}>
				<span style={{ ...knobStyle, transform: on ? 'translateX(13px)' : 'translateX(0)' }} />
			</span>
		</button>
	);
}

const stormLayerStyle: React.CSSProperties = {
	position: 'absolute',
	inset: 0,
	pointerEvents: 'none',
	// Persistent grey-violet "storm cloud" base; the reactbits lightning canvas
	// flickers its bolts on top. The shader already outputs alpha, so this sits
	// behind the transparent graph with normal compositing (no screen blend
	// needed — that only washed the cloud out). Masked to an upper-center region.
	background:
		'radial-gradient(95% 68% at 62% 26%, rgba(154,144,208,0.34), rgba(74,80,132,0.15) 40%, transparent 68%)',
	WebkitMaskImage: 'radial-gradient(115% 80% at 62% 26%, #000 0%, rgba(0,0,0,0.6) 52%, transparent 80%)',
	maskImage: 'radial-gradient(115% 80% at 62% 26%, #000 0%, rgba(0,0,0,0.6) 52%, transparent 80%)'
};

const topStripStyle: React.CSSProperties = {
	position: 'absolute',
	top: 0,
	left: 0,
	right: 0,
	height: 44,
	display: 'flex',
	alignItems: 'center',
	justifyContent: 'space-between',
	padding: '0 14px',
	borderBottom: '1px solid rgba(237,234,224,0.07)',
	background: 'linear-gradient(180deg, rgba(7,8,12,0.78), rgba(7,8,12,0.32))',
	backdropFilter: 'blur(8px)'
};

const tabStyle = (active: boolean, live: boolean): React.CSSProperties => ({
	display: 'inline-flex',
	alignItems: 'center',
	gap: 6,
	padding: '6px 12px',
	border: 'none',
	borderRadius: 2,
	background: active ? 'rgba(74,93,191,0.18)' : 'transparent',
	color: active ? 'var(--atlas-celestial)' : live ? 'var(--l2-fg-2)' : 'var(--l2-fg-3)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11.5,
	letterSpacing: '0.03em',
	cursor: live ? 'pointer' : 'not-allowed',
	opacity: live || active ? 1 : 0.55
});

const countChipStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.16em',
	color: 'var(--l2-fg-3)'
};

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

const controlPanelStyle: React.CSSProperties = {
	position: 'absolute',
	top: 58,
	left: 14,
	width: 230,
	display: 'flex',
	flexDirection: 'column',
	gap: 11,
	padding: '12px 13px',
	borderRadius: 2,
	border: '1px solid rgba(237,234,224,0.08)',
	background: 'rgba(7,8,12,0.6)',
	backdropFilter: 'blur(10px)'
};

const searchWrapStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 8,
	padding: '7px 10px',
	borderRadius: 2,
	border: '1px solid rgba(74,93,191,0.3)',
	background: 'rgba(7,8,12,0.5)'
};

const searchInputStyle: React.CSSProperties = {
	flex: 1,
	minWidth: 0,
	border: 'none',
	background: 'transparent',
	outline: 'none',
	color: 'var(--l2-fg-1)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11.5,
	letterSpacing: '0.03em'
};

const legendStyle: React.CSSProperties = {
	display: 'flex',
	flexWrap: 'wrap',
	gap: '7px 12px',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.08em',
	textTransform: 'uppercase',
	color: 'var(--l2-fg-3)'
};

const toggleRowStyle: React.CSSProperties = {
	display: 'flex',
	flexDirection: 'column',
	gap: 7,
	paddingTop: 9,
	borderTop: '1px solid rgba(237,234,224,0.07)'
};

const toggleButtonStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	justifyContent: 'space-between',
	gap: 10,
	border: 'none',
	background: 'transparent',
	padding: 0,
	cursor: 'pointer',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11,
	letterSpacing: '0.03em'
};

const trackStyle: React.CSSProperties = {
	position: 'relative',
	width: 28,
	height: 15,
	borderRadius: 8,
	flex: '0 0 auto',
	transition: 'background 160ms'
};

const knobStyle: React.CSSProperties = {
	position: 'absolute',
	top: 2,
	left: 2,
	width: 11,
	height: 11,
	borderRadius: 11,
	background: '#EDEAE0',
	transition: 'transform 160ms'
};

const statsStyle: React.CSSProperties = {
	position: 'absolute',
	bottom: 14,
	left: 14,
	width: 204,
	display: 'flex',
	flexDirection: 'column',
	gap: 6,
	padding: '12px 13px',
	borderRadius: 2,
	border: '1px solid rgba(237,234,224,0.08)',
	background: 'rgba(7,8,12,0.62)',
	backdropFilter: 'blur(10px)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11
};

const statsTitleStyle: React.CSSProperties = {
	fontSize: 9,
	letterSpacing: '0.18em',
	color: 'var(--atlas-bronze)',
	marginBottom: 2
};

const updatedRowStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 7,
	marginTop: 6,
	paddingTop: 8,
	borderTop: '1px solid rgba(237,234,224,0.07)',
	fontSize: 9.5,
	letterSpacing: '0.08em',
	color: 'var(--l2-fg-3)'
};

const minimapWrapStyle: React.CSSProperties = {
	position: 'absolute',
	bottom: 14,
	right: 14,
	display: 'flex',
	alignItems: 'flex-end',
	gap: 8
};

const controlsColStyle: React.CSSProperties = {
	display: 'flex',
	flexDirection: 'column',
	gap: 6
};

const minimapFrameStyle: React.CSSProperties = {
	padding: 4,
	borderRadius: 3,
	border: '1px solid rgba(74,93,191,0.28)',
	background: 'rgba(7,8,12,0.66)',
	backdropFilter: 'blur(8px)',
	lineHeight: 0
};

const ctrlButtonStyle: React.CSSProperties = {
	width: 34,
	height: 34,
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	borderRadius: 2,
	border: '1px solid rgba(74,93,191,0.32)',
	background: 'rgba(7,8,12,0.62)',
	backdropFilter: 'blur(8px)',
	color: 'var(--atlas-celestial)',
	cursor: 'pointer'
};

const inspectStyle: React.CSSProperties = {
	position: 'absolute',
	top: 58,
	right: 14,
	width: 268,
	display: 'flex',
	flexDirection: 'column',
	gap: 9,
	padding: '13px 14px',
	borderRadius: 2,
	border: '1px solid rgba(74,93,191,0.34)',
	background: 'rgba(9,11,16,0.86)',
	backdropFilter: 'blur(14px)',
	boxShadow: '0 18px 52px rgba(0,0,0,0.45)'
};

const inspectKindStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.16em',
	color: 'var(--l2-fg-3)'
};

const inspectCloseStyle: React.CSSProperties = {
	display: 'inline-flex',
	border: 'none',
	background: 'transparent',
	color: 'var(--l2-fg-3)',
	cursor: 'pointer',
	padding: 2
};

const inspectTitleStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-sans)',
	fontSize: 15,
	fontWeight: 600,
	color: 'var(--l2-fg-1)',
	lineHeight: 1.25
};

const inspectPathStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10.5,
	color: 'var(--l2-fg-3)',
	wordBreak: 'break-all'
};

const inspectSectionLabelStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9,
	letterSpacing: '0.16em',
	color: 'var(--atlas-bronze)',
	marginTop: 2
};

const focusButtonStyle: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	justifyContent: 'center',
	gap: 7,
	padding: '7px 0',
	borderRadius: 2,
	border: '1px solid rgba(74,93,191,0.4)',
	background: 'rgba(74,93,191,0.14)',
	color: 'var(--atlas-celestial)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.14em',
	cursor: 'pointer'
};

const neighborRowStyle: React.CSSProperties = {
	display: 'flex',
	alignItems: 'center',
	gap: 8,
	width: '100%',
	padding: '5px 7px',
	border: 'none',
	borderRadius: 2,
	background: 'rgba(237,234,224,0.03)',
	color: 'var(--l2-fg-2)',
	cursor: 'pointer',
	textAlign: 'left'
};

const neighborLabelStyle: React.CSSProperties = {
	minWidth: 0,
	overflow: 'hidden',
	textOverflow: 'ellipsis',
	whiteSpace: 'nowrap',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11
};

const hintStyle: React.CSSProperties = {
	position: 'absolute',
	bottom: 16,
	left: '50%',
	transform: 'translateX(-50%)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 9.5,
	letterSpacing: '0.1em',
	color: 'var(--l2-fg-3)',
	pointerEvents: 'none',
	opacity: 0.7
};

const rebuildButtonStyle: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	gap: 7,
	padding: '6px 11px',
	borderRadius: 2,
	border: '1px solid rgba(74,93,191,0.4)',
	background: 'rgba(74,93,191,0.12)',
	color: 'var(--atlas-celestial)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.14em',
	cursor: 'pointer'
};
