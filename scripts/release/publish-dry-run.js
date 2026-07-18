#!/usr/bin/env node
'use strict';

/**
 * ATLAS npm Publish Dry-Run
 *
 * Validates everything is ready to publish without actually publishing.
 * Works on Windows, macOS, and Linux.
 *
 * Usage:
 *   node scripts/release/publish-dry-run.js [--version 0.1.2] [--allow-dirty] [--skip-python]
 */

const { execSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const repo = path.resolve(__dirname, '..', '..');
const launcherDir = path.join(repo, 'packages', 'atlas-cli');

// ── Parse args ──────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
function getArg(name) {
	const idx = args.indexOf(name);
	return idx !== -1 ? args[idx + 1] : undefined;
}
const allowDirty = args.includes('--allow-dirty');
const skipPython = args.includes('--skip-python');
let version = getArg('--version');

// ── Helpers ─────────────────────────────────────────────────────────────────
const PASS = '\x1b[32m[OK  ]\x1b[0m';
const FAIL = '\x1b[31m[FAIL]\x1b[0m';
const SKIP = '\x1b[33m[SKIP]\x1b[0m';
let allPass = true;
let gateCount = 0;
let passCount = 0;

function gate(name, fn) {
	gateCount++;
	try {
		const detail = fn();
		console.log(`${PASS} ${name}${detail ? ': ' + detail : ''}`);
		passCount++;
		return true;
	} catch (err) {
		console.log(`${FAIL} ${name}: ${err.message}`);
		allPass = false;
		return false;
	}
}

function skip(name, reason) {
	gateCount++;
	console.log(`${SKIP} ${name}: ${reason}`);
	passCount++;
}

function run(cmd, opts = {}) {
	try {
		return execSync(cmd, { cwd: opts.cwd || repo, encoding: 'utf8', stdio: opts.stdio || 'pipe', ...opts }).trim();
	} catch (err) {
		throw new Error(`command failed (exit ${err.status}): ${cmd}`);
	}
}

// ── Load package.json ──────────────────────────────────────────────────────
const launcherPkg = JSON.parse(fs.readFileSync(path.join(launcherDir, 'package.json'), 'utf8'));
const platformName = '@systemsl2/atlas-win32-x64';

if (!version) version = launcherPkg.version;

console.log('');
console.log('\x1b[36mATLAS npm Publish Dry-Run — ' + version + '\x1b[0m');
console.log('='.repeat(60));
console.log('');

// ── Gate 1: Version format ─────────────────────────────────────────────────
gate('Version format', () => {
	if (!/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/.test(version)) {
		throw new Error('invalid version: ' + version);
	}
});

// ── Gate 2: Version consistency ────────────────────────────────────────────
gate('Version consistency', () => {
	if (launcherPkg.version !== version) {
		throw new Error(`package.json is ${launcherPkg.version}, expected ${version}`);
	}
	const pinned = launcherPkg.optionalDependencies?.[platformName];
	if (pinned !== version) {
		throw new Error(`${platformName} pinned at ${pinned}, expected ${version}`);
	}
});

// ── Gate 3: Git status ─────────────────────────────────────────────────────
if (allowDirty) {
	skip('Git clean', '--allow-dirty');
} else {
	gate('Git clean', () => {
		const dirty = run('git status --porcelain');
		if (dirty) {
			const lines = dirty.split('\n').length;
			throw new Error(`${lines} uncommitted change(s)`);
		}
	});
}

// ── Gate 4: Launcher tests ─────────────────────────────────────────────────
gate('atlas-cli tests', () => {
	run('npm test', { cwd: launcherDir, stdio: 'pipe' });
});

// ── Gate 5: Python tests ───────────────────────────────────────────────────
if (skipPython) {
	skip('Python config/doctor tests', '--skip-python');
} else {
	const venvPython = path.join(repo, '.venv', process.platform === 'win32' ? 'Scripts' : 'bin', 'python');
	if (fs.existsSync(venvPython)) {
		gate('Python config/doctor tests', () => {
			run(`"${venvPython}" -m pytest services/agent-runtime/tests/test_config_service.py services/agent-runtime/tests/test_cli_doctor.py -q`);
		});
	} else {
		skip('Python config/doctor tests', '.venv not found');
	}
}

// ── Gate 6: npm pack dry-run ───────────────────────────────────────────────
gate('npm pack launcher (dry-run)', () => {
	run('npm pack --dry-run', { cwd: launcherDir, stdio: 'pipe' });
});

// ── Gate 7: npm auth ───────────────────────────────────────────────────────
gate('npm auth (whoami)', () => {
	const user = run('npm whoami');
	return 'Logged in as: ' + user;
});

// ── Gate 8: Registry pre-flight ────────────────────────────────────────────
gate(`Registry: @systemsl2/atlas@${version} not published`, () => {
	try {
		run(`npm view @systemsl2/atlas@${version} version`);
		throw new Error('already published');
	} catch (err) {
		if (err.message === 'already published') throw err;
		// npm view exits non-zero when version doesn't exist — that's what we want
	}
});

gate(`Registry: ${platformName}@${version} not published`, () => {
	try {
		run(`npm view ${platformName}@${version} version`);
		throw new Error('already published');
	} catch (err) {
		if (err.message === 'already published') throw err;
	}
});

// ── Summary ────────────────────────────────────────────────────────────────
console.log('');
console.log('='.repeat(60));
if (allPass) {
	console.log(`\x1b[32mALL GATES PASSED (${passCount}/${gateCount}) — ready to publish ${version}\x1b[0m`);
	console.log('');
	console.log('To publish:');
	console.log('  1. Tag:  git tag v' + version + ' && git push origin v' + version);
	console.log('  2. CI:   GitHub Actions will run publish-npm.yml automatically');
	console.log('  3. Or:   powershell scripts/release/npm-release.ps1 -Version ' + version + ' -Mode Publish');
	process.exit(0);
} else {
	console.log(`\x1b[31mGATES FAILED: ${gateCount - passCount}/${gateCount} failed\x1b[0m`);
	console.log('\x1b[33mFix the failures above before publishing.\x1b[0m');
	process.exit(1);
}
