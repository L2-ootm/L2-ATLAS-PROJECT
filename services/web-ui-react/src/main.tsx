import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider, createBrowserRouter } from 'react-router-dom';

// Fonts are loaded once via tokens.css @import (self-hosted, WebView2-safe).
import './app.css';
import { routes } from './App';

const router = createBrowserRouter(routes);

createRoot(document.getElementById('root')!).render(
	<StrictMode>
		<RouterProvider router={router} />
	</StrictMode>
);
