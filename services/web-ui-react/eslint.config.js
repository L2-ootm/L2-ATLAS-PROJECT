import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

export default tseslint.config(
	{ ignores: ['dist', 'node_modules'] },
	{
		files: ['**/*.{ts,tsx}'],
		extends: [js.configs.recommended, ...tseslint.configs.recommended],
		languageOptions: {
			ecmaVersion: 2022,
			globals: globals.browser
		},
		plugins: {
			'react-hooks': reactHooks,
			'react-refresh': reactRefresh
		},
		rules: {
			'react-hooks/rules-of-hooks': 'error',
			'react-hooks/exhaustive-deps': 'warn',
			'react-refresh/only-export-components': ['warn', { allowConstantExport: true }]
		}
	},
	{
		files: [
			'src/context/AgentSurfaceContext.ts',
			'src/context/ConsoleSessionContext.ts'
		],
		rules: {
			'react-refresh/only-export-components': 'off'
		}
	},
	// topoEngine is a verbatim framework-agnostic port; allow its terser idioms.
	{
		files: ['src/topo/topoEngine.ts'],
		rules: {
			'@typescript-eslint/no-explicit-any': 'off'
		}
	}
);
