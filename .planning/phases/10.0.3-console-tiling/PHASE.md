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
