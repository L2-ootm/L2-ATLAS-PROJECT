# ULTRAREVIEW — Graph Chunk and Slash Dropdown

## Root cause: stale lazy-route hash resolves to HTML

**Failure point:** `services/web-ui-react/src/App.tsx:21`

`Graph` was loaded with an unguarded `lazy(() => import('./routes/Graph'))`. After a production rebuild, an already-open main bundle still requested its old `Graph-*.js` hash. Direct inspection of the reported URL returned `200`, but with `Content-Type: text/html` and the body beginning with `<!doctype html>`: the SPA fallback substituted `index.html` for the missing module. The browser rejected it and React Router had no project error element, so its default developer screen replaced the cockpit.

## Root cause: completion list was clipped into the composer

**Failure point:** `services/web-ui-react/src/components/chat/QueuedChatComposer.tsx` and `src/app.css`

The slash list was rendered inside `.chat-composer-shell`, whose `overflow: hidden` is required by the scan/focus effects. Its `bottom: 44px` position therefore overlaid the textarea inside the composer instead of opening above it. Moving the list beside the shell gives it an unclipped positioning context and preserves the shell effects.

## Remediation

- Guard all lazy cockpit routes with one-time chunk recovery and a reload-loop marker.
- Install an ATLAS route error surface for persistent failures.
- Anchor the slash index above the composer region with an upward reveal.
- Cover stale-chunk matching, one-time recovery, and loop prevention with tests.
