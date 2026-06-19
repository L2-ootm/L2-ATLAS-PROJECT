import { useEffect, useId, useRef } from 'react';
import type { CSSProperties } from 'react';
import { createTopoField, type TopoFieldAPI } from '../topo/topoEngine';

// TopoInput — an input whose own topographic field reacts to authorship.
// L2 Law 2: "typing = authorship — the caret drags a comet of glow behind the
// letters." Each keystroke pushes a decaying source at the caret (brightest at the
// newest letter). Cools to rest on blur; the rAF stops itself when idle. The canvas
// is decorative + aria-hidden; the real <input>/<textarea> carries all semantics.

type Tone = 'info' | 'ai' | 'good' | 'bad';
const GLOW: Record<Tone, string> = {
	info: 'rgba(79,139,255,0.85)', // celestial — search / neutral authorship
	ai: 'rgba(161,123,255,0.85)', // violet — AI-bound fields (intent, ⌘K)
	good: 'rgba(70,240,224,0.85)', // valid
	bad: 'rgba(255,77,125,0.90)' // error
};

// Mirror-div caret measurement. canvas measureText only knows a single run of
// text, so it can't see soft wraps — the trail stalled on line 1 once a line
// wrapped. A hidden div that mirrors the control's box + type styles wraps
// identically; a marker span at the caret gives an accurate (x, y).
const MIRROR_PROPS = [
	'box-sizing', 'width', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
	'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
	'font-family', 'font-size', 'font-weight', 'font-style', 'font-variant', 'letter-spacing',
	'line-height', 'text-transform', 'text-indent', 'word-spacing', 'tab-size'
];

function caretXY(
	el: HTMLInputElement | HTMLTextAreaElement,
	caret: number,
	multiline: boolean
): { x: number; y: number } {
	const cs = getComputedStyle(el);
	const div = document.createElement('div');
	const s = div.style;
	s.position = 'absolute';
	s.top = '-9999px';
	s.left = '-9999px';
	s.visibility = 'hidden';
	s.whiteSpace = multiline ? 'pre-wrap' : 'pre';
	s.overflowWrap = 'break-word';
	for (const p of MIRROR_PROPS) s.setProperty(p, cs.getPropertyValue(p));
	if (!multiline) s.width = 'auto';

	div.textContent = el.value.slice(0, caret);
	const marker = document.createElement('span');
	marker.textContent = el.value.slice(caret) || '.';
	div.appendChild(marker);

	document.body.appendChild(div);
	const x = marker.offsetLeft - el.scrollLeft;
	const y = marker.offsetTop - el.scrollTop;
	document.body.removeChild(div);
	return { x, y };
}

interface TopoInputProps {
	value: string;
	onChange: (v: string) => void;
	placeholder?: string;
	tone?: Tone;
	multiline?: boolean;
	rows?: number;
	icon?: React.ReactNode;
	onSubmit?: () => void;
	ariaLabel?: string;
	autoFocus?: boolean;
	/** Clean mode: no per-field topo, solid background. For modals/dialogs. */
	quiet?: boolean;
	style?: CSSProperties;
}

export default function TopoInput({
	value,
	onChange,
	placeholder,
	tone = 'info',
	multiline = false,
	rows = 4,
	icon,
	onSubmit,
	ariaLabel,
	autoFocus,
	quiet = false,
	style
}: TopoInputProps) {
	const hostRef = useRef<HTMLDivElement>(null);
	const fieldRef = useRef<TopoFieldAPI | null>(null);
	const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
	const id = useId();

	// Build a per-field topo behind the control, sized to the host.
	useEffect(() => {
		const host = hostRef.current;
		if (!host) return;
		if (quiet) return; // clean mode — no per-field topo (modals)
		if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

		const build = () => {
			fieldRef.current?.destroy();
			const W = host.clientWidth || 320;
			const H = host.clientHeight || 44;
			fieldRef.current = createTopoField({
				host,
				viewW: W,
				viewH: H,
				cellSize: 13,
				color: 'rgba(150,170,210,1)',
				glowColor: GLOW[tone],
				restingOpacity: 0.07,
				glowOpacity: 0.5,
				restingWidth: 0.6,
				glowWidth: 1.15,
				bulgeStrength: 0.5,
				hoverRadius: Math.min(W, H) * 1.1,
				freq: 0.02
			});
		};
		build();
		const ro = new ResizeObserver(build);
		ro.observe(host);
		return () => {
			ro.disconnect();
			fieldRef.current?.destroy();
			fieldRef.current = null;
		};
	}, [tone, quiet]);

	// Caret → field coordinates (accounting for the control's offset within the
	// host and soft-wrapped lines), then push a glow source there.
	const ping = () => {
		const el = inputRef.current;
		const field = fieldRef.current;
		const host = hostRef.current;
		if (!el || !field || !host) return;
		const caret = el.selectionStart ?? value.length;
		const { x, y } = caretXY(el, caret, multiline);
		const px = Math.max(2, Math.min(host.clientWidth - 2, el.offsetLeft + x));
		const py = multiline
			? Math.max(2, Math.min(host.clientHeight - 2, el.offsetTop + y))
			: host.clientHeight / 2;
		field.pushTrail(px, py, GLOW[tone]);
	};

	const shared = {
		ref: inputRef as never,
		id,
		value,
		'aria-label': ariaLabel ?? placeholder,
		placeholder,
		autoFocus,
		onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
			onChange(e.target.value);
			ping();
		},
		onKeyDown: (e: React.KeyboardEvent) => {
			if (!multiline && e.key === 'Enter' && onSubmit) onSubmit();
		},
		style: {
			position: 'relative' as const,
			zIndex: 1,
			width: '100%',
			background: 'transparent',
			border: 'none',
			outline: 'none',
			color: 'var(--l2-fg-1)',
			fontFamily: 'var(--l2-font-sans)',
			fontSize: 14,
			lineHeight: 1.5,
			padding: multiline ? '12px 14px' : '0 14px',
			resize: 'none' as const
		}
	};

	return (
		<div
			data-topo="atlas"
			style={{
				position: 'relative',
				display: 'flex',
				alignItems: multiline ? 'stretch' : 'center',
				gap: 10,
				minHeight: multiline ? undefined : 44,
				borderRadius: 2,
				border: '1px solid var(--l2-hairline)',
				background: quiet
					? 'rgba(15,18,25,1)'
					: 'linear-gradient(180deg, rgba(21,24,32,0.66), rgba(11,13,18,0.66))',
				backdropFilter: quiet ? undefined : 'blur(10px) saturate(1.2)',
				overflow: 'hidden',
				...style
			}}
		>
			{/* topo field host — behind the control */}
			<div ref={hostRef} aria-hidden="true" style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} />
			{icon && !multiline && (
				<span style={{ position: 'relative', zIndex: 1, display: 'flex', paddingLeft: 12, color: 'var(--l2-fg-3)' }}>
					{icon}
				</span>
			)}
			{multiline ? (
				<textarea {...shared} rows={rows} />
			) : (
				<input {...shared} type="text" />
			)}
		</div>
	);
}
