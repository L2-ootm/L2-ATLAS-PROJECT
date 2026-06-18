/* clickSpark — Svelte action. A brief radial spark burst at the click point.
   Diegetic: confirmation of a committed action (create, run, cancel). Honors
   prefers-reduced-motion (no-op). Ported from react-bits/ClickSpark to vanilla
   canvas so it works on any element without React. */

interface ClickSparkOptions {
	color?: string;
	count?: number;
	radius?: number;
	duration?: number;
}

function spawn(cx: number, cy: number, color: string, count: number, radius: number, duration: number): void {
	const canvas = document.createElement('canvas');
	const size = (radius + 12) * 2;
	const dpr = Math.min(window.devicePixelRatio || 1, 2);
	canvas.width = size * dpr;
	canvas.height = size * dpr;
	canvas.style.cssText =
		`position:fixed;left:${cx - size / 2}px;top:${cy - size / 2}px;width:${size}px;height:${size}px;` +
		'pointer-events:none;z-index:9999;';
	document.body.appendChild(canvas);
	const ctx = canvas.getContext('2d');
	if (!ctx) { canvas.remove(); return; }
	ctx.scale(dpr, dpr);

	const c = size / 2;
	const sparks = Array.from({ length: count }, (_, i) => ({
		angle: (Math.PI * 2 * i) / count + Math.random() * 0.3
	}));
	const start = performance.now();
	const ease = (t: number) => 1 - Math.pow(1 - t, 3);

	function frame(now: number): void {
		const t = Math.min((now - start) / duration, 1);
		const e = ease(t);
		ctx!.clearRect(0, 0, size, size);
		ctx!.lineCap = 'round';
		ctx!.strokeStyle = color;
		ctx!.globalAlpha = 1 - t;
		ctx!.lineWidth = 2;
		for (const s of sparks) {
			const r0 = e * radius;
			const r1 = r0 + 8 * (1 - e);
			ctx!.beginPath();
			ctx!.moveTo(c + Math.cos(s.angle) * r0, c + Math.sin(s.angle) * r0);
			ctx!.lineTo(c + Math.cos(s.angle) * r1, c + Math.sin(s.angle) * r1);
			ctx!.stroke();
		}
		if (t < 1) requestAnimationFrame(frame);
		else canvas.remove();
	}
	requestAnimationFrame(frame);
}

export function clickSpark(node: HTMLElement, options: ClickSparkOptions = {}) {
	let opts = options;
	function onClick(e: MouseEvent): void {
		if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		// canvas needs a concrete colour (hex/rgb), not a CSS var.
		spawn(e.clientX, e.clientY, opts.color ?? '#00F0FF', opts.count ?? 9, opts.radius ?? 18, opts.duration ?? 420);
	}
	node.addEventListener('click', onClick);
	return {
		update(next: ClickSparkOptions) { opts = next; },
		destroy() { node.removeEventListener('click', onClick); }
	};
}
