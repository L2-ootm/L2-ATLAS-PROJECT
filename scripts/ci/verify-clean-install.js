#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const crypto = require('node:crypto');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { fileURLToPath } = require('node:url');

const { verifyCleanInstall } = require('../../packages/atlas-cli/src/verifyCleanInstall');
const { hashFile } = require('../../packages/atlas-cli/src/manifest');

function parseArgs(argv) {
	const opts = {};
	for (let i = 0; i < argv.length; i += 1) {
		const arg = argv[i];
		if (arg === '--manifest') opts.manifest = argv[++i];
		else if (arg === '--update-manifest') opts.updateManifest = argv[++i];
		else if (arg === '--channel') opts.channel = argv[++i];
		else if (arg === '--platform') opts.platform = argv[++i];
		else if (arg === '--home') opts.home = argv[++i];
		else if (arg === '--version') opts.version = argv[++i];
		else if (arg === '--update-version') opts.updateVersion = argv[++i];
		else if (arg === '--local-index') opts.localIndex = argv[++i];
		else if (arg === '--probe-version') opts.probeVersion = true;
		else if (arg === '--probe-freellmapi-redaction') opts.probeFreellmapiRedaction = true;
	}
	return opts;
}

function usage() {
	console.log('usage: verify-clean-install (--local-index file | --manifest url --update-manifest url) [--channel stable] [--platform os-arch] [--home dir] [--version x] [--probe-version] [--probe-freellmapi-redaction]');
}

function run(command, args, options = {}) {
	const result = spawnSync(command, args, {
		encoding: 'utf8',
		windowsHide: true,
		...options,
	});
	if (result.error || result.status !== 0) {
		const detail = (result.stderr || result.stdout || result.error?.message || '').trim();
		throw new Error(`${options.label || path.basename(command)} failed${detail ? `: ${detail}` : ''}`);
	}
	return result;
}

function sha256(value) {
	return crypto.createHash('sha256').update(value).digest('hex');
}

function localArtifactPath(url, indexPath) {
	if (url.startsWith('file:')) return fileURLToPath(url);
	if (/^https?:/.test(url)) throw new Error('local release index must resolve to a local artifact');
	return path.resolve(path.dirname(indexPath), url);
}

function scanTreeForCanary(root, canary) {
	if (!fs.existsSync(root)) return [];
	const matches = [];
	const pending = [root];
	while (pending.length > 0) {
		const current = pending.pop();
		for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
			const target = path.join(current, entry.name);
			if (entry.isDirectory()) pending.push(target);
			else if (entry.isFile() && fs.readFileSync(target).includes(Buffer.from(canary))) matches.push(target);
		}
	}
	return matches;
}

function resolvedArtifact(index, version, platform, indexPath) {
	const releaseVersion = version || index.channels?.stable;
	const artifact = index.releases?.[releaseVersion]?.platforms?.[platform];
	if (!releaseVersion || !artifact?.url || !artifact?.sha256) {
		throw new Error(`local release index has no complete ${platform} artifact for ${releaseVersion || '(missing version)'}`);
	}
	const artifactPath = localArtifactPath(artifact.url, indexPath);
	if (!fs.existsSync(artifactPath)) throw new Error(`resolved artifact does not exist: ${artifactPath}`);
	const actualSha256 = hashFile(artifactPath);
	if (actualSha256 !== artifact.sha256) throw new Error('resolved artifact SHA-256 mismatch');
	return { version: releaseVersion, artifact, artifactPath, sha256: actualSha256 };
}

