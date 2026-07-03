"use client";

import { useEffect, useRef } from "react";
import { createTopoField, type TopoFieldAPI } from "@/lib/topoEngine";

// Ambient topographic background — the "living terrain" beneath the cashflow
// surface. Ported from the ATLAS cockpit (services/web-ui-react TopoField) so
// both surfaces share one terrain grammar: faint at rest; bulges + glows by
// the SEMANTIC context of whatever the cursor touches (elements tag themselves
// with data-topo="brand|info|good|warn|bad|atlas"); drifts in parallax on
// scroll; clicks on interactive topo-tagged elements emit a sonar ping
// ("this entered the system"). Recedes behind content.

// Bright glow inks (mix-blend screen) keyed by semantic context — identical
// to the cockpit's so the two surfaces read as one system.
const GLOW: Record<string, string> = {
    brand: "var(--atlas-violet)",
    info: "var(--atlas-celestial)",
    good: "var(--atlas-cyan)",
    warn: "var(--sig-amber)",
    bad: "var(--sig-crimson)",
    atlas: "var(--atlas-bronze)",
};

function semanticAt(x: number, y: number): string {
    const el = document.elementFromPoint(x, y) as HTMLElement | null;
    const tagged = el?.closest<HTMLElement>("[data-topo]");
    if (tagged) return GLOW[tagged.dataset.topo || "atlas"] || GLOW.atlas;
    // Untagged interactive elements still read as live signals (info);
    // everything else rests on the atlas bronze ambient.
    const interactive = el?.closest("button, a, [role='button'], input, select, textarea, label");
    return interactive ? GLOW.info : GLOW.atlas;
}

export default function TopoField() {
    const hostRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const host = hostRef.current;
        if (!host) return;

        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        let field: TopoFieldAPI | null = null;
        let raf = 0;

        function build() {
            field?.destroy();
            const W = window.innerWidth;
            const H = window.innerHeight;
            field = createTopoField({
                host: host!,
                viewW: W,
                viewH: H,
                cellSize: 18,
                color: "var(--topo-resting-line)",
                glowColor: GLOW.atlas,
                restingOpacity: 0.1,
                glowOpacity: 0.32, // ambient — recedes behind content
                restingWidth: 0.7,
                glowWidth: 1.0,
                bulgeStrength: 0.42,
                hoverRadius: Math.min(W, H) * 0.32,
                freq: 0.005,
            });
        }

        build();

        let px = -9999,
            py = -9999,
            queued = false;
        function onMove(e: PointerEvent) {
            px = e.clientX;
            py = e.clientY;
            if (queued || reduce || !field) return;
            queued = true;
            raf = requestAnimationFrame(() => {
                queued = false;
                field?.setHover(px, py, semanticAt(px, py));
            });
        }
        function onLeave() {
            field?.endHover();
        }

        // Submit shockwave: a click on an interactive, semantically-tagged
        // element radiates one sonar ring — "a thing happened".
        function onClick(e: MouseEvent) {
            const el = e.target as HTMLElement | null;
            const interactive = el?.closest<HTMLElement>("button, a, [role='button']");
            if (!interactive || !interactive.closest("[data-topo]")) return;
            field?.sonarPing(e.clientX, e.clientY, semanticAt(e.clientX, e.clientY));
        }

        // Parallax drift: the terrain is never frozen; it eases under scroll.
        function onScroll() {
            const drift = -(window.scrollY % window.innerHeight) * 0.06;
            host!.style.transform = `translate3d(0, ${drift}px, 0)`;
            if (px !== -9999 && py !== -9999) {
                field?.setHover(px, py, semanticAt(px, py));
            }
        }

        let rt = 0;
        function onResize() {
            clearTimeout(rt);
            rt = window.setTimeout(build, 200) as unknown as number;
        }

        if (!reduce) {
            window.addEventListener("pointermove", onMove, { passive: true });
            window.addEventListener("pointerleave", onLeave, { passive: true });
            window.addEventListener("scroll", onScroll, { passive: true });
            window.addEventListener("click", onClick, { passive: true });
        }
        window.addEventListener("resize", onResize);

        return () => {
            cancelAnimationFrame(raf);
            clearTimeout(rt);
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerleave", onLeave);
            window.removeEventListener("scroll", onScroll);
            window.removeEventListener("click", onClick);
            window.removeEventListener("resize", onResize);
            field?.destroy();
        };
    }, []);

    return (
        <div
            ref={hostRef}
            className="ambient-topo"
            aria-hidden="true"
            style={{
                position: "fixed",
                inset: "-10vh 0 0 0",
                height: "120vh",
                zIndex: 0,
                pointerEvents: "none",
                opacity: 0.5,
                willChange: "transform",
            }}
        />
    );
}
