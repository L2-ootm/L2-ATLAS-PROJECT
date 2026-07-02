import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

// Fonts are loaded once via tokens.css @import (self-hosted, WebView2-safe).
import './app.css';
import App from './App';
import { initScrollEdgePulse } from './lib/scrollEdgePulse';

// Global cosmetic: pulse the new-mission tones when a scroll area hits its limit.
initScrollEdgePulse();

createRoot(document.getElementById('root')!).render(
	<StrictMode>
		<App />
	</StrictMode>
);
