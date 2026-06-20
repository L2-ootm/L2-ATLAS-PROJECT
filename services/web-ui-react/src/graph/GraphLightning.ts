// In-scene lightning for the Graphify storm.
//
// Periodically flashes a bright additive bolt between two nearby nodes inside
// one of the densest clusters (the same clusters GraphFog clouds over), so the
// lightning reads as discharging *within* the storm. Bolts are jagged polylines
// that flash on and decay over a few hundred ms; UnrealBloom turns the thin
// bright lines into glowing arcs. Spawn rate is low and concurrency is capped,
// so this stays cheap. Gated by the Storm Activity toggle (attach/detach).

import * as THREE from 'three';
import type { GraphNode } from '../lib/api';
import { colorFor } from './GraphVisualConfig';

type SimNode = GraphNode & { x?: number; y?: number; z?: number };

const LIGHTNING = {
	minClusterSize: 4,
	maxClusters: 12,
	spawnMinMs: 460, // randomized gap between strikes
	spawnMaxMs: 1250,
	maxConcurrent: 4,
	segments: 10, // jag subdivisions per bolt
	jitter: 0.28, // perpendicular displacement as a fraction of bolt length
	maxLen: 170, // skip node pairs farther apart than this (keep bolts local)
	sampleTries: 6, // sample N candidate endpoints, keep the farthest in-range
	lifeMs: 360, // flash + decay duration
	tint: 0.72, // lerp the cluster color this far toward white (electric)
	flashScale: 18 // size of the bright endpoint discharge sprites
} as const;

type Bolt = {
	line: THREE.Line;
	flashes: THREE.Sprite[];
	born: number;
};

// Shared radial texture for the bright endpoint discharge sprites.
let flashTex: THREE.Texture | null = null;
function flashTexture(): THREE.Texture {
	if (flashTex) return flashTex;
	const size = 64;
	const c = document.createElement('canvas');
	c.width = c.height = size;
	const ctx = c.getContext('2d');
	if (ctx) {
		const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
		g.addColorStop(0, 'rgba(255,255,255,1)');
		g.addColorStop(0.35, 'rgba(255,255,255,0.55)');
		g.addColorStop(1, 'rgba(255,255,255,0)');
		ctx.fillStyle = g;
		ctx.fillRect(0, 0, size, size);
	}
	flashTex = new THREE.CanvasTexture(c);
	return flashTex;
}

/**
 * Attach the lightning emitter to `scene`. Returns a cleanup function that
 * stops the emitter and disposes any in-flight bolts.
 */
export function attachLightning(
	scene: THREE.Scene,
	nodes: GraphNode[],
	getSimNodes: () => SimNode[]
): () => void {
	// Cluster membership + a per-cluster electric color, ranked by density.
	const members = new Map<string, { kind: string; ids: Set<string> }>();
	for (const n of nodes) {
		if (n.kind === 'group' || n.id === 'root') continue;
		const m = members.get(n.group);
		if (m) m.ids.add(n.id);
		else members.set(n.group, { kind: n.kind, ids: new Set([n.id]) });
	}
	const clusters = Array.from(members.entries())
		.filter(([, v]) => v.ids.size >= LIGHTNING.minClusterSize)
		.sort((a, b) => b[1].ids.size - a[1].ids.size)
		.slice(0, LIGHTNING.maxClusters)
		.map(([group, v]) => ({
			group,
			ids: v.ids,
			color: new THREE.Color(colorFor(v.kind)).lerp(new THREE.Color('#ffffff'), LIGHTNING.tint)
		}));

	if (!clusters.length) return () => {};

	const bolts: Bolt[] = [];

	const spawn = (now: number) => {
		if (bolts.length >= LIGHTNING.maxConcurrent) return;
		const cluster = clusters[(Math.random() * clusters.length) | 0];
		// Live positions for this cluster's nodes.
		const pts: THREE.Vector3[] = [];
		for (const node of getSimNodes()) {
			if (node.x === undefined || !cluster.ids.has(node.id)) continue;
			pts.push(new THREE.Vector3(node.x, node.y ?? 0, node.z ?? 0));
		}
		if (pts.length < 2) return;

		const a = pts[(Math.random() * pts.length) | 0];
		// Pick the farthest in-range candidate of a few random samples → bolts
		// arc across the cluster (visible) rather than hugging the nearest node.
		let b: THREE.Vector3 | null = null;
		let best = 0;
		for (let i = 0; i < LIGHTNING.sampleTries; i++) {
			const cand = pts[(Math.random() * pts.length) | 0];
			if (cand === a) continue;
			const d = cand.distanceTo(a);
			if (d > best && d <= LIGHTNING.maxLen) {
				best = d;
				b = cand;
			}
		}
		if (!b || best < 1e-3) return;

		const line = makeBolt(a, b, cluster.color);
		scene.add(line);
		const mid = a.clone().lerp(b, 0.5);
		const flashes = [
			makeFlash(a, cluster.color, 1),
			makeFlash(b, cluster.color, 1),
			makeFlash(mid, cluster.color, 1.35) // brighter core lights the arc center
		];
		for (const f of flashes) scene.add(f);
		bolts.push({ line, flashes, born: now });
	};

	let raf = 0;
	let nextSpawn = performance.now() + rand(LIGHTNING.spawnMinMs, LIGHTNING.spawnMaxMs);
	const tick = (t: number) => {
		raf = requestAnimationFrame(tick);
		if (t >= nextSpawn) {
			spawn(t);
			nextSpawn = t + rand(LIGHTNING.spawnMinMs, LIGHTNING.spawnMaxMs);
		}
		for (let i = bolts.length - 1; i >= 0; i--) {
			const bolt = bolts[i];
			const age = (t - bolt.born) / LIGHTNING.lifeMs;
			const mat = bolt.line.material as THREE.LineBasicMaterial;
			if (age >= 1) {
				disposeBolt(scene, bolt);
				bolts.splice(i, 1);
				continue;
			}
			// Fast rise, flicker, decay — a struck-then-fading arc.
			const env = age < 0.12 ? age / 0.12 : 1 - (age - 0.12) / 0.88;
			const flicker = 0.7 + 0.3 * Math.sin(age * 48);
			const op = THREE.MathUtils.clamp(env * flicker, 0, 1);
			mat.opacity = op;
			for (const f of bolt.flashes) (f.material as THREE.SpriteMaterial).opacity = op * 0.85;
		}
	};
	raf = requestAnimationFrame(tick);

	return () => {
		cancelAnimationFrame(raf);
		for (const bolt of bolts) disposeBolt(scene, bolt);
		bolts.length = 0;
	};
}

