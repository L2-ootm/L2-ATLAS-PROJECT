'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');

const cmds = require('../src/commands');
const { atlasInstallRoot, atlasStateHome } = require('../src/paths');
const { resolveRuntimeEntrypoint, launchRuntime } = require('../src/launcher');
const { compareVersions, updateLauncher, handoffUpdatedLauncher } = require('../src/selfUpdate');
const { check } = require('../src/check');
const { safeRelativeEntrypoint } = require('../src/release');
const { buildPlatformPackage } = require('../src/buildPlatformPackage');
const { materializePlatformPackage, platformPackageName } = require('../src/platformPackage');

function tempDir(label) {
	return fs.mkdtempSync(path.join(os.tmpdir(), `atlas-lifecycle-${label}-`));
}

test('application install root is separate from ATLAS_HOME state', () => {
	const env = {
		LOCALAPPDATA: 'C:\\Users\\operator\\AppData\\Local',
		ATLAS_HOME: 'C:\\Users\\operator\\atlas-state'
	};
	assert.equal(atlasInstallRoot(env, 'win32'), path.join(env.LOCALAPPDATA, 'atlas'));
	assert.equal(atlasStateHome(env), path.resolve(env.ATLAS_HOME));
	assert.notEqual(atlasInstallRoot(env, 'win32'), atlasStateHome(env));
});

test('runtime entrypoint resolves only inside the active immutable release', () => {
	const root = tempDir('root');
	const bundle = tempDir('bundle');
	fs.mkdirSync(path.join(bundle, 'bin'), { recursive: true });
	fs.writeFileSync(path.join(bundle, 'bin', 'runtime.js'), 'process.exit(0);\n');
	cmds.install(root, { from: bundle, version: '1.0.0', entrypoint: 'bin/runtime.js' });
	assert.equal(resolveRuntimeEntrypoint(root), path.join(root, 'versions', '1.0.0', 'bin', 'runtime.js'));
	assert.equal(launchRuntime(root, []), 0);
});

test('release entrypoint rejects absolute and traversal paths', () => {
	assert.equal(safeRelativeEntrypoint('bin/atlas.exe'), 'bin/atlas.exe');
	assert.throws(() => safeRelativeEntrypoint('../atlas.exe'), /unsafe/);
	assert.throws(() => safeRelativeEntrypoint('C:\\atlas.exe'), /relative/);
});

test('launcher semver comparison and npm self-update are deterministic', async () => {
	assert.equal(compareVersions('1.2.0', '1.1.9'), 1);
	assert.equal(compareVersions('1.2.0-beta.1', '1.2.0'), -1);
	let invocation = null;
	const result = await updateLauncher({
		currentVersion: '0.1.0',
		fetcher: async () => ({ ok: true, json: async () => ({ version: '0.2.0' }) }),
		spawn: (command, args) => {
			invocation = { command, args };
			return { status: 0 };
		}
	});
	assert.equal(result.updated, true);
	assert.deepEqual(invocation, {
		command: 'npm',
		args: ['install', '--global', '@systemsl2/atlas@0.2.0']
	});
});

test('check reports an available update without installing anything', async () => {
	const result = await check({
		currentVersion: '0.1.0',
		fetcher: async () => ({ ok: true, json: async () => ({ version: '0.2.0' }) })
	});
	assert.equal(result.updateAvailable, true);
	assert.equal(result.current, '0.1.0');
	assert.equal(result.latest, '0.2.0');
});

test('check reports no update when already on the latest version', async () => {
	const result = await check({
		currentVersion: '0.2.0',
		fetcher: async () => ({ ok: true, json: async () => ({ version: '0.2.0' }) })
	});
	assert.equal(result.updateAvailable, false);
	assert.equal(result.latest, '0.2.0');
});

test('updated launcher hands runtime materialization to the newly installed code', () => {
	let invocation = null;
	const status = handoffUpdatedLauncher(['--json'], {
		node: 'node.exe',
		entrypoint: 'C:\\npm\\node_modules\\@systemsl2\\atlas\\bin\\atlas.js',
		env: { ATLAS_HOME: 'C:\\atlas-state' },
		spawn: (command, args, options) => {
			invocation = { command, args, options };
			return { status: 0 };
		}
	});
	assert.equal(status, 0);
	assert.equal(invocation.command, 'node.exe');
	assert.deepEqual(invocation.args, [
		'C:\\npm\\node_modules\\@systemsl2\\atlas\\bin\\atlas.js',
		'update',
		'--json',
		'--no-launcher-update'
	]);
	assert.equal(invocation.options.shell, false);
	assert.equal(invocation.options.env.ATLAS_HOME, 'C:\\atlas-state');
});

