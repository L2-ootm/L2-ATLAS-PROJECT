// World-anchored "knowledge mist" for the Graphify graph.
//
// Replaces the old screen-space lightning/cloud (which felt fixed to the
// viewport). Fog is rendered as additive THREE.Sprites placed at each cluster's
// centroid *inside the graph scene*, so it moves and parallaxes with the graph
// as the camera orbits/zooms. Intensity is driven by cluster density (a stable
// stand-in for future "consultation activity") and smoothed, not per-frame.

import * as THREE from 'three';
import type { GraphNode } from '../lib/api';
import { colorFor } from './GraphVisualConfig';

type SimNode = GraphNode & { x?: number; y?: number; z?: number };

const FOG = {
	minClusterSize: 4,
	maxClusters: 12,
	updateMs: 1000, // recompute centroids ~1x/sec, not per frame
	baseOpacity: 0.04,
	maxOpacity: 0.1,
	smoothing: 0.25,
	maxScale: 150 // cap so a wide cluster doesn't become a giant dome
} as const;

let sharedTexture: THREE.Texture | null = null;
function fogTexture(): THREE.Texture {
	if (sharedTexture) return sharedTexture;
	const size = 128;
	const c = document.createElement('canvas');
	c.width = c.height = size;
	const ctx = c.getContext('2d');
	if (ctx) {
		const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
		g.addColorStop(0, 'rgba(255,255,255,0.85)');
		g.addColorStop(0.45, 'rgba(255,255,255,0.22)');
		g.addColorStop(1, 'rgba(255,255,255,0)');
		ctx.fillStyle = g;
		ctx.fillRect(0, 0, size, size);
	}
	sharedTexture = new THREE.CanvasTexture(c);
	return sharedTexture;
}

/**
 * Attach fog sprites for the densest clusters to `scene`. Returns a cleanup
 * function that stops the updater and removes/disposes the sprites.
 */
export function attachFog(
	scene: THREE.Scene,
	nodes: GraphNode[],
	getSimNodes: () => SimNode[]
): () => void {
	// Rank clusters (graph `group`) by node count; fog only the densest.
	const groups = new Map<string, { kind: string; count: number }>();
	for (const n of nodes) {
		if (n.kind === 'group' || n.id === 'root') continue;
		const g = groups.get(n.group);
		if (g) g.count += 1;
		else groups.set(n.group, { kind: n.kind, count: 1 });
	}
	const top = Array.from(groups.entries())
		.filter(([, v]) => v.count >= FOG.minClusterSize)
		.sort((a, b) => b[1].count - a[1].count)
		.slice(0, FOG.maxClusters);

	const tex = fogTexture();
	const sprites: { sprite: THREE.Sprite; group: string; count: number }[] = [];
	for (const [group, info] of top) {
		const tint = new THREE.Color(colorFor(info.kind)).lerp(new THREE.Color('#ffffff'), 0.25);
		const material = new THREE.SpriteMaterial({
			map: tex,
			color: tint,
			transparent: true,
			opacity: 0,
			blending: THREE.AdditiveBlending,
			depthWrite: false
		});
		const sprite = new THREE.Sprite(material);
		sprite.renderOrder = -1; // behind nodes
		scene.add(sprite);
		sprites.push({ sprite, group, count: info.count });
	}

	const update = () => {
		const sim = getSimNodes();
		for (const { sprite, group, count } of sprites) {
			let cx = 0, cy = 0, cz = 0, n = 0;
			for (const node of sim) {
				if (node.group !== group || node.x === undefined) continue;
				cx += node.x; cy += node.y ?? 0; cz += node.z ?? 0; n += 1;
			}
			const mat = sprite.material as THREE.SpriteMaterial;
			if (!n) {
				sprite.visible = false;
				continue;
			}
			cx /= n; cy /= n; cz /= n;
			let spread = 0;
			for (const node of sim) {
				if (node.group !== group || node.x === undefined) continue;
				spread = Math.max(spread, Math.hypot(node.x - cx, (node.y ?? 0) - cy, (node.z ?? 0) - cz));
			}
			sprite.visible = true;
			sprite.position.set(cx, cy, cz);
			const s = Math.min(Math.max(40, spread * 1.5 + 25), FOG.maxScale);
			sprite.scale.set(s, s, 1);
			// Density-driven, smoothed opacity (foundation for activity later).
			const target = THREE.MathUtils.clamp(FOG.baseOpacity + count / 400, FOG.baseOpacity, FOG.maxOpacity);
			mat.opacity += (target - mat.opacity) * FOG.smoothing;
		}
	};

	update();
	const interval = window.setInterval(update, FOG.updateMs);

	return () => {
		window.clearInterval(interval);
		for (const { sprite } of sprites) {
			scene.remove(sprite);
			(sprite.material as THREE.SpriteMaterial).dispose();
		}
	};
}
