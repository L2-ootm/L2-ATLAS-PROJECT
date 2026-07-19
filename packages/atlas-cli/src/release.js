'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { hashFile } = require('./manifest');
const { extractTarGz } = require('./tarball');
const { compareVersions } = require('./selfUpdate');

function platformKey(runtime = process) {
	return `${runtime.platform}-${runtime.arch}`;
}

function safeRelativeEntrypoint(value) {
	if (!value) return null;
	const normalized = String(value).replace(/\\/g, '/');
	if (normalized.startsWith('/') || /^[A-Za-z]:\//.test(normalized)) {
		throw new Error(`release entrypoint must be relative: ${value}`);
	}
	const parts = normalized.split('/');
	if (parts.some((part) => !part || part === '.' || part === '..')) {
		throw new Error(`unsafe release entrypoint: ${value}`);
	}
	return normalized;
}

function fileUrlToPath(url) {
	const parsed = new URL(url);
	if (parsed.protocol !== 'file:') throw new Error(`not a file URL: ${url}`);
	return decodeURIComponent(parsed.pathname.replace(/^\/([A-Za-z]:\/)/, '$1'));
}

async function readText(location) {
	if (/^https?:\/\//.test(location)) {
		const res = await fetch(location);
		if (!res.ok) throw new Error(`fetch failed ${res.status} for ${location}`);
		return res.text();
	}
	const file = location.startsWith('file://') ? fileUrlToPath(location) : location;
	return fs.readFileSync(file, 'utf8');
}

async function copyArtifact(location, dest) {
	if (/^https?:\/\//.test(location)) {
		const res = await fetch(location);
		if (!res.ok) throw new Error(`download failed ${res.status} for ${location}`);
		const bytes = Buffer.from(await res.arrayBuffer());
		fs.writeFileSync(dest, bytes);
		return;
	}
	const file = location.startsWith('file://') ? fileUrlToPath(location) : location;
	fs.copyFileSync(file, dest);
}

async function readReleaseIndex(location) {
	return JSON.parse(await readText(location));
}

/**
 * Minimal space-separated AND range check (e.g. ">=0.1.0 <0.4.0") against a
 * launcher version, reusing selfUpdate's X.Y.Z(-pre) comparator so this
 * package doesn't need a semver dependency (it is intentionally
 * dependency-free, see tarball.js).
 */
function satisfiesLauncherRequirement(range, launcherVersion) {
	if (!range) return true;
	const clauses = String(range).trim().split(/\s+/).filter(Boolean);
	for (const clause of clauses) {
		const match = /^(>=|<=|>|<|=)?(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)$/.exec(clause);
		if (!match) throw new Error(`unsupported requiresLauncher clause: ${clause}`);
		const [, op = '=', target] = match;
		const cmp = compareVersions(launcherVersion, target);
		const ok =
			op === '>=' ? cmp >= 0 :
			op === '<=' ? cmp <= 0 :
			op === '>' ? cmp > 0 :
			op === '<' ? cmp < 0 :
			cmp === 0;
		if (!ok) return false;
	}
	return true;
}

function selectArtifact(index, opts) {
	const channel = opts.channel || 'stable';
	const version = opts.version || index.channels?.[channel];
	if (!version) throw new Error(`release channel not found: ${channel}`);
	const release = index.releases?.[version];
	if (!release) throw new Error(`release not found: ${version}`);
	// Optional, additive: only enforced when the release declares
	// `requiresLauncher` AND the caller tells us its own launcher version.
	// Callers that don't pass `launcherVersion` see no behavior change.
	if (release.requiresLauncher && opts.launcherVersion) {
		if (!satisfiesLauncherRequirement(release.requiresLauncher, opts.launcherVersion)) {
			throw new Error(
				`release ${version} requires launcher ${release.requiresLauncher}, running ${opts.launcherVersion}`
			);
		}
	}
	const key = opts.platform || platformKey();
	const artifact = release.platforms?.[key];
	if (!artifact) throw new Error(`release ${version} has no artifact for ${key}`);
	if (!artifact.url || !artifact.sha256) {
		throw new Error(`release ${version} artifact for ${key} must include url and sha256`);
	}
	return {
		version,
		platform: key,
		artifact: { ...artifact, entrypoint: safeRelativeEntrypoint(artifact.entrypoint) }
	};
}

async function downloadVerifiedArtifact(artifact, workDir) {
	const archive = path.join(workDir, path.basename(new URL(artifact.url).pathname) || 'atlas-release.tar.gz');
	await copyArtifact(artifact.url, archive);
	const actual = hashFile(archive);
	if (actual !== artifact.sha256) {
		throw new Error(`checksum mismatch for ${artifact.url}: expected ${artifact.sha256}, got ${actual}`);
	}
	return archive;
}

function extractArchive(archive, dest) {
	// In-process extraction (src/tarball.js): system `tar` on Windows (MSYS/Git
	// GNU tar) parses `C:\...` as a remote-host spec and fails.
	extractTarGz(archive, dest);
}

module.exports = {
	platformKey,
	readReleaseIndex,
	selectArtifact,
	satisfiesLauncherRequirement,
	downloadVerifiedArtifact,
	extractArchive,
	safeRelativeEntrypoint,
};