function installLauncher(repo, workspace) {
	const npmCli = path.join(path.dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js');
	if (!fs.existsSync(npmCli)) throw new Error(`npm CLI is missing beside Node: ${npmCli}`);
	const packageDir = path.join(repo, 'packages', 'atlas-cli');
	const packDir = path.join(workspace, 'pack');
	const prefix = path.join(workspace, 'launcher');
	fs.mkdirSync(packDir, { recursive: true });
	const packed = run(process.execPath, [npmCli, 'pack', packageDir, '--pack-destination', packDir, '--json'], {
		label: 'npm pack launcher',
	});
	const packReport = JSON.parse(packed.stdout);
	const tarball = path.join(packDir, packReport[0].filename);
	run(process.execPath, [npmCli, 'install', '--ignore-scripts', '--no-package-lock', '--omit=optional', '--prefix', prefix, tarball], {
		label: 'isolated launcher install',
	});
	const launcher = path.join(prefix, 'node_modules', '@systemsl2', 'atlas', 'bin', 'atlas.js');
	if (!fs.existsSync(launcher)) throw new Error('isolated installed launcher executable is missing');
	return launcher;
}

function createCanarySidecar(python, sidecarDir, canary, env) {
	const dbPath = path.join(sidecarDir, 'server', 'data', 'freeapi.db');
	fs.mkdirSync(path.dirname(dbPath), { recursive: true });
	const program = [
		'import os, sqlite3',
		'p=os.environ["ATLAS_CANARY_DB"]',
		'c=sqlite3.connect(p)',
		'c.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")',
		'c.execute("INSERT INTO settings VALUES (?, ?)", ("unified_api_key", os.environ["ATLAS_TEST_SECRET_CANARY"]))',
		'c.commit()',
		'c.close()',
	].join(';');
	run(python, ['-s', '-c', program], {
		env: { ...env, ATLAS_CANARY_DB: dbPath, ATLAS_TEST_SECRET_CANARY: canary },
		label: 'canary sidecar setup',
	});
}

function verifyLocalInstall(opts) {
	const repo = path.resolve(__dirname, '..', '..');
	const indexPath = path.resolve(opts.localIndex);
	if (!fs.existsSync(indexPath)) throw new Error(`local release index does not exist: ${indexPath}`);
	const index = JSON.parse(fs.readFileSync(indexPath, 'utf8'));
	const platform = opts.platform || `${process.platform}-${process.arch}`;
	const selected = resolvedArtifact(index, opts.version, platform, indexPath);
	const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'atlas-resolved-probe-'));
	const probeRoot = fs.mkdtempSync(path.join(path.resolve(opts.home), 'probe-'));
	const installRoot = path.join(probeRoot, 'install');
	const stateRoot = `${installRoot}-state`;
	const steps = [];
	let launcher;
	try {
		launcher = installLauncher(repo, workspace);
		const baseEnv = {
			...process.env,
			ATLAS_HOME: stateRoot,
			ATLAS_INSTALL_ROOT: installRoot,
			ATLAS_RELEASE_MANIFEST: indexPath,
			NODE_PATH: '',
			PYTHONPATH: '',
		};
		const install = run(process.execPath, [
			launcher,
			'install',
			'--manifest',
			indexPath,
			'--version',
			selected.version,
			'--platform',
			platform,
			'--json',
		], { cwd: workspace, env: baseEnv, label: 'resolved artifact install' });
		steps.push({ ok: true, name: 'artifact-path', detail: selected.artifactPath });
		steps.push({ ok: true, name: 'artifact-sha256', detail: selected.sha256 });

		const manifestPath = path.join(installRoot, 'versions', selected.version, 'manifest.json');
		const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
		if (manifest.version !== selected.version) throw new Error('installed manifest version mismatch');
		steps.push({ ok: true, name: 'manifest-version', detail: manifest.version });
		steps.push({ ok: true, name: 'installed-executable', detail: launcher });

		if (opts.probeVersion) {
			const versionResult = run(process.execPath, [launcher, '--version'], {
				cwd: workspace,
				env: baseEnv,
				label: 'installed atlas --version',
			});
			const output = versionResult.stdout.trim();
			if (output !== selected.version) throw new Error('installed atlas --version mismatch');
			steps.push({ ok: true, name: 'installed-version-output', detail: output });
		}

		if (opts.probeFreellmapiRedaction) {
			const canary = process.env.ATLAS_TEST_SECRET_CANARY || `atlas-canary-${sha256(String(Date.now())).slice(0, 24)}`;
			const sidecarDir = path.join(workspace, 'freellmapi-sidecar');
			const python = path.join(
				installRoot,
				'versions',
				selected.version,
				'python',
				process.platform === 'win32' ? 'python.exe' : 'bin/python3'
			);
			createCanarySidecar(python, sidecarDir, canary, baseEnv);
			const redaction = run(process.execPath, [launcher, 'freellmapi', 'status', '--json'], {
				cwd: workspace,
				env: {
					...baseEnv,
					ATLAS_FREELLMAPI_DIR: sidecarDir,
					ATLAS_TEST_SECRET_CANARY: canary,
				},
				label: 'installed FreeLLMAPI redaction probe',
			});
			if (`${install.stdout}${install.stderr}${redaction.stdout}${redaction.stderr}`.includes(canary)) {
				throw new Error('FreeLLMAPI canary leaked through process output');
			}
			const persistedMatches = scanTreeForCanary(stateRoot, canary);
			if (persistedMatches.length > 0) {
				throw new Error('FreeLLMAPI canary leaked into persisted audit or evidence');
			}
			steps.push({
				ok: true,
				name: 'freellmapi-redaction',
				detail: 'stdout, stderr, audit, and evidence are canary-free',
			});
		}

		run(process.execPath, [launcher, 'uninstall'], {
			cwd: workspace,
			env: baseEnv,
			label: 'isolated uninstall',
		});
		steps.push({ ok: true, name: 'uninstall', detail: 'resolved runtime removed' });
		return { ok: true, steps };
	} finally {
		fs.rmSync(workspace, { recursive: true, force: true });
		fs.rmSync(probeRoot, { recursive: true, force: true });
	}
}

async function main() {
	const opts = parseArgs(process.argv.slice(2));
	if (opts.localIndex) {
		opts.home = opts.home || fs.mkdtempSync(path.join(os.tmpdir(), 'atlas-clean-install-'));
		fs.mkdirSync(opts.home, { recursive: true });
		const report = verifyLocalInstall(opts);
		for (const step of report.steps) console.log(`OK ${step.name}: ${step.detail}`);
		return;
	}
	if (!opts.manifest || !opts.updateManifest) {
		usage();
		process.exitCode = 2;
		return;
	}
	opts.home = opts.home || fs.mkdtempSync(path.join(os.tmpdir(), 'atlas-clean-install-'));

	const report = await verifyCleanInstall(opts);
	for (const step of report.steps) {
		console.log(`${step.ok ? 'OK' : 'FAIL'} ${step.name}: ${step.detail}`);
	}
	if (!report.ok) process.exitCode = 1;
}

main().catch((err) => {
	console.error(`FAIL verify-clean-install: ${err.message}`);
	process.exitCode = 1;
});
