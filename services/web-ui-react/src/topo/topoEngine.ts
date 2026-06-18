/* ==========================================================================
   Topographic engine — ported from the L2 Design System (topo_engine.js).
   Draws resting contour lines over a static noise heightfield; the cursor (or a
   typing trail / sonar ping) creates a local height bulge that re-draws contours
   with a contextual glow colour. WebView2-safe (SVG DOM + requestAnimationFrame).

   Philosophy: the terrain is always there, faint; it responds to presence; colour
   is meaning, not region; it recedes behind content. Keep glowOpacity low for the
   ambient background field so it never competes with foreground data.
   ========================================================================== */

export interface TopoFieldOptions {
	host: HTMLElement;
	viewW: number;
	viewH: number;
	color?: string;
	glowColor?: string;
	cellSize?: number;
	levels?: number[];
	restingOpacity?: number;
	hoverRadius?: number;
	bulgeStrength?: number;
	seed?: number;
	freq?: number;
	restingWidth?: number;
	glowWidth?: number;
	glowOpacity?: number;
	trailDecay?: number;
	trailRadius?: number;
	trailMax?: number;
	sonarSpeed?: number;
	sonarMaxR?: number;
	sonarRingW?: number;
}

export interface TopoFieldAPI {
	setHover(x: number, y: number, color?: string): void;
	endHover(): void;
	pushTrail(x: number, y: number, color?: string): void;
	sonarPing(x: number, y: number, color?: string): void;
	clearTrail(): void;
	destroy(): void;
}

// cheap 2D value noise
function hash(i: number, j: number, seed: number): number {
	const x = Math.sin(i * 127.1 + j * 311.7 + seed * 13.0) * 43758.5453;
	return x - Math.floor(x);
}
function smooth(t: number): number {
	return t * t * (3 - 2 * t);
}
function noise2(x: number, y: number, seed: number): number {
	const xi = Math.floor(x), yi = Math.floor(y);
	const xf = x - xi, yf = y - yi;
	const a = hash(xi, yi, seed), b = hash(xi + 1, yi, seed);
	const c = hash(xi, yi + 1, seed), d = hash(xi + 1, yi + 1, seed);
	const u = smooth(xf), v = smooth(yf);
	return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
}
function fbm(x: number, y: number, seed: number): number {
	let s = 0, a = 1, f = 1, norm = 0;
	for (let i = 0; i < 3; i++) {
		s += noise2(x * f, y * f, seed + i) * a;
		norm += a; a *= 0.55; f *= 2.0;
	}
	return s / norm;
}

// Marching squares contour extraction at threshold.
function contours(
	field: Float32Array, cols: number, rows: number,
	cellW: number, cellH: number, threshold: number
): number[] {
	const segs: number[] = [];
	for (let j = 0; j < rows - 1; j++) {
		for (let i = 0; i < cols - 1; i++) {
			const tl = field[j * cols + i], tr = field[j * cols + i + 1];
			const bl = field[(j + 1) * cols + i], br = field[(j + 1) * cols + i + 1];
			let code = 0;
			if (tl > threshold) code |= 1;
			if (tr > threshold) code |= 2;
			if (br > threshold) code |= 4;
			if (bl > threshold) code |= 8;
			if (code === 0 || code === 15) continue;
			const x0 = i * cellW, y0 = j * cellH;
			const it = x0 + cellW * (threshold - tl) / (tr - tl || 1e-9);
			const ir = y0 + cellH * (threshold - tr) / (br - tr || 1e-9);
			const ib = x0 + cellW * (threshold - bl) / (br - bl || 1e-9);
			const il = y0 + cellH * (threshold - tl) / (bl - tl || 1e-9);
			const T: [number, number] = [it, y0];
			const R: [number, number] = [x0 + cellW, ir];
			const B: [number, number] = [ib, y0 + cellH];
			const L: [number, number] = [x0, il];
			const push = (a: [number, number], b: [number, number]) => segs.push(a[0], a[1], b[0], b[1]);
			switch (code) {
				case 1: case 14: push(L, T); break;
				case 2: case 13: push(T, R); break;
				case 3: case 12: push(L, R); break;
				case 4: case 11: push(B, R); break;
				case 5: push(L, T); push(B, R); break;
				case 6: case 9: push(T, B); break;
				case 7: case 8: push(L, B); break;
				case 10: push(L, B); push(T, R); break;
			}
		}
	}
	return segs;
}

function segsToPath(segs: number[]): string {
	let d = '';
	for (let k = 0; k < segs.length; k += 4) {
		d += 'M' + segs[k].toFixed(1) + ' ' + segs[k + 1].toFixed(1) +
			'L' + segs[k + 2].toFixed(1) + ' ' + segs[k + 3].toFixed(1) + ' ';
	}
	return d;
}

