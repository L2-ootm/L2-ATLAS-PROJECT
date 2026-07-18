'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');

const { atlasInstallRoot, atlasStateHome, versionsDir, versionDir, currentPointerFile, manifestFile } = require('./paths');
const { buildManifest, readManifest, verifyManifest } = require('./manifest');
const { readInstallState, writeInstallState } = require('./installState');
const {
	readReleaseIndex,
	selectArtifact,
	downloadVerifiedArtifact,
	extractArchive
} = require('./release');
const { appendRollbackHistory, resolveRollbackTarget } = require('./rollbackHistory');
const { atomicWriteFileSync } = require('./atomicWrite');

class CliError extends Error {}

function copyDir(src, dest) {
	fs.mkdirSync(dest, { recursive: true });
	fs.cpSync(src, dest, { recursive: true });
}

function readCurrent(home) {
	const file = currentPointerFile(home);
	if (!fs.existsSync(file)) return null;
	const version = fs.readFileSync(file, 'utf8').trim();
	return version || null;
}

function writeCurrent(home, version) {
	atomicWriteFileSync(currentPointerFile(home), `${version}\n`, 'utf8');
}

function listVersions(home) {
	const dir = versionsDir(home);
	if (!fs.existsSync(dir)) return [];
	return fs
		.readdirSync(dir, { withFileTypes: true })
		.filter((e) => e.isDirectory())
		.map((e) => e.name)
		.sort();
}

/** Same default entrypoint names `launcher.js` looks for (mirrored here, not
 * imported, to avoid a require cycle: launcher.js requires commands.js for
 * readCurrent). */
function _candidateRuntimeEntrypoints(platform = process.platform) {
	return platform === 'win32' ? ['bin/atlas.exe', 'atlas.exe'] : ['bin/atlas', 'atlas'];
}

/** Resolve the runtime entrypoint inside a specific installed version dir
 * (as opposed to launcher.js's resolveRuntimeEntrypoint, which always
 * resolves the *current* version — migrations must run against the version
 * just installed/updated/rolled back to, which may not be current yet). */
function _resolveRuntimeEntrypointFor(home, version) {
	if (!version) return null;
	const root = path.resolve(versionDir(home, version));
	const state = readInstallState(home);
	const candidates = state?.runtimeEntrypoint ? [state.runtimeEntrypoint] : _candidateRuntimeEntrypoints();
	for (const relative of candidates) {
		const absolute = path.resolve(root, relative);
		if (!absolute.startsWith(`${root}${path.sep}`)) continue;
		if (fs.existsSync(absolute) && fs.statSync(absolute).isFile()) return absolute;
	}
	return null;
}

/** Spawn the resolved runtime entrypoint the same way launcher.js does: a
 * `.js` entrypoint runs under this process's Node, anything else runs
 * directly (the packaged atlas binary embeds its own Python runtime). */
function _spawnRuntime(entrypoint, args, home) {
	const isNodeScript = path.extname(entrypoint).toLowerCase() === '.js';
	const command = isNodeScript ? process.execPath : entrypoint;
	const commandArgs = isNodeScript ? [entrypoint, ...args] : args;
	return spawnSync(command, commandArgs, {
		encoding: 'utf8',
		timeout: 30_000,
		env: { ...process.env, ATLAS_INSTALL_ROOT: home },
		shell: false
	});
}

/**
 * Apply pending DB migrations by shelling out to the installed runtime's
 * `db init` (services/agent-runtime/atlas_runtime/db.py owns the migration
 * table and is the single source of truth — this never reimplements it).
 * Never blocks the caller: a missing runtime entrypoint or a failed
 * migration is reported in the result, not thrown, because the version
 * files are already on disk and the user can retry with `atlas db init`.
 * Returns `{ ok, applied: string[], error?, note? }`.
 */
