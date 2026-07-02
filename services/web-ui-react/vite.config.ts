import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Static SPA — WebView2-safe for the Tauri native shell (no SSR, no Node APIs
// at runtime). The gateway serves `dist/` and falls back to index.html for
// client-side routes.
export default defineConfig({
	plugins: [react(), tailwindcss()],
	// Pre-bundle the heavy 3D graph stack up front. Without this, Vite discovers
	// them lazily on first /graph visit and re-optimizes mid-session, which
	// invalidates the in-flight dynamic import ("Failed to fetch dynamically
	// imported module: Graph.tsx").
	optimizeDeps: {
		include: ['3d-force-graph', 'three', 'three-spritetext']
	},
	build: {
		outDir: 'dist',
		target: 'es2022',
		sourcemap: true
	},
	server: { port: 5174 }
});