function disposeBolt(scene: THREE.Scene, bolt: Bolt): void {
	scene.remove(bolt.line);
	bolt.line.geometry.dispose();
	(bolt.line.material as THREE.LineBasicMaterial).dispose();
	for (const f of bolt.flashes) {
		scene.remove(f);
		(f.material as THREE.SpriteMaterial).dispose();
	}
}

function makeFlash(at: THREE.Vector3, color: THREE.Color, scale: number): THREE.Sprite {
	const material = new THREE.SpriteMaterial({
		map: flashTexture(),
		color: color.clone().lerp(new THREE.Color('#ffffff'), 0.4),
		transparent: true,
		opacity: 0,
		blending: THREE.AdditiveBlending,
		depthWrite: false
	});
	const sprite = new THREE.Sprite(material);
	sprite.position.copy(at);
	sprite.scale.setScalar(LIGHTNING.flashScale * scale);
	sprite.renderOrder = 2;
	return sprite;
}

function rand(min: number, max: number): number {
	return min + Math.random() * (max - min);
}

// Build a jagged additive line from `a` to `b` with perpendicular jitter that
// peaks mid-bolt (zero at the endpoints so it still connects the two nodes).
function makeBolt(a: THREE.Vector3, b: THREE.Vector3, color: THREE.Color): THREE.Line {
	const dir = b.clone().sub(a);
	const len = dir.length();
	dir.normalize();
	// Two perpendicular axes for 3D displacement.
	const up = Math.abs(dir.y) > 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0);
	const p1 = new THREE.Vector3().crossVectors(dir, up).normalize();
	const p2 = new THREE.Vector3().crossVectors(dir, p1).normalize();

	const seg = LIGHTNING.segments;
	const amp = len * LIGHTNING.jitter;
	const positions = new Float32Array((seg + 1) * 3);
	for (let i = 0; i <= seg; i++) {
		const f = i / seg;
		const point = a.clone().lerp(b, f);
		const taper = Math.sin(f * Math.PI); // 0 at ends, 1 at middle
		if (i > 0 && i < seg) {
			const j1 = (Math.random() * 2 - 1) * amp * taper;
			const j2 = (Math.random() * 2 - 1) * amp * taper;
			point.add(p1.clone().multiplyScalar(j1)).add(p2.clone().multiplyScalar(j2));
		}
		positions[i * 3] = point.x;
		positions[i * 3 + 1] = point.y;
		positions[i * 3 + 2] = point.z;
	}

	const geometry = new THREE.BufferGeometry();
	geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
	const material = new THREE.LineBasicMaterial({
		color,
		transparent: true,
		opacity: 0,
		blending: THREE.AdditiveBlending,
		depthWrite: false
	});
	const line = new THREE.Line(geometry, material);
	line.renderOrder = 1; // in front of clouds
	return line;
}