function runMigrations(home, version) {
	const entrypoint = _resolveRuntimeEntrypointFor(home, version);
	if (!entrypoint) {
		return { ok: true, applied: [], note: 'runtime entrypoint not found, skipping migrations' };
	}

	const result = _spawnRuntime(entrypoint, ['db', 'init'], home);
	if (result.error) {
		return { ok: false, applied: [], error: result.error.message };
	}
	if (result.status !== 0) {
		const stderr = (result.stderr || '').trim();
		return { ok: false, applied: [], error: stderr || `exit code ${result.status}` };
	}

	const output = (result.stdout || '').trim();
	const applied = output
		.split('\n')
		.filter((line) => line.startsWith('applied '))
		.map((line) => line.replace('applied ', '').trim());

	return { ok: true, applied, note: output || undefined };
}

/**
 * `atlas-cli install --from <bundleDir> [--version X]`
 *
 * Stages a version from a local directory (docs/plans/2026-07-03-wsb-
 * installer-plan.md §7 step 1: prove the mechanics against a manually
 * staged bundle before any CI/publishing exists). A real release-fetch
 * path (`--version X --channel stable` downloading from a release host)
 * is a separate, later addition — the version/current/manifest/doctor
 * mechanics below don't change when that lands.
 */
function install(home, opts) {
	if (!opts.from) throw new CliError('install requires --from <staged bundle dir>');
	const source = path.resolve(opts.from);
	if (!fs.existsSync(source)) throw new CliError(`staged bundle not found: ${source}`);

	const version = opts.version || path.basename(source);
	const dest = versionDir(home, version);
	if (fs.existsSync(dest)) {
		throw new CliError(`version ${version} is already installed at ${dest} (use update, or uninstall first)`);
	}

	copyDir(source, dest);

	const manifestPath = manifestFile(dest);
	if (!fs.existsSync(manifestPath)) {
		const manifest = buildManifest(dest, version);
		fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
	}

	writeCurrent(home, version);
	writeInstallState(home, {
		installedVersion: version,
		installMethod: 'local-staged',
		lastUpdateCheck: new Date().toISOString(),
		runtimeEntrypoint: opts.entrypoint || undefined
	});

	const migrations = runMigrations(home, version);
	return { version, path: dest, migrations };
}

/**
 * `atlas-cli update --from <bundleDir> --version X`
 *
 * Same staging mechanics as install, but the previous version is retained
 * on disk (not deleted) so rollback has something to flip back to.
 */
function update(home, opts) {
	if (!opts.from) throw new CliError('update requires --from <staged bundle dir>');
	if (!opts.version) throw new CliError('update requires --version <new version>');
	const source = path.resolve(opts.from);
	if (!fs.existsSync(source)) throw new CliError(`staged bundle not found: ${source}`);

	const previous = readCurrent(home);
	const dest = versionDir(home, opts.version);
	if (fs.existsSync(dest)) {
		throw new CliError(`version ${opts.version} already exists at ${dest}`);
	}

	copyDir(source, dest);
	const manifestPath = manifestFile(dest);
	if (!fs.existsSync(manifestPath)) {
		const manifest = buildManifest(dest, opts.version);
		fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
	}

	writeCurrent(home, opts.version);
	writeInstallState(home, {
		installedVersion: opts.version,
		installMethod: 'local-staged',
		lastUpdateCheck: new Date().toISOString(),
		previousVersion: previous || undefined,
		runtimeEntrypoint: opts.entrypoint || undefined
	});

	const migrations = runMigrations(home, opts.version);
	return { version: opts.version, previous, path: dest, migrations };
}

/** Activate the complete runtime carried by the npm platform package. */
function installBundledPlatform(home, opts) {
	if (!opts.from || !opts.version || !opts.entrypoint) {
		throw new CliError('platform package requires from, version, and entrypoint');
	}
	const source = path.resolve(opts.from);
	const previous = readCurrent(home);
	const dest = versionDir(home, opts.version);
	let reused = false;
	if (fs.existsSync(dest)) {
		const existingManifest = manifestFile(dest);
		if (!fs.existsSync(existingManifest) || !verifyManifest(dest, readManifest(existingManifest)).ok) {
			throw new CliError(`version ${opts.version} exists but failed verification at ${dest}`);
		}
		reused = true;
	} else {
		copyDir(source, dest);
		const manifest = buildManifest(dest, opts.version, { entrypoint: opts.entrypoint });
		fs.writeFileSync(manifestFile(dest), JSON.stringify(manifest, null, 2) + '\n', 'utf8');
	}
	writeCurrent(home, opts.version);
	writeInstallState(home, {
		installedVersion: opts.version,
		installMethod: 'npm-platform-package',
		packageName: opts.packageName,
		lastUpdateCheck: new Date().toISOString(),
		runtimeEntrypoint: opts.entrypoint,
		previousVersion: previous && previous !== opts.version ? previous : undefined
	});
	const migrations = runMigrations(home, opts.version);
	return { version: opts.version, previous, path: dest, reused, migrations };
}

