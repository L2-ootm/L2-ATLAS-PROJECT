'use strict';

const fs = require('node:fs');
const path = require('node:path');

const { safeRelativeEntrypoint } = require('./release');

function splitPlatform(value) {
	const match = /^(win32|darwin|linux)-(x64|arm64)$/.exec(value || '');
	if (!match) throw new Error(`unsupported platform package target: ${value}`);
	return { os: match[1], cpu: match[2] };
}

function buildPlatformPackage(opts) {
	const bundleDir = path.resolve(opts.bundleDir || '');
	const outDir = path.resolve(opts.outDir || '');
	const version = opts.version;
	const platform = opts.platform;
	const entrypoint = safeRelativeEntrypoint(opts.entrypoint);
	const target = splitPlatform(platform);
	if (!version) throw new Error('version is required');
	if (!fs.existsSync(bundleDir)) throw new Error(`bundle directory not found: ${bundleDir}`);
	if (!fs.existsSync(path.join(bundleDir, entrypoint))) {
		throw new Error(`runtime entrypoint not found in bundle: ${entrypoint}`);
	}

	const packageDir = path.join(outDir, `atlas-${platform}-${version}`);
	if (!packageDir.startsWith(`${outDir}${path.sep}`)) {
		throw new Error('platform package output escapes the requested output directory');
	}
	fs.rmSync(packageDir, { recursive: true, force: true });
	fs.mkdirSync(packageDir, { recursive: true });
	fs.cpSync(bundleDir, path.join(packageDir, 'runtime'), { recursive: true });
	const metadata = {
		name: `@systemsl2/atlas-${platform}`,
		version,
		private: false,
		license: 'MIT',
		os: [target.os],
		cpu: [target.cpu],
		files: ['runtime'],
		publishConfig: { access: 'public' },
		atlasPlatform: { version, runtimeDir: 'runtime', entrypoint }
	};
	fs.writeFileSync(path.join(packageDir, 'package.json'), JSON.stringify(metadata, null, 2) + '\n');
	return { packageDir, metadata };
}

module.exports = { splitPlatform, buildPlatformPackage };
