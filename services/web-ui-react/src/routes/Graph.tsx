import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type * as React from 'react';
import ForceGraph3D from '3d-force-graph';
import * as THREE from 'three';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import SpriteText from 'three-spritetext';
import { Boxes, Crosshair, FolderCog, FolderOpen, Lock, Maximize2, Minus, Plus, RefreshCw, Search, X } from 'lucide-react';
import { Page } from '../components/Page';
import { GlassPanel } from '../components/GlassFx';
import { attachLightning } from '../graph/GraphLightning';
import {
	createGraphScope,
	deleteGraphScope,
	getGraph,
	getGraphFetchedAt,
	listGraphScopes,
	setGraphScopeRoot,
	type CustomGraphScope,
	type GraphData,
	type GraphNode,
	type GraphScope
} from '../lib/api';
import { revealFolder, selectFolder } from '../lib/host';
import {
	BLOOM,
	colorFor,
	FORCE,
	linkColorFor,
	nodeSize,
	particleColorFor,
	TEXT
} from '../graph/GraphVisualConfig';

type Load = { s: 'loading' } | { s: 'ready'; data: GraphData } | { s: 'error'; message: string };
type SimNode = GraphNode & { x?: number; y?: number; z?: number };

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
	d3VelocityDecay: (v: number) => GraphHandle;
	d3AlphaDecay: (v: number) => GraphHandle;
	warmupTicks: (v: number) => GraphHandle;
	cooldownTime: (v: number) => GraphHandle;
	postProcessingComposer: () => { addPass: (p: unknown) => void };
	scene: () => THREE.Scene;
	camera: () => THREE.PerspectiveCamera;
	controls: () => {
		target?: THREE.Vector3;
		enableDamping?: boolean;
		dampingFactor?: number;
		autoRotate?: boolean;
		autoRotateSpeed?: number;
	};
	_destructor?: () => void;
};

type Vec3 = { x: number; y: number; z: number };

type TabDef = { id: string; label: string; live: boolean; scope: GraphScope; custom?: boolean };

const BUILTIN_TABS: TabDef[] = [
	{ id: 'global', label: 'Global', live: true, scope: 'global' },
	{ id: 'projects', label: 'Projects', live: true, scope: 'projects' },
	{ id: 'vault', label: 'Obsidian Vault', live: true, scope: 'obsidian' },
	{ id: 'agent', label: 'Agent Context', live: false, scope: 'atlas' }
];