async function stageRelease(home, opts, mode) {
	if (!opts.manifest) throw new CliError(`${mode} requires --manifest <release index url>`);
	let index;
	try {
		index = await readReleaseIndex(opts.manifest);
	} catch (err) {
		throw new CliError(err.message);
	}
	let selected;
	try {
		selected = selectArtifact(index, opts);
	} catch (err) {
		throw new CliError(err.message);
	}

	const previous = readCurrent(home);
	const dest = versionDir(home, selected.version);
	if (fs.existsSync(dest)) {
		const existingManifest = manifestFile(dest);
		if (!fs.existsSync(existingManifest) || !verifyManifest(dest, readManifest(existingManifest)).ok) {
			throw new CliError(`version ${selected.version} exists but failed verification at ${dest}`);
		}
		writeCurrent(home, selected.version);
		writeInstallState(home, {
			installedVersion: selected.version,
			installMethod: 'release-manifest',
			lastUpdateCheck: new Date().toISOString(),
			channel: opts.channel || 'stable',
			platform: selected.platform,
			releaseManifest: opts.manifest,
			runtimeEntrypoint: selected.artifact.entrypoint || undefined,
			previousVersion: mode === 'update' && previous !== selected.version ? previous || undefined : undefined
		});
		const migrations = runMigrations(home, selected.version);
		return { version: selected.version, previous, path: dest, platform: selected.platform, reused: true, migrations };
	}

	const workDir = fs.mkdtempSync(path.join(os.tmpdir(), 'atlas-cli-release-'));
	try {
		const archive = await downloadVerifiedArtifact(selected.artifact, workDir);
		extractArchive(archive, dest);
		const manifestPath = manifestFile(dest);
		if (!fs.existsSync(manifestPath)) {
			const manifest = buildManifest(dest, selected.version, {
				commit: selected.artifact.commit || index.commit || null,
				entrypoint: selected.artifact.entrypoint || null
			});
			fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
		}
	} catch (err) {
		fs.rmSync(dest, { recursive: true, force: true });
		throw new CliError(err.message);
	} finally {
		fs.rmSync(workDir, { recursive: true, force: true });
	}

	writeCurrent(home, selected.version);
	writeInstallState(home, {
		installedVersion: selected.version,
		installMethod: 'release-manifest',
		lastUpdateCheck: new Date().toISOString(),
		channel: opts.channel || 'stable',
		platform: selected.platform,
		releaseManifest: opts.manifest,
		runtimeEntrypoint: selected.artifact.entrypoint || undefined,
		previousVersion: mode === 'update' ? previous || undefined : undefined
	});

	const migrations = runMigrations(home, selected.version);
	return { version: selected.version, previous, path: dest, platform: selected.platform, migrations };
}

async function installFromRelease(home, opts) {
	return stageRelease(home, opts, 'install');
}

async function updateFromRelease(home, opts) {
	return stageRelease(home, opts, 'update');
}

/**
 * Verify a version directory has a valid manifest and all checksums match.
 * Returns { ok, reason } where reason is a human-readable failure description.
 */
function verifyVersionIntegrity(home, version) {
	const dest = versionDir(home, version);
	if (!fs.existsSync(dest)) {
		return { ok: false, reason: `version directory missing: ${dest}` };
	}
	const manifestPath = manifestFile(dest);
	if (!fs.existsSync(manifestPath)) {
		return { ok: false, reason: `manifest missing for ${version}` };
	}
	const manifest = readManifest(manifestPath);
	const result = verifyManifest(dest, manifest);
	if (!result.ok) {
		const details = [
			result.mismatches.length ? `mismatched: ${result.mismatches.join(', ')}` : '',
			result.missing.length ? `missing: ${result.missing.join(', ')}` : ''
		].filter(Boolean).join('; ');
		return { ok: false, reason: `checksum verification failed — ${details}` };
	}
	return { ok: true, reason: null };
}

