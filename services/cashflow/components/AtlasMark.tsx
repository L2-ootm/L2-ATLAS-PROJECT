// ATLAS celestial mark — "the titan bears the heavens".
// Ported from the ATLAS cockpit (services/web-ui-react/src/brand/AtlasMark.tsx)
// so the cashflow surface carries the same brand fragment. Uses the same
// --atlas-* tokens defined in app/globals.css.

interface AtlasMarkProps {
    size?: number;
    title?: string;
}

export default function AtlasMark({ size = 32, title = "ATLAS" }: AtlasMarkProps) {
    const globe = "var(--atlas-celestial)";
    const lines = "var(--atlas-mythic)";
    const bronze = "var(--atlas-bronze)";
    const node = "var(--atlas-cyan)";

    const cx = 32;
    const cy = 27;
    const r = 16;

    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 64 64"
            fill="none"
            role="img"
            aria-label={title}
            style={{ display: "block", overflow: "visible" }}
        >
            <title>{title}</title>

            {/* Celestial globe — graticule */}
            <circle cx={cx} cy={cy} r={r} stroke={globe} strokeWidth="1.4" />
            <g stroke={lines} strokeWidth="0.85" opacity="0.92">
                <ellipse cx={cx} cy={cy} rx={r} ry={r * 0.34} />
                <ellipse cx={cx} cy={cy} rx={r * 0.82} ry={r * 0.66} />
                <ellipse cx={cx} cy={cy} rx={r * 0.34} ry={r} />
                <ellipse cx={cx} cy={cy} rx={r * 0.66} ry={r} />
            </g>

            {/* Tilted orbit ring crossing the sphere */}
            <g transform={`rotate(-24 ${cx} ${cy})`}>
                <ellipse cx={cx} cy={cy} rx={r + 4.5} ry={r * 0.32} stroke={globe} strokeWidth="1" opacity="0.8" />
            </g>

            {/* Constellation nodes (stars) */}
            <g fill={node}>
                <circle cx={cx} cy={cy - r} r="1.25" />
                <circle cx={cx + r * 0.7} cy={cy - r * 0.5} r="1" />
                <circle cx={cx - r * 0.78} cy={cy + r * 0.36} r="1" />
                <circle cx={cx + r * 0.5} cy={cy + r * 0.62} r="0.9" />
            </g>

            {/* Central compass-star */}
            <g stroke={bronze} strokeWidth="1" strokeLinecap="round">
                <path d={`M${cx} ${cy - 4} L${cx} ${cy + 4} M${cx - 4} ${cy} L${cx + 4} ${cy}`} />
                <path
                    d={`M${cx - 2.4} ${cy - 2.4} L${cx + 2.4} ${cy + 2.4} M${cx + 2.4} ${cy - 2.4} L${cx - 2.4} ${cy + 2.4}`}
                    strokeWidth="0.6"
                    opacity="0.7"
                />
            </g>
            <circle cx={cx} cy={cy} r="1.3" fill={bronze} />

            {/* Bronze bearer cradle — the titan takes the load */}
            <g stroke={bronze} strokeLinecap="round" fill="none">
                <path d={`M14 ${cy + r - 1} Q32 ${cy + r + 12} 50 ${cy + r - 1}`} strokeWidth="2" />
                <path d={`M19 ${cy + r + 2.5} L24 ${cy + r - 3} M45 ${cy + r + 2.5} L40 ${cy + r - 3}`} strokeWidth="1.6" opacity="0.85" />
            </g>
        </svg>
    );
}