test('platform npm package materializes a verified release without touching ATLAS_HOME', () => {
	const installRoot = tempDir('install');
	const stateHome = tempDir('state');
	const bundle = tempDir('bundle');
	const packages = tempDir('packages');
	fs.mkdirSync(path.join(bundle, 'bin'), { recursive: true });
	fs.writeFileSync(path.join(bundle, 'bin', 'runtime.js'), 'process.exit(0);\n');
	const built = buildPlatformPackage({
		bundleDir: bundle,
		outDir: packages,
		version: '1.0.0',
		platform: `${process.platform}-${process.arch}`,
		entrypoint: 'bin/runtime.js'
	});
	const marker = path.join(stateHome, 'modules', 'operator-module', 'module.yaml');
	fs.mkdirSync(path.dirname(marker), { recursive: true });
	fs.writeFileSync(marker, 'id: operator-module\n');

	const result = materializePlatformPackage(installRoot, {
		env: { ATLAS_PLATFORM_PACKAGE_ROOT: built.packageDir, ATLAS_HOME: stateHome }
	});
	assert.equal(platformPackageName(), `@systemsl2/atlas-${process.platform}-${process.arch}`);
	assert.equal(cmds.readCurrent(installRoot), '1.0.0');
	assert.equal(fs.readFileSync(marker, 'utf8'), 'id: operator-module\n');
	assert.equal(resolveRuntimeEntrypoint(installRoot), path.join(installRoot, 'versions', '1.0.0', 'bin', 'runtime.js'));
});

test('fresh platform install binds state before migrations and the first runtime command', () => {
	const work = tempDir('clean-platform-install');
	const installRoot = path.join(work, 'app');
	const stateHome = path.join(work, 'state');
	const bundle = path.join(work, 'bundle');
	const packages = path.join(work, 'packages');
	const runtime = path.join(bundle, 'bin', 'runtime.js');
	fs.mkdirSync(path.dirname(runtime), { recursive: true });
	fs.writeFileSync(runtime, `
const fs = require('node:fs');
const path = require('node:path');
const marker = path.join(process.env.ATLAS_HOME, '.atlas-state-root.json');
if (!fs.existsSync(marker)) {
	console.error('state marker missing before runtime launch');
	process.exit(9);
}
if (process.argv.slice(2).join(' ') === 'db init') {
	fs.writeFileSync(path.join(process.env.ATLAS_HOME, 'atlas.db'), 'initialized');
	console.log('applied 0001_test');
} else {
	console.log('atlas test runtime 1.0.0');
}
`);
	const built = buildPlatformPackage({
		bundleDir: bundle,
		outDir: packages,
		version: '1.0.0',
		platform: `${process.platform}-${process.arch}`,
		entrypoint: 'bin/runtime.js'
	});
	const cli = path.join(__dirname, '..', 'bin', 'atlas.js');
	const env = {
		...process.env,
		ATLAS_INSTALL_ROOT: installRoot,
		ATLAS_HOME: stateHome,
		ATLAS_PLATFORM_PACKAGE_ROOT: built.packageDir
	};

	const installed = spawnSync(process.execPath, [cli, 'install', '--json'], { encoding: 'utf8', env });
	assert.equal(installed.status, 0, installed.stderr || installed.stdout);
	assert.equal(JSON.parse(installed.stdout).version, '1.0.0');
	assert.equal(fs.existsSync(path.join(stateHome, '.atlas-state-root.json')), true);
	assert.equal(fs.readFileSync(path.join(stateHome, 'atlas.db'), 'utf8'), 'initialized');

	const firstCommand = spawnSync(process.execPath, [cli, 'runtime-smoke'], { encoding: 'utf8', env });
	assert.equal(firstCommand.status, 0, firstCommand.stderr || firstCommand.stdout);
	assert.match(firstCommand.stdout, /atlas test runtime 1\.0\.0/);
});