/**
 * `atlas-cli rollback [--to X] [--dry-run] [--no-verify]` — flip `current`
 * back to a prior retained version.
 *
 * Target resolution: explicit --to > the rollbackHistory chain (so a second
 * rollback undoes the first, yo-yo style) > the legacy single-slot
 * `previousVersion` (state written before rollbackHistory existed).
 *
 * Pre-verification (skippable with --no-verify) checks the target's manifest
 * before flipping anything. --dry-run reports the plan without writing state.
 * After a real rollback, migrations run against the target version and
 * doctor() runs as a post-health-check so a broken rollback is visible
 * immediately instead of at the next command.
 */
function rollback(home, opts) {
	const state = readInstallState(home);
	const target = resolveRollbackTarget(state, opts.to);
	if (!target) throw new CliError('no prior version on record; pass --to <version> explicitly');
	const dest = versionDir(home, target);
	if (!fs.existsSync(dest)) throw new CliError(`version ${target} is not installed at ${dest}`);

	const current = readCurrent(home);
	if (current === target) throw new CliError(`already at version ${target}; nothing to roll back`);

	if (!opts.noVerify) {
		const check = verifyVersionIntegrity(home, target);
		if (!check.ok) throw new CliError(`target version ${target} failed pre-verification: ${check.reason}`);
	}

	if (opts.dryRun) {
		return { dryRun: true, version: target, rolledBackFrom: current, manifestVerified: !opts.noVerify };
	}

	const targetManifestPath = manifestFile(dest);
	const targetManifest = fs.existsSync(targetManifestPath) ? readManifest(targetManifestPath) : null;

	let newState = {
		installedVersion: target,
		installMethod: state?.installMethod || 'local-staged',
		lastUpdateCheck: new Date().toISOString(),
		previousVersion: current || undefined,
		channel: state?.channel,
		platform: state?.platform,
		releaseManifest: state?.releaseManifest,
		runtimeEntrypoint: targetManifest?.entrypoint || state?.runtimeEntrypoint,
		// carry the existing chain forward — appendRollbackHistory reads it off
		// this object, not off the old `state`, so it must be seeded here first.
		rollbackHistory: state?.rollbackHistory
	};
	newState = appendRollbackHistory(newState, current, target, 'explicit');

	writeCurrent(home, target);
	writeInstallState(home, newState);

	const migrations = runMigrations(home, target);

	let postCheck;
	try {
		postCheck = doctor(home);
	} catch {
		// doctor() should never throw, but guard against unexpected failures
		// rather than let a post-rollback health probe crash the rollback itself.
		postCheck = { ok: false, checks: [{ name: 'post-rollback-check', ok: false, detail: 'doctor threw unexpectedly' }] };
	}

	return {
		version: target,
		rolledBackFrom: current,
		manifestVerified: !opts.noVerify,
		migrations,
		postHealthCheck: postCheck.ok,
		doctorReport: postCheck
	};
}

/** `atlas-cli rollback-history` — display the rollback history chain. */
function rollbackHistory(home) {
	const state = readInstallState(home);
	const history = Array.isArray(state?.rollbackHistory) ? state.rollbackHistory : [];
	return {
		current: readCurrent(home),
		history: history.map((entry) => ({
			from: entry.from,
			to: entry.to,
			timestamp: entry.timestamp,
			reason: entry.reason || 'explicit'
		}))
	};
}

/**
 * `atlas-cli uninstall [--purge]` — removes versions/current/install.json.
 * `--purge` additionally removes runtime state (atlas.db, config) if the
 * caller passes their location; left to the caller to avoid this package
 * guessing at ATLAS_HOME-adjacent runtime paths it doesn't own.
 */
