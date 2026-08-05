'use strict';

const fs = require('node:fs');
const { spawnSync } = require('node:child_process');

function parseIdentity(stdout) {
	let value;
	try { value = JSON.parse(stdout); }
	catch (error) { throw new Error(`gateway emitted malformed version JSON: ${error.message}`); }
	if (!value || typeof value !== 'object' || Array.isArray(value)) {
		throw new Error('gateway version identity must be a JSON object');
	}
	return value;
}

function verifyIdentity(identity, expected) {
	if (identity.service !== 'atlas-gateway') throw new Error(`unexpected gateway service: ${identity.service}`);
	for (const field of ['release_version', 'component_version', 'build_sha']) {
		if (typeof identity[field] !== 'string' || !identity[field].trim()) {
			throw new Error(`gateway identity is missing ${field}`);
		}
	}
	if (identity.release_version !== expected.releaseVersion) {
		throw new Error(`stale gateway binary: release ${identity.release_version}, expected ${expected.releaseVersion}`);
	}
	if (expected.buildSha && identity.build_sha !== expected.buildSha) {
		throw new Error(`stale gateway binary: build ${identity.build_sha}, expected ${expected.buildSha}`);
	}
	if (!expected.allowDev && identity.build_sha === 'dev') {
		throw new Error('release packaging refuses a gateway with development build identity');
	}
	return identity;
}

function parseArgs(argv) {
	const options = {};
	for (let i = 0; i < argv.length; i += 2) {
		const key = argv[i];
		const value = argv[i + 1];
		if (!key?.startsWith('--') || value === undefined) throw new Error(`invalid argument: ${key || '(missing)'}`);
		options[key.slice(2)] = value;
	}
	return options;
}

function verifyBinary(options) {
	if (!options.binary || !options['release-version']) throw new Error('--binary and --release-version are required');
	if (options['launcher-manifest']) {
		const manifest = JSON.parse(fs.readFileSync(options['launcher-manifest'], 'utf8'));
		if (manifest.version !== options['release-version']) {
			throw new Error(`launcher manifest is ${manifest.version}, expected ${options['release-version']}`);
		}
	}
	const result = spawnSync(options.binary, ['--version', '--json'], {
		encoding: 'utf8', timeout: 10_000, windowsHide: true
	});
	if (result.error) throw new Error(`cannot execute gateway identity probe: ${result.error.message}`);
	if (result.status !== 0) throw new Error(`gateway identity probe exited ${result.status}: ${(result.stderr || '').trim()}`);
	return verifyIdentity(parseIdentity(result.stdout), {
		releaseVersion: options['release-version'],
		buildSha: options['build-sha'],
		allowDev: options['allow-dev'] === 'true'
	});
}

if (require.main === module) {
	try {
		const identity = verifyBinary(parseArgs(process.argv.slice(2)));
		process.stdout.write(`gateway identity verified: ${identity.release_version} (${identity.build_sha})\n`);
	} catch (error) {
		process.stderr.write(`${error.message}\n`);
		process.exitCode = 1;
	}
}

module.exports = { parseIdentity, verifyIdentity, verifyBinary };
