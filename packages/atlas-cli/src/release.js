'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { hashFile } = require('./manifest');
const { extractTarGz } = require('./tarball');

function platformKey(runtime = process) {
	return `${runtime.platform}-${runtime.arch}`;
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

function selectArtifact(index, opts) {
	const channel = opts.channel || 'stable';
	const version = opts.version || index.channels?.[channel];
	if (!version) throw new Error(`release channel not found: ${channel}`);
	const release = index.releases?.[version];
	if (!release) throw new Error(`release not found: ${version}`);
	const key = opts.platform || platformKey();
	const artifact = release.platforms?.[key];
	if (!artifact) throw new Error(`release ${version} has no artifact for ${key}`);
	if (!artifact.url || !artifact.sha256) {
		throw new Error(`release ${version} artifact for ${key} must include url and sha256`);
	}
	return { version, platform: key, artifact };
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
	downloadVerifiedArtifact,
	extractArchive,
};