export function createTopoField(opts: TopoFieldOptions): TopoFieldAPI {
	const host = opts.host;
	const W = opts.viewW, H = opts.viewH;
	const cell = opts.cellSize || 12;
	const cols = Math.ceil(W / cell) + 1;
	const rows = Math.ceil(H / cell) + 1;
	const levels = opts.levels || [0.30, 0.40, 0.50, 0.60, 0.70, 0.80];
	const restingOpacity = opts.restingOpacity == null ? 0.18 : opts.restingOpacity;
	const hoverRadius = opts.hoverRadius || Math.min(W, H) * 0.45;
	const bulgeStrength = opts.bulgeStrength == null ? 0.45 : opts.bulgeStrength;
	const seed = opts.seed == null ? Math.random() * 1000 : opts.seed;
	const freq = opts.freq || 0.006;
	const restingWidth = opts.restingWidth || 0.6;
	const glowWidth = opts.glowWidth || 0.9;
	const glowOpacity = opts.glowOpacity == null ? 0.9 : opts.glowOpacity;

	const NS = 'http://www.w3.org/2000/svg';
	const svg = document.createElementNS(NS, 'svg');
	svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
	svg.setAttribute('preserveAspectRatio', 'none');
	svg.style.position = 'absolute';
	svg.style.inset = '0';
	svg.style.width = '100%';
	svg.style.height = '100%';
	svg.style.pointerEvents = 'none';
	host.appendChild(svg);

	const defs = document.createElementNS(NS, 'defs');
	const maskId = 'restmask_' + Math.random().toString(36).slice(2, 9);
	const mask = document.createElementNS(NS, 'mask');
	mask.setAttribute('id', maskId);
	mask.setAttribute('maskUnits', 'userSpaceOnUse');
	const bgRect = document.createElementNS(NS, 'rect');
	bgRect.setAttribute('x', '0'); bgRect.setAttribute('y', '0');
	bgRect.setAttribute('width', String(W)); bgRect.setAttribute('height', String(H));
	bgRect.setAttribute('fill', 'white');
	mask.appendChild(bgRect);
	const gradId = 'restgrad_' + Math.random().toString(36).slice(2, 9);
	const grad = document.createElementNS(NS, 'radialGradient');
	grad.setAttribute('id', gradId);
	grad.setAttribute('gradientUnits', 'userSpaceOnUse');
	const s0 = document.createElementNS(NS, 'stop');
	s0.setAttribute('offset', '0%'); s0.setAttribute('stop-color', 'black'); s0.setAttribute('stop-opacity', '1');
	const s1 = document.createElementNS(NS, 'stop');
	s1.setAttribute('offset', '70%'); s1.setAttribute('stop-color', 'black'); s1.setAttribute('stop-opacity', '0.7');
	const s2 = document.createElementNS(NS, 'stop');
	s2.setAttribute('offset', '100%'); s2.setAttribute('stop-color', 'black'); s2.setAttribute('stop-opacity', '0');
	grad.appendChild(s0); grad.appendChild(s1); grad.appendChild(s2);
	defs.appendChild(grad);
	const maskDisc = document.createElementNS(NS, 'circle');
	maskDisc.setAttribute('cx', '-9999'); maskDisc.setAttribute('cy', '-9999');
	maskDisc.setAttribute('r', String(opts.hoverRadius || 100));
	maskDisc.setAttribute('fill', `url(#${gradId})`);
	mask.appendChild(maskDisc);
	defs.appendChild(mask);
	svg.appendChild(defs);

	const restGroup = document.createElementNS(NS, 'g');
	restGroup.setAttribute('mask', `url(#${maskId})`);
	svg.appendChild(restGroup);

	const restPaths: SVGPathElement[] = [], glowPaths: SVGPathElement[] = [];
	for (let k = 0; k < levels.length; k++) {
		const r = document.createElementNS(NS, 'path');
		r.setAttribute('fill', 'none');
		r.setAttribute('stroke', opts.color || 'rgba(180,200,220,1)');
		r.setAttribute('stroke-width', restingWidth.toString());
		r.setAttribute('opacity', restingOpacity.toString());
		restGroup.appendChild(r); restPaths.push(r);

		const g = document.createElementNS(NS, 'path');
		g.setAttribute('fill', 'none');
		g.setAttribute('stroke', opts.glowColor || 'oklch(0.80 0.18 160)');
		g.setAttribute('stroke-width', glowWidth.toString());
		g.setAttribute('opacity', '0');
		g.style.mixBlendMode = 'screen';
		g.style.transition = 'opacity 0.3s cubic-bezier(.22,1,.36,1)';
		svg.appendChild(g); glowPaths.push(g);
	}

	const restField = new Float32Array(cols * rows);
	for (let j = 0; j < rows; j++) {
		for (let i = 0; i < cols; i++) {
			const x = i * cell, y = j * cell;
			restField[j * cols + i] = fbm(x * freq, y * freq, seed);
		}
	}
	let mn = Infinity, mxv = -Infinity;
	for (let k = 0; k < restField.length; k++) { mn = Math.min(mn, restField[k]); mxv = Math.max(mxv, restField[k]); }
	for (let k = 0; k < restField.length; k++) { restField[k] = (restField[k] - mn) / (mxv - mn || 1); }

	for (let k = 0; k < levels.length; k++) {
		const segs = contours(restField, cols, rows, cell, cell, levels[k]);
		restPaths[k].setAttribute('d', segsToPath(segs));
	}

	let mx2 = -9999, my2 = -9999, tmx = mx2, tmy = my2, active = false;
	let raf: number | null = null;
	let currentGlow = opts.glowColor || 'oklch(0.80 0.18 160)';

	let trail: { x: number; y: number; life: number }[] = [];
	const trailDecay = opts.trailDecay == null ? 0.018 : opts.trailDecay;
	const trailRadius = opts.trailRadius || 44;
	const trailMax = opts.trailMax || 48;

	let sonars: { x: number; y: number; t: number }[] = [];
	const sonarSpeed = opts.sonarSpeed || 0.02;
	const sonarMaxR = opts.sonarMaxR || Math.max(W, H);
	const sonarRingW = opts.sonarRingW || 12;

	const dynField = new Float32Array(cols * rows);

	function frame(): void {
		tmx += (mx2 - tmx) * 0.55;
		tmy += (my2 - tmy) * 0.55;
		if (trail.length) {
			for (let t = 0; t < trail.length; t++) trail[t].life -= trailDecay;
			trail = trail.filter((p) => p.life > 0);
		}
		if (sonars.length) {
			for (let s = 0; s < sonars.length; s++) sonars[s].t += sonarSpeed;
			sonars = sonars.filter((s) => s.t < 1);
		}
		const hovering = active;
		const R = hoverRadius, R2 = R * R;
		const tr2 = trailRadius * trailRadius;
		for (let j = 0; j < rows; j++) {
			for (let i = 0; i < cols; i++) {
				const idx = j * cols + i;
				const cx = i * cell, cy = j * cell;
				let add = 0;
				if (hovering) {
					const dx = cx - tmx, dy = cy - tmy, d2 = dx * dx + dy * dy;
					if (d2 < R2) { const f = 1 - d2 / R2; add += f * f * bulgeStrength; }
				}
				for (let t = 0; t < trail.length; t++) {
					const p = trail[t];
					const dx = cx - p.x, dy = cy - p.y, d2 = dx * dx + dy * dy;
					if (d2 < tr2) { const f = 1 - d2 / tr2; add += f * f * bulgeStrength * 1.25 * p.life; }
				}
				for (let s = 0; s < sonars.length; s++) {
					const so = sonars[s];
					const r = so.t * sonarMaxR;
					const dx = cx - so.x, dy = cy - so.y;
					const dist = Math.sqrt(dx * dx + dy * dy);
					const rd = Math.abs(dist - r);
					if (rd < sonarRingW) { const f = 1 - rd / sonarRingW; add += f * f * bulgeStrength * 1.5 * Math.sin(Math.PI * so.t); }
				}
				dynField[idx] = add > 0 ? restField[idx] + add : restField[idx];
			}
		}
		for (let k = 0; k < levels.length; k++) {
			const segs = contours(dynField, cols, rows, cell, cell, levels[k]);
			glowPaths[k].setAttribute('d', segsToPath(segs));
			glowPaths[k].setAttribute('stroke', currentGlow);
		}
		const head = trail.length ? trail[trail.length - 1] : { x: tmx, y: tmy };
		const focusR = trail.length ? trailRadius * 1.6 : hoverRadius;
		maskDisc.setAttribute('cx', String(head.x));
		maskDisc.setAttribute('cy', String(head.y));
		grad.setAttribute('cx', String(head.x));
		grad.setAttribute('cy', String(head.y));
		grad.setAttribute('r', String(focusR));
		grad.setAttribute('fx', String(head.x));
		grad.setAttribute('fy', String(head.y));
		if (hovering || trail.length || sonars.length || Math.abs(mx2 - tmx) > 0.5 || Math.abs(my2 - tmy) > 0.5) {
			raf = requestAnimationFrame(frame);
		} else {
			raf = null;
			for (const g of glowPaths) g.setAttribute('opacity', '0');
		}
	}

	return {
		setHover(x: number, y: number, color?: string): void {
			mx2 = x; my2 = y;
			if (color) currentGlow = color;
			for (const g of glowPaths) g.setAttribute('opacity', String(glowOpacity));
			if (!raf) { active = true; frame(); }
		},
		endHover(): void {
			mx2 = -9999; my2 = -9999;
			active = false;
			if (!trail.length) for (const g of glowPaths) g.setAttribute('opacity', '0');
		},
		pushTrail(x: number, y: number, color?: string): void {
			if (color) currentGlow = color;
			trail.push({ x, y, life: 1 });
			if (trail.length > trailMax) trail.shift();
			for (const g of glowPaths) g.setAttribute('opacity', String(glowOpacity));
			if (!raf) { raf = requestAnimationFrame(frame); }
		},
		sonarPing(x: number, y: number, color?: string): void {
			if (color) currentGlow = color;
			sonars.push({ x, y, t: 0.001 });
			for (const g of glowPaths) g.setAttribute('opacity', String(glowOpacity));
			if (!raf) { raf = requestAnimationFrame(frame); }
		},
		clearTrail(): void { trail.length = 0; sonars.length = 0; },
		destroy(): void {
			if (raf) cancelAnimationFrame(raf);
			raf = null;
			if (svg.parentNode === host) host.removeChild(svg);
		}
	};
}