function uninstall(home, opts) {
	const removed = [];
	const versions = versionsDir(home);
	if (fs.existsSync(versions)) {
		fs.rmSync(versions, { recursive: true, force: true });
		removed.push(versions);
	}
	const current = currentPointerFile(home);
	if (fs.existsSync(current)) {
		fs.rmSync(current, { force: true });
		removed.push(current);
	}
	const installFile = path.join(home, 'install.json');
	if (fs.existsSync(installFile)) {
		fs.rmSync(installFile, { force: true });
		removed.push(installFile);
	}
	if (opts.purge && opts.purgePaths) {
		for (const p of opts.purgePaths) {
			if (fs.existsSync(p)) {
				fs.rmSync(p, { recursive: true, force: true });
				removed.push(p);
			}
		}
	}
	return { removed };
}

/**
 * `atlas-cli doctor` — installed-vs-on-disk checksum match (per manifest),
 * retained-version list, current-pointer sanity.
 */
function doctor(home) {
	const checks = [];
	const current = readCurrent(home);
	if (!current) {
		checks.push({ name: 'current-version-set', ok: false, detail: 'no version installed (run install first)' });
		return { ok: false, checks };
	}
	checks.push({ name: 'current-version-set', ok: true, detail: current });

	const dest = versionDir(home, current);
	if (!fs.existsSync(dest)) {
		checks.push({ name: 'current-version-present', ok: false, detail: `${dest} is missing` });
		return { ok: false, checks };
	}
	checks.push({ name: 'current-version-present', ok: true, detail: dest });

	const manifestPath = manifestFile(dest);
	if (!fs.existsSync(manifestPath)) {
		checks.push({ name: 'manifest-present', ok: false, detail: `${manifestPath} is missing` });
	} else {
		checks.push({ name: 'manifest-present', ok: true, detail: manifestPath });
		const manifest = readManifest(manifestPath);
		const result = verifyManifest(dest, manifest);
		checks.push({
			name: 'manifest-checksum-match',
			ok: result.ok,
			detail: result.ok
				? 'all files match recorded checksums'
				: `mismatches: ${result.mismatches.join(', ') || 'none'}; missing: ${result.missing.join(', ') || 'none'}`
		});
	}

	const versions = listVersions(home);
	checks.push({ name: 'retained-versions', ok: true, detail: versions.join(', ') || '(none)' });

	const state = readInstallState(home);
	if (state?.runtimeEntrypoint) {
		const entrypoint = path.resolve(dest, state.runtimeEntrypoint);
		const insideVersion = entrypoint.startsWith(`${path.resolve(dest)}${path.sep}`);
		checks.push({
			name: 'runtime-entrypoint',
			ok: insideVersion && fs.existsSync(entrypoint),
			detail: insideVersion && fs.existsSync(entrypoint) ? entrypoint : `missing or unsafe: ${state.runtimeEntrypoint}`
		});
	}

	// Version consistency — only meaningful for the npm-platform-package
	// distribution path, where the release process pins the launcher's own
	// package.json version to the materialized runtime version 1:1 (see
	// scripts/release/npm-release.ps1 Assert-VersionContract). Local-staged
	// and release-manifest installs intentionally allow arbitrary versions
	// (manual/dev staging), so the check doesn't apply to them.
	if (state?.installMethod === 'npm-platform-package') {
		const launcherVersion = require('../package.json').version;
		checks.push({
			name: 'version-consistency',
			ok: launcherVersion === current,
			detail: launcherVersion === current
				? `launcher ${launcherVersion} == runtime ${current}`
				: `MISMATCH: launcher ${launcherVersion} != runtime ${current}`
		});
	}

	return { ok: checks.every((c) => c.ok), checks };
}

/** `atlas-cli versions` — list installed versions, marking `current`. */
function versions(home) {
	const current = readCurrent(home);
	return listVersions(home).map((v) => ({ version: v, current: v === current }));
}

module.exports = {
	CliError,
	atlasInstallRoot,
	atlasStateHome,
	// Backward-compatible name for the installer prototype API. New callers
	// should use atlasInstallRoot; ATLAS_HOME now means runtime state only.
	atlasHome: atlasInstallRoot,
	install,
	installBundledPlatform,
	installFromRelease,
	update,
	updateFromRelease,
	rollback,
	rollbackHistory,
	uninstall,
	doctor,
	versions,
	readCurrent,
	listVersions,
	runMigrations
};
