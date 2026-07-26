'use strict';

/**
 * Guards the release payload declaration.
 *
 * History this protects against: the payload was a hardcoded list duplicated in
 * all three platform build scripts, kept consistent by hand. Anything omitted
 * silently never shipped, and no test noticed. That is how services/cashflow,
 * services/discord-bot, services/atlas-terminal and docs/imports/SKILL_INVENTORY.md
 * became unreachable in release installs while runtime code kept resolving paths
 * into the bundle expecting them.
 */

const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const {
	readPayloadManifest,
	defaultManifestPath
} = require('../../../scripts/ci/payload-manifest');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const MANIFEST = defaultManifestPath(REPO_ROOT);

const BUILD_SCRIPTS = [
	'scripts/ci/build-windows-runtime.ps1',
	'scripts/ci/build-linux-runtime.sh',
	'scripts/ci/build-darwin-runtime.sh'
];

/**
 * Trees that runtime code resolves relative to the bundle root. If any of these
 * stops shipping, the corresponding surface breaks only in release installs —
 * never in a developer checkout — which is the hardest class of bug to notice.
 */
const BUNDLE_RESOLVED_REQUIREMENTS = [
	// db.py:25 -> <bundle>/infra/migrations
	'infra/migrations',
	// module_service.py:106 -> <bundle>/modules
	'modules',
	// cashflow_control.py:20 -> <bundle>/services/cashflow
	'services/cashflow',
	// discord_control.py:27 -> <bundle>/services/discord-bot
	'services/discord-bot',
	// cli/atlas_terminal.py resolve_terminal_dir() -> <bundle>/services/atlas-terminal
	'services/atlas-terminal',
	// memory_router.py:632 -> <bundle>/docs/imports/SKILL_INVENTORY.md
	'docs/imports/SKILL_INVENTORY.md'
];

function trackedFiles(pathspec) {
	const out = execFileSync('git', ['ls-files', '-z', '--', pathspec], {
		cwd: REPO_ROOT,
		encoding: 'utf8',
		maxBuffer: 64 * 1024 * 1024
	});
	return out.split('\0').filter(Boolean);
}

test('payload manifest parses and declares entries', () => {
	const entries = readPayloadManifest(MANIFEST);
	assert.ok(entries.length > 0, 'expected at least one payload entry');
	for (const entry of entries) {
		assert.ok(
			entry.mode === 'tracked' || entry.mode === 'tree',
			`unexpected mode ${entry.mode}`
		);
		assert.ok(entry.pathspec.length > 0, 'empty pathspec');
	}
});

test('every tracked pathspec resolves to at least one git-tracked file', () => {
	const entries = readPayloadManifest(MANIFEST);
	const unresolved = [];
	for (const entry of entries) {
		if (entry.mode !== 'tracked') continue;
		if (trackedFiles(entry.pathspec).length === 0) {
			unresolved.push(`${entry.pathspec} (line ${entry.line})`);
		}
	}
	assert.deepEqual(
		unresolved,
		[],
		`payload pathspecs match no tracked files — a rename would silently drop ` +
			`them from every release: ${unresolved.join(', ')}`
	);
});

test('tracked payload carries no dependency trees or build output', () => {
	const entries = readPayloadManifest(MANIFEST);
	const forbidden = /(^|\/)(node_modules|\.next|__pycache__|\.venv)(\/|$)/;
	const offenders = [];
	for (const entry of entries) {
		if (entry.mode !== 'tracked') continue;
		for (const file of trackedFiles(entry.pathspec)) {
			if (forbidden.test(file)) offenders.push(file);
		}
	}
	assert.deepEqual(
		offenders,
		[],
		`payload would ship regenerable artifacts: ${offenders.slice(0, 10).join(', ')}`
	);
});

test('trees that runtime code resolves inside the bundle are all shipped', () => {
	const entries = readPayloadManifest(MANIFEST);
	const declared = new Set(entries.map((entry) => entry.pathspec));
	const missing = BUNDLE_RESOLVED_REQUIREMENTS.filter((req) => !declared.has(req));
	assert.deepEqual(
		missing,
		[],
		`runtime code resolves these under the bundle root but they are not in the ` +
			`payload, so the feature works in a checkout and breaks in a release: ${missing.join(', ')}`
	);
});

test('all three platform builders consume the manifest', () => {
	for (const relative of BUILD_SCRIPTS) {
		const text = fs.readFileSync(path.join(REPO_ROOT, relative), 'utf8');
		assert.match(
			text,
			/infra[\\/]release[\\/]payload\.manifest/,
			`${relative} does not reference the payload manifest`
		);
	}
});

test('no platform builder carries its own hardcoded payload list', () => {
	// Sentinels chosen because they only ever appeared as payload entries — unlike
	// e.g. services/web-ui-react/dist, which the builders legitimately still name
	// in their required-build-output guards.
	const PAYLOAD_ONLY_SENTINELS = [
		'foundation/atlas-hermes/tui_gateway',
		'foundation/atlas-hermes/acp_registry',
		'services/wiki-runtime/atlas_wiki'
	];
	const offenders = [];
	for (const relative of BUILD_SCRIPTS) {
		const text = fs.readFileSync(path.join(REPO_ROOT, relative), 'utf8');
		if (/\$runtimeTrees\s*=\s*@\(/.test(text)) {
			offenders.push(`${relative}: $runtimeTrees array`);
		}
		for (const sentinel of PAYLOAD_ONLY_SENTINELS) {
			// Match the path in either slash style, but only when quoted as an
			// argument — comments referring to the manifest are fine.
			const pattern = new RegExp(`["']${sentinel.replace(/\//g, '[\\\\/]')}["']`);
			if (pattern.test(text)) {
				offenders.push(`${relative}: inline payload path ${sentinel}`);
			}
		}
	}
	assert.deepEqual(
		offenders,
		[],
		`payload list resurrected inside a build script: ${offenders.join(', ')}`
	);
});
