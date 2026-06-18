import type { CSSProperties, ReactNode } from 'react';

// GlowBorder — an electric conic border that reads as "this is live". A rotating
// conic gradient is masked to the border ring only (gradient-border trick) and
// driven by the --atlas-glow-angle @property (app.css). When inactive it collapses
// to a static hairline so nothing stays lit without cause (UX-VISUAL-SPEC Law 5).

interface GlowBorderProps {
	active: boolean;
	children?: ReactNode;
	/** ring color while active */
	color?: string;
	radius?: number;
	style?: CSSProperties;
}

export default function GlowBorder({
	active,
	children,
	color = 'var(--atlas-celestial)',
	radius = 2,
	style
}: GlowBorderProps) {
	return (
		<div style={{ position: 'relative', borderRadius: radius, ...style }}>
			{active && (
				<span
					aria-hidden="true"
					style={{
						position: 'absolute',
						inset: 0,
						borderRadius: radius,
						padding: 1,
						background: `conic-gradient(from var(--atlas-glow-angle), transparent 0%, ${color} 18%, transparent 38%, transparent 62%, ${color} 82%, transparent 100%)`,
						animation: 'atlas-glow-spin 3.6s linear infinite',
						WebkitMask: 'linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)',
						WebkitMaskComposite: 'xor',
						maskComposite: 'exclude',
						pointerEvents: 'none'
					}}
				/>
			)}
			{!active && (
				<span
					aria-hidden="true"
					style={{
						position: 'absolute',
						inset: 0,
						borderRadius: radius,
						border: '1px solid var(--l2-hairline)',
						pointerEvents: 'none'
					}}
				/>
			)}
			{children}
		</div>
	);
}
