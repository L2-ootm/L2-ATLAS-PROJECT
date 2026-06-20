# 10.0.3 — Console Hyprland-style BSP Auto-Tiling

> Status: **planned** (in-flight; sequence item #4). Independent UI work.
> Owner concern: `services/web-ui-react` Console only. No backend, no gateway, no foundation.

## Intent

The `/console` workbench already supports three layout modes — exclusive tabs, manual free-drag, and a
simple tile reorder. The one outstanding UI ask is **hyprland-style binary-space-partition (BSP)
auto-tiling**: opening a window splits the focused region; closing one reflows the remaining windows to
fill the space; no manual placement. This is the dwindle/BSP behavior operators expect from a tiling WM.

## Scope

**In scope:**
- A `useBspLayout` hook (or reducer) maintaining a BSP tree of console windows: each leaf = a window,
  each internal node = a split (direction + ratio).
- Insertion: a new window splits the **focused** leaf; split direction chosen by the leaf's aspect ratio
  (wider → vertical split, taller → horizontal split), hyprland "dwindle"-style.
- Removal: closing a leaf collapses its parent split, sibling expands to fill.
- Resize: dragging a split boundary adjusts the node ratio; clamp to a min window size.
- Compute pixel rects from the tree + container size; windows render absolutely positioned from rects.
- A layout-mode entry "BSP / auto-tile" alongside the existing tabs/free/tile modes; free mode preserved.

**Out of scope:**
- Keyboard-driven window navigation/movement (nice-to-have; can follow).
- Persisting layout across reloads, multi-monitor concepts.

## Approach

1. Model the BSP tree as a pure data structure with unit-tested operations (insert at focus, remove leaf,
   resize split, compute rects). Keep it framework-agnostic so it is testable.
2. Hook the existing Console window registry into the tree; map window ids to leaves.
3. Render windows from computed rects; wire split-boundary drag handles to the resize op.
4. Add the BSP option to the layout-mode switch.

## Acceptance

- Opening N windows in BSP mode auto-tiles them with no overlap and no gaps; closing any window reflows
  the rest to fill; split boundaries are draggable with a min-size clamp.
- Existing tabs/free/tile modes still work; switching to/from BSP is non-destructive.
- `npm run check/lint/build` green; Playwright shot of a 3–4 window BSP layout + a post-close reflow.

## Notes
- Pure-data BSP core first (unit-testable), UI second — keeps the trickiest logic out of React.
- Reference behavior: hyprland `dwindle` layout (aspect-driven split direction).

## Delivered (2026-06-20)

- `src/lib/bspLayout.ts` — pure, framework-agnostic `computeDwindle(ids, container, gap, focusId)`:
  aspect-driven recursive split (first window takes half, rest recurse the other half), focus takes the
  largest cell, min-edge clamp, no overlap/gaps. This is the dwindle behavior as pure geometry.
- Console: new `bsp` LayoutMode wired into the toolbar cycle (tile→bsp→free→tabs), the segment switch,
  and the status badge. BSP windows are absolutely positioned from computed rects via a ResizeObserver on
  the canvas, so opening a window splits the space and closing one reflows the rest (the rect set derives
  from the live window list). Existing tile/free/tabs modes untouched.
- Verified: `npm run check`/`lint`/`build` green (0 errors; pre-existing exhaustive-deps warning only).

**Deferred:** draggable split-boundary manual resize (the dwindle auto-layout uses fixed 0.5 splits);
keyboard window navigation; layout persistence. A JS unit-test runner (vitest) is not configured in this
app, so `bspLayout.ts` is verified by tsc/build + (pending) Playwright visual check rather than unit tests.
