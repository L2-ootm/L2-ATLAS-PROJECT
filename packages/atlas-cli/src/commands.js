'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const { atlasInstallRoot, atlasStateHome, versionsDir, versionDir, currentPointerFile, manifestFile } = require('./paths');
const { buildManifest, readManifest, verifyManifest } = require('./manifest');
const { readInstallState, writeInstallState } = require('./installState');
const {
	readReleaseIndex,
	selectArtifact,
	downloadVerifiedArtifact,
	extractArchive
} = require('./release');

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
	fs.writeFileSync(currentPointerFile(home), `${version}\n`, 'utf8');
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

	return { version, path: dest };
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

	return { version: opts.version, previous, path: dest };
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
	return { version: opts.version, previous, path: dest, reused };
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
		return { version: selected.version, previous, path: dest, platform: selected.platform, reused: true };
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

	return { version: selected.version, previous, path: dest, platform: selected.platform };
}

async function installFromRelease(home, opts) {
	return stageRelease(home, opts, 'install');
}

async function updateFromRelease(home, opts) {
	return stageRelease(home, opts, 'update');
}

/**
 * `atlas-cli rollback [--to X]` — flip `current` back to a prior retained
 * version. Defaults to the version update() recorded as `previousVersion`.
 */
function rollback(home, opts) {
	const state = readInstallState(home);
	const target = opts.to || state?.previousVersion;
	if (!target) throw new CliError('no prior version on record; pass --to <version> explicitly');
	const dest = versionDir(home, target);
	if (!fs.existsSync(dest)) throw new CliError(`version ${target} is not installed at ${dest}`);

	const current = readCurrent(home);
	const targetManifestPath = manifestFile(dest);
	const targetManifest = fs.existsSync(targetManifestPath) ? readManifest(targetManifestPath) : null;
	writeCurrent(home, target);
	writeInstallState(home, {
		installedVersion: target,
		installMethod: state?.installMethod || 'local-staged',
		lastUpdateCheck: new Date().toISOString(),
		previousVersion: current || undefined,
		channel: state?.channel,
		platform: state?.platform,
		releaseManifest: state?.releaseManifest,
		runtimeEntrypoint: targetManifest?.entrypoint || state?.runtimeEntrypoint
	});

	return { version: target, rolledBackFrom: current };
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
	uninstall,
	doctor,
	versions,
	readCurrent,
	listVersions
};
