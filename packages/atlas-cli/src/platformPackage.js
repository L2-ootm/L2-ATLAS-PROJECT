'use strict';

const fs = require('node:fs');
const path = require('node:path');

const cmds = require('./commands');
const { safeRelativeEntrypoint } = require('./release');

function platformPackageName(runtime = process) {
	return `@systemsl2/atlas-${runtime.platform}-${runtime.arch}`;
}

function resolvePackageRoot(options = {}) {
	if (options.env?.ATLAS_PLATFORM_PACKAGE_ROOT) {
		return path.resolve(options.env.ATLAS_PLATFORM_PACKAGE_ROOT);
	}
	const name = platformPackageName(options.runtime || process);
	try {
		return path.dirname(require.resolve(`${name}/package.json`, { paths: [path.join(__dirname, '..')] }));
	} catch {
		return null;
	}
}

function readPlatformPackage(options = {}) {
	const root = resolvePackageRoot(options);
	if (!root) return null;
	const packageFile = path.join(root, 'package.json');
	if (!fs.existsSync(packageFile)) throw new Error(`platform package metadata missing: ${packageFile}`);
	const metadata = JSON.parse(fs.readFileSync(packageFile, 'utf8'));
	const contract = metadata.atlasPlatform;
	if (!contract || contract.version !== metadata.version) {
		throw new Error(`invalid ATLAS platform package contract: ${packageFile}`);
	}
	const runtimeDir = path.resolve(root, contract.runtimeDir || 'runtime');
	const entrypoint = safeRelativeEntrypoint(contract.entrypoint);
	const executable = path.resolve(runtimeDir, entrypoint);
	if (!runtimeDir.startsWith(`${root}${path.sep}`) || !executable.startsWith(`${runtimeDir}${path.sep}`)) {
		throw new Error('platform package paths escape the package root');
	}
	if (!fs.existsSync(executable)) throw new Error(`platform runtime entrypoint missing: ${executable}`);
	return { packageName: metadata.name, version: metadata.version, root, runtimeDir, entrypoint };
}

function materializePlatformPackage(installRoot, options = {}) {
	const platform = readPlatformPackage(options);
	if (!platform) return null;
	return cmds.installBundledPlatform(installRoot, {
		from: platform.runtimeDir,
		version: platform.version,
		entrypoint: platform.entrypoint,
		packageName: platform.packageName
	});
}

module.exports = { platformPackageName, resolvePackageRoot, readPlatformPackage, materializePlatformPackage };
