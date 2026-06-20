import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider, createBrowserRouter } from 'react-router-dom';

// Fonts are loaded once via tokens.css @import (self-hosted, WebView2-safe).
import './app.css';
import { routes } from './App';
import { initScrollEdgePulse } from './lib/scrollEdgePulse';

const router = createBrowserRouter(routes);

// Global cosmetic: pulse the new-mission tones when a scroll area hits its limit.
initScrollEdgePulse();

createRoot(document.getElementById('root')!).render(
	<StrictMode>
		<RouterProvider router={router} />
	</StrictMode>
);