export default function Graph() {
	const [load, setLoad] = useState<Load>({ s: 'loading' });
	const [reload, setReload] = useState(0);
	const [selected, setSelected] = useState<GraphNode | null>(null);
	const [query, setQuery] = useState('');
	const [tab, setTab] = useState<string>('global');
	const [customScopes, setCustomScopes] = useState<CustomGraphScope[]>([]);
	const [addingPath, setAddingPath] = useState<string | null>(null);
	const [addErr, setAddErr] = useState<string | null>(null);
	const [electricity, setElectricity] = useState(true);
	const [storm, setStorm] = useState(true);
	const [, setClock] = useState(0); // ticks "Updated Xm ago"
	const containerRef = useRef<HTMLDivElement>(null);
	const minimapRef = useRef<HTMLCanvasElement>(null);
	const viewportRectRef = useRef<HTMLDivElement>(null);
	const graphRef = useRef<GraphHandle | null>(null);
	const simNodesRef = useRef<SimNode[]>([]);
	const electricityRef = useRef(electricity);
	const forceNext = useRef(false);
	electricityRef.current = electricity;

	const tabs = useMemo<TabDef[]>(
		() => [
			...BUILTIN_TABS,
			...customScopes.map((s) => ({
				id: s.id,
				label: s.label,
				live: true,
				scope: s.id,
				custom: true
			}))
		],
		[customScopes]
	);
	const scope = tabs.find((t) => t.id === tab)?.scope ?? 'global';

	const refreshScopes = useCallback(async () => {
		setCustomScopes(await listGraphScopes());
	}, []);
	useEffect(() => {
		void refreshScopes();
	}, [refreshScopes]);

	const startAddScope = useCallback(async () => {
		setAddErr(null);
		const picked = await selectFolder('Choose a folder for the new graph tab');
		if (picked) setAddingPath(picked);
	}, []);

	const confirmAddScope = useCallback(
		async (label: string, kind: 'markdown' | 'projects') => {
			if (!addingPath) return;
			try {
				const { scope: created } = await createGraphScope(label, addingPath, kind);
				setAddingPath(null);
				await refreshScopes();
				setTab(created.id);
			} catch (e) {
				setAddErr(e instanceof Error ? e.message : String(e));
			}
		},
		[addingPath, refreshScopes]
	);

	const removeScope = useCallback(
		async (id: string) => {
			try {
				await deleteGraphScope(id);
			} catch {
				/* refresh below reconciles either way */
			}
			if (tab === id) setTab('global');
			await refreshScopes();
		},
		[tab, refreshScopes]
	);

	useEffect(() => {
		let alive = true;
		setLoad({ s: 'loading' });
		setSelected(null);
		setQuery('');
		const force = forceNext.current;
		forceNext.current = false;
		getGraph(scope, force)
			.then((data) => alive && setLoad({ s: 'ready', data }))
			.catch((err) => alive && setLoad({ s: 'error', message: err instanceof Error ? err.message : String(err) }));
		return () => {
			alive = false;
		};
	}, [scope, reload]);

	const rebuild = () => {
		forceNext.current = true;
		setReload((r) => r + 1);
	};

	// Re-render the "Updated Xm ago" label periodically.
	useEffect(() => {
		const t = setInterval(() => setClock((c) => c + 1), 30000);
		return () => clearInterval(t);
	}, []);

	const data = load.s === 'ready' ? load.data : null;

	// Folder actions for the active tab. Built-in projects/obsidian + any custom
	// scope are folder-backed (repointable); atlas/global are repo-derived. The
	// backend scope id is the tab's `scope` (projects/obsidian/<custom slug>).
	const activeTab = tabs.find((t) => t.id === tab);
	const folderBacked =
		activeTab?.scope === 'projects' || activeTab?.scope === 'obsidian' || !!activeTab?.custom;
	const activeRoot = data?.root ?? null;
	const [folderErr, setFolderErr] = useState<string | null>(null);

	const changeFolder = useCallback(async () => {
		if (!activeTab || !folderBacked) return;
		setFolderErr(null);
		try {
			const picked = await selectFolder(`Choose a folder for the ${activeTab.label} graph`);
			if (!picked) return;
			await setGraphScopeRoot(activeTab.scope, picked);
			await refreshScopes();
			forceNext.current = true;
			setReload((r) => r + 1);
		} catch (e) {
			setFolderErr(e instanceof Error ? e.message : String(e));
		}
	}, [activeTab, folderBacked, refreshScopes]);

	const openInExplorer = useCallback(async () => {
		if (!activeRoot) return;
		setFolderErr(null);
		try {
			await revealFolder(activeRoot);
		} catch (e) {
			setFolderErr(e instanceof Error ? e.message : String(e));
		}
	}, [activeRoot]);

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

	// Legend reflects the actual communities in the loaded scope (top by count).
	const legend = useMemo(() => {
		if (!data) return [] as { kind: string; count: number }[];
		const counts = new Map<string, number>();
		for (const node of data.nodes) {
			if (node.kind === 'group') continue;
			counts.set(node.kind, (counts.get(node.kind) ?? 0) + 1);
		}
		return Array.from(counts.entries())
			.sort((a, b) => b[1] - a[1])
			.slice(0, 8)
			.map(([kind, count]) => ({ kind, count }));
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

		// Orbit controls (with damping) feel less "weird" than the default
		// trackball — smoother pan/zoom/orbit that doesn't fight node drag.
		const graph = new (ForceGraph3D as unknown as new (
			e: HTMLElement,
			opts?: { controlType?: string }
		) => GraphHandle)(el, { controlType: 'orbit' })
			.backgroundColor('rgba(7,8,12,0)')
			.showNavInfo(false)
			.nodeLabel((n) => {
				const node = n as GraphNode;
				return `<div style="font-family:var(--l2-font-mono);font-size:11px;letter-spacing:0.04em;color:${TEXT.primary};background:rgba(7,8,12,0.94);border:1px solid rgba(79,139,255,0.4);padding:4px 8px;border-radius:2px"><b>${node.label}</b><br/><span style="color:${TEXT.secondary}">${node.kind} · ${node.id}</span></div>`;
			})
			.nodeColor((n) => colorFor((n as GraphNode).kind))
			.nodeVal((n) => nodeSize(n as GraphNode))
			.nodeOpacity(0.9)
			.nodeResolution(14)
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
			.linkWidth(0.5)
			.linkOpacity(0.5)
			.linkDirectionalParticles((l) =>
				electricityRef.current && (l as { kind: string }).kind !== 'contains' ? 3 : 0
			)
			.linkDirectionalParticleWidth(2.6)
			.linkDirectionalParticleSpeed(0.012)
			.linkDirectionalParticleColor((l) => particleColorFor((l as { kind: string }).kind))
			.width(el.clientWidth)
			.height(el.clientHeight)
			.onNodeClick((n) => selectAndFocus(n as GraphNode))
			.graphData({ nodes: simNodes, links: data.links.map((link) => ({ ...link })) });

		// Smoothed cooling + weighted damping: drag is responsive but settles
		// without violent spring-back; orbit damps instead of snapping.
		graph.d3VelocityDecay(FORCE.velocityDecay).d3AlphaDecay(FORCE.alphaDecay).cooldownTime(FORCE.cooldownTime);
		const controls = graph.controls();
		if (controls) {
			controls.enableDamping = true;
			controls.dampingFactor = FORCE.orbitDamping;
			// Ambient orbit: the camera slowly circles the fitted center while
			// idle; user drag overrides it and it resumes after (OrbitControls).
			controls.autoRotate = true;
			controls.autoRotateSpeed = FORCE.autoRotateSpeed;
		}

		// Center the layout once it settles.
		let fitted = false;
		graph.onEngineStop(() => {
			if (fitted) return;
			fitted = true;
			graph.zoomToFit(700, 80);
		});

		// Unreal bloom — gentle: bright cores/particles glow, hubs don't melt.
		try {
			const bloom = new UnrealBloomPass(
				new THREE.Vector2(el.clientWidth, el.clientHeight),
				BLOOM.strength,
				BLOOM.radius,
				BLOOM.threshold
			);
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
			electricity && (l as { kind: string }).kind !== 'contains' ? 3 : 0
		);
	}, [electricity]);

	// Storm Activity → lightning discharging within the densest clusters.
	// (The per-cluster fog/smoke was removed — it read as out-of-place blobs.)
	useEffect(() => {
		const graph = graphRef.current;
		if (!graph || !data || !storm) return;
		return attachLightning(graph.scene(), data.nodes, () => simNodesRef.current);
	}, [data, storm]);

	// Minimap = a true secondary viewport: a second WebGL renderer drawing the
	// main graph's *same scene* from a far camera framed to fit every node. It
	// mirrors the live layout (same positions/clusters) zoomed all the way out,
	// matches the main container's aspect ratio, overlays the current camera
	// viewport as a rectangle, and navigates the main graph on click. ~10fps.
	useEffect(() => {
		const canvas = minimapRef.current;
		const graph = graphRef.current;
		const container = containerRef.current;
		if (!canvas || !data || !graph || !container) return;
		let renderer: THREE.WebGLRenderer;
		try {
			renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
		} catch {
			return;
		}
		// Match the main container's aspect ratio so the global shape reads true.
		const W = 184;
		const aspect = container.clientWidth / Math.max(1, container.clientHeight);
		const H = Math.round(THREE.MathUtils.clamp(W / aspect, 88, 150));
		canvas.style.width = `${W}px`;
		canvas.style.height = `${H}px`;
		renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
		renderer.setSize(W, H, false);
		renderer.setClearColor(0x000000, 0);
		const scene = graph.scene();
		const cam = new THREE.PerspectiveCamera(50, W / H, 1, 500000);
		const center = new THREE.Vector3();
		const halfFov = (cam.fov * Math.PI) / 180 / 2;
		let miniDist = 1;

		// Click → translate the main camera to look at the picked world point.
		const onClick = (ev: MouseEvent) => {
			const r = canvas.getBoundingClientRect();
			const ndc = new THREE.Vector3(
				((ev.clientX - r.left) / r.width) * 2 - 1,
				-(((ev.clientY - r.top) / r.height) * 2 - 1),
				0.5
			).unproject(cam);
			const dir = ndc.sub(cam.position).normalize();
			const tt = (center.z - cam.position.z) / (dir.z || 1e-6);
			const world = cam.position.clone().add(dir.multiplyScalar(tt));
			const mainCam = graph.camera();
			const target = graph.controls()?.target ?? new THREE.Vector3();
			const offset = mainCam.position.clone().sub(target);
			graph.cameraPosition(
				{ x: world.x + offset.x, y: world.y + offset.y, z: world.z + offset.z },
				world,
				600
			);
		};
		canvas.addEventListener('click', onClick);

		let raf = 0;
		let last = 0;
		const draw = (t: number) => {
			raf = requestAnimationFrame(draw);
			if (t - last < 100) return; // ~10fps — plenty for a thumbnail
			last = t;
			const nodes = simNodesRef.current;
			let minX = Infinity, minY = Infinity, minZ = Infinity;
			let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
			for (const n of nodes) {
				if (n.x === undefined || n.y === undefined || n.z === undefined) continue;
				minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x);
				minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y);
				minZ = Math.min(minZ, n.z); maxZ = Math.max(maxZ, n.z);
			}
			if (isFinite(minX)) {
				center.set((minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2);
				const radius = Math.max(maxX - minX, maxY - minY, maxZ - minZ) / 2 || 50;
				miniDist = (radius / Math.tan(halfFov)) * 1.25 + 40;
				// Aim the minimap camera along the *main* camera's view direction
				// (pulled back to fit every node) so it mirrors the live rotation
				// instead of staying a fixed front view.
				const mainCam = graph.camera();
				const tgt = graph.controls()?.target ?? center;
				const dir = mainCam.position.clone().sub(tgt);
				if (dir.lengthSq() < 1e-6) dir.set(0, 0, 1);
				dir.normalize();
				cam.position.copy(center).addScaledVector(dir, miniDist);
				cam.up.copy(mainCam.up);
				cam.lookAt(center);
				cam.updateProjectionMatrix();
			}
			renderer.render(scene, cam);

			// Viewport overlay: project the main camera target into minimap space;
			// size the rect by how much of the graph the main camera sees.
			const rect = viewportRectRef.current;
			const target = graph.controls()?.target;
			if (rect && target) {
				const p = target.clone().project(cam);
				const sx = (p.x * 0.5 + 0.5) * W;
				const sy = (-p.y * 0.5 + 0.5) * H;
				const mainDist = graph.camera().position.distanceTo(target);
				const frac = THREE.MathUtils.clamp(mainDist / miniDist, 0.1, 1);
				const rw = W * frac;
				const rh = H * frac;
				rect.style.display = 'block';
				rect.style.left = `${THREE.MathUtils.clamp(sx - rw / 2, 0, W - rw)}px`;
				rect.style.top = `${THREE.MathUtils.clamp(sy - rh / 2, 0, H - rh)}px`;
				rect.style.width = `${rw}px`;
				rect.style.height = `${rh}px`;
			}
		};
		raf = requestAnimationFrame(draw);
		return () => {
			cancelAnimationFrame(raf);
			canvas.removeEventListener('click', onClick);
			renderer.dispose();
		};
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

	const updatedAgo = updatedLabel(scope);

	return (
		<Page eyebrow="STRUCTURE · GRAPHIFY" title="Knowledge Graph" max={null}>
			<GlassPanel
				data-topo="atlas"
				style={{ position: 'relative', height: 'calc(100vh - 142px)', minHeight: 560, overflow: 'hidden' }}
			>
				<div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />

				{/* Top strip — source tabs + node/edge count + rebuild */}
				<div style={topStripStyle}>
					<div style={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
						{tabs.map((t) => {
							const active = t.id === tab;
							return (
								<span key={t.id} style={{ display: 'inline-flex', alignItems: 'center' }}>
									<button
										type="button"
										onClick={() => t.live && setTab(t.id)}
										disabled={!t.live}
										title={
											t.live
												? t.custom
													? 'Custom graph tab'
													: undefined
												: 'Coming soon — wires to agent context, wiki, RAG & memory'
										}
										style={tabStyle(active, t.live)}
									>
										{!t.live && <Lock size={10} strokeWidth={1.8} style={{ opacity: 0.7 }} />}
										{t.label}
									</button>
									{t.custom && (
										<button
											type="button"
											aria-label={`Remove graph tab ${t.label}`}
											title="Remove this graph tab"
											onClick={() => void removeScope(t.id)}
											style={{
												background: 'none',
												border: 'none',
												color: 'var(--l2-fg-3)',
												cursor: 'pointer',
												padding: '0 4px',
												display: 'inline-flex'
											}}
										>
											<X size={10} strokeWidth={2} />
										</button>
									)}
								</span>
							);
						})}
						<button
							type="button"
							onClick={() => void startAddScope()}
							title="Add a graph tab from a folder"
							aria-label="Add graph tab"
							style={{
								display: 'inline-flex',
								alignItems: 'center',
								justifyContent: 'center',
								width: 24,
								height: 24,
								marginLeft: 4,
								borderRadius: 2,
								border: '1px dashed var(--l2-hairline)',
								background: 'transparent',
								color: 'var(--l2-fg-3)',
								cursor: 'pointer'
							}}
						>
							<Plus size={12} strokeWidth={2} />
						</button>
					</div>
					<div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
						{stats && (
							<span style={countChipStyle}>
								{stats.n} NODES <span style={{ opacity: 0.4 }}>·</span> {stats.e} EDGES
							</span>
						)}
						<div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
							{folderBacked && (
								<button
									type="button"
									onClick={() => void changeFolder()}
									style={folderButtonStyle}
									title={`Change the ${activeTab?.label ?? ''} folder`}
									aria-label="Change graph folder"
								>
									<FolderCog size={13} strokeWidth={1.8} />
									<span>FOLDER</span>
								</button>
							)}
							{activeRoot && (
								<button
									type="button"
									onClick={() => void openInExplorer()}
									style={folderButtonStyle}
									title={`Open ${activeRoot} in the file manager`}
									aria-label="Open folder in file manager"
								>
									<FolderOpen size={13} strokeWidth={1.8} />
									<span>EXPLORER</span>
								</button>
							)}
						</div>
						<button type="button" onClick={rebuild} style={rebuildButtonStyle} title="Rebuild graph">
							<RefreshCw size={13} strokeWidth={1.8} />
							<span>REBUILD</span>
						</button>
					</div>
				</div>
				{folderErr && (
					<div
						role="alert"
						style={{
							position: 'absolute',
							top: 52,
							right: 16,
							zIndex: 6,
							maxWidth: 320,
							padding: '6px 10px',
							borderRadius: 2,
							border: '1px solid rgba(255,0,85,0.4)',
							background: 'rgba(20,6,10,0.9)',
							color: 'var(--l2-error)',
							fontFamily: 'var(--l2-font-mono)',
							fontSize: 11
						}}
					>
						{folderErr}
					</div>
				)}

				{addingPath && (
					<NewScopeDialog
						path={addingPath}
						error={addErr}
						onConfirm={(label, kind) => void confirmAddScope(label, kind)}
						onCancel={() => {
							setAddingPath(null);
							setAddErr(null);
						}}
					/>
				)}

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
						{legend.map((item) => (
							<span key={item.kind} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} title={`${item.count} nodes`}>
								<span style={{ width: 8, height: 8, borderRadius: 8, background: colorFor(item.kind) }} />
								{item.kind}
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
						<div style={{ position: 'relative', lineHeight: 0, cursor: 'pointer' }} title="Click to navigate">
							<canvas ref={minimapRef} style={{ width: 184, height: 112, display: 'block' }} />
							<div ref={viewportRectRef} style={viewportRectStyle} />
						</div>
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

function updatedLabel(scope: GraphScope): string {
	const at = getGraphFetchedAt(scope);
	if (!at) return 'Updated just now';
	const mins = Math.floor((Date.now() - at) / 60000);
	if (mins <= 0) return 'Updated just now';
	if (mins === 1) return 'Updated 1m ago';
	if (mins < 60) return `Updated ${mins}m ago`;
	const hrs = Math.floor(mins / 60);
	return `Updated ${hrs}h ago`;
}

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
	borderBottom: active ? '2px solid rgba(79,139,255,0.9)' : '2px solid transparent',
	borderRadius: 2,
	background: active ? 'rgba(79,139,255,0.14)' : 'transparent',
	// Active = full ivory; live-inactive = secondary; disabled = ghost.
	color: active ? TEXT.primary : live ? TEXT.secondary : TEXT.ghost,
	textShadow: active ? '0 0 10px rgba(79,139,255,0.45)' : 'none',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 11.5,
	letterSpacing: '0.03em',
	cursor: live ? 'pointer' : 'not-allowed',
	opacity: live || active ? 1 : 0.7
});

const countChipStyle: React.CSSProperties = {
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.16em',
	color: TEXT.secondary
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
	fontSize: 10,
	letterSpacing: '0.06em',
	textTransform: 'uppercase',
	color: TEXT.secondary
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
	fontSize: 10,
	letterSpacing: '0.06em',
	color: TEXT.secondary
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
	border: '1px solid rgba(79,139,255,0.28)',
	background: 'rgba(7,8,12,0.66)',
	backdropFilter: 'blur(8px)',
	lineHeight: 0
};

const viewportRectStyle: React.CSSProperties = {
	position: 'absolute',
	display: 'none',
	border: '1px solid rgba(79,139,255,0.9)',
	background: 'rgba(79,139,255,0.08)',
	borderRadius: 2,
	pointerEvents: 'none',
	boxShadow: '0 0 8px rgba(79,139,255,0.35)'
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
	fontSize: 10,
	letterSpacing: '0.08em',
	color: TEXT.secondary,
	pointerEvents: 'none',
	opacity: 0.9
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

const folderButtonStyle: React.CSSProperties = {
	display: 'inline-flex',
	alignItems: 'center',
	gap: 6,
	padding: '6px 10px',
	borderRadius: 2,
	border: '1px solid var(--l2-hairline)',
	background: 'transparent',
	color: 'var(--l2-fg-2)',
	fontFamily: 'var(--l2-font-mono)',
	fontSize: 10,
	letterSpacing: '0.14em',
	cursor: 'pointer'
};

/** Name + kind picker for a new custom graph tab (folder already chosen). */
function NewScopeDialog({
	path,
	error,
	onConfirm,
	onCancel
}: {
	path: string;
	error: string | null;
	onConfirm: (label: string, kind: 'markdown' | 'projects') => void;
	onCancel: () => void;
}) {
	const [label, setLabel] = useState(() => path.split(/[\\/]/).filter(Boolean).pop() ?? 'New graph');
	const [kind, setKind] = useState<'markdown' | 'projects'>('markdown');
	return (
		<div
			onClick={onCancel}
			style={{ position: 'absolute', inset: 0, zIndex: 30, display: 'grid', placeItems: 'center', background: 'rgba(5,6,10,0.72)', backdropFilter: 'blur(4px)' }}
		>
			<div
				onClick={(e) => e.stopPropagation()}
				style={{ width: 'min(440px, 90%)', borderRadius: 2, border: '1px solid var(--l2-hairline)', background: 'linear-gradient(160deg, rgba(20,24,33,0.98), rgba(10,12,18,0.98))', boxShadow: '0 24px 70px rgba(0,0,0,0.6)', padding: 18 }}
			>
				<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, letterSpacing: '0.2em', color: 'var(--atlas-celestial)', marginBottom: 10 }}>
					NEW GRAPH TAB
				</div>
				<div style={{ fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, color: 'var(--l2-fg-3)', marginBottom: 12, overflowWrap: 'anywhere' }}>
					{path}
				</div>
				<input
					autoFocus
					value={label}
					onChange={(e) => setLabel(e.target.value)}
					onKeyDown={(e) => {
						if (e.key === 'Enter' && label.trim()) onConfirm(label.trim(), kind);
						if (e.key === 'Escape') onCancel();
					}}
					placeholder="Tab name"
					style={{ width: '100%', height: 34, borderRadius: 2, border: '1px solid var(--l2-hairline)', background: 'rgba(9,11,16,0.72)', color: 'var(--l2-fg-1)', fontSize: 13, padding: '0 10px', outline: 'none', marginBottom: 12 }}
				/>
				<div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
					{(['markdown', 'projects'] as const).map((k) => (
						<button
							key={k}
							type="button"
							onClick={() => setKind(k)}
							title={k === 'markdown' ? 'One graph of every markdown file in the folder' : 'One cluster per sub-folder (projects overview)'}
							style={{
								padding: '6px 12px',
								borderRadius: 2,
								border: `1px solid ${kind === k ? 'rgba(79,139,255,0.5)' : 'var(--l2-hairline)'}`,
								background: kind === k ? 'rgba(79,139,255,0.12)' : 'transparent',
								color: kind === k ? 'var(--atlas-celestial)' : 'var(--l2-fg-3)',
								fontFamily: 'var(--l2-font-mono)',
								fontSize: 10,
								letterSpacing: '0.14em',
								cursor: 'pointer',
								textTransform: 'uppercase'
							}}
						>
							{k}
						</button>
					))}
				</div>
				{error && (
					<div style={{ color: 'var(--l2-error)', fontSize: 11.5, fontFamily: 'var(--l2-font-mono)', marginBottom: 12 }}>{error}</div>
				)}
				<div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
					<button type="button" onClick={onCancel} style={{ padding: '7px 14px', borderRadius: 2, border: '1px solid var(--l2-hairline)', background: 'transparent', color: 'var(--l2-fg-2)', fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, letterSpacing: '0.14em', cursor: 'pointer' }}>
						CANCEL
					</button>
					<button
						type="button"
						disabled={!label.trim()}
						onClick={() => onConfirm(label.trim(), kind)}
						style={{ padding: '7px 14px', borderRadius: 2, border: '1px solid rgba(70,240,160,0.4)', background: 'rgba(70,240,160,0.12)', color: 'var(--atlas-emerald)', fontFamily: 'var(--l2-font-mono)', fontSize: 10.5, letterSpacing: '0.14em', cursor: label.trim() ? 'pointer' : 'default', opacity: label.trim() ? 1 : 0.5 }}
					>
						CREATE TAB
					</button>
				</div>
			</div>
		</div>
	);
}
