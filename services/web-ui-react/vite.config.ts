import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Static SPA — WebView2-safe for the Tauri native shell (no SSR, no Node APIs
// at runtime). Mirrors the Svelte cockpit's adapter-static posture. The gateway
// serves `dist/` and falls back to index.html for client-side routes.
export default defineConfig({
	plugins: [react(), tailwindcss()],
	build: {
		outDir: 'dist',
		target: 'es2022',
		sourcemap: true
	},
	server: { port: 5174 }
});
