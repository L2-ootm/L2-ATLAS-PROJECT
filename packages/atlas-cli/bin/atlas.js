#!/usr/bin/env node
'use strict';

const cmds = require('../src/commands');
const { readInstallState } = require('../src/installState');
const { releaseManifest } = require('../src/config');
const { launchRuntime, resolveRuntimeEntrypoint } = require('../src/launcher');
const { updateLauncher, handoffUpdatedLauncher } = require('../src/selfUpdate');
const { materializePlatformPackage } = require('../src/platformPackage');

function parseArgs(argv) {
	const opts = {};
	let i = 0;
	while (i < argv.length) {
		const arg = argv[i];
		if (arg === '--from') opts.from = argv[++i];
		else if (arg === '--manifest') opts.manifest = argv[++i];
		else if (arg === '--channel') opts.channel = argv[++i];
		else if (arg === '--platform') opts.platform = argv[++i];
		else if (arg === '--version') opts.version = argv[++i];
		else if (arg === '--to') opts.to = argv[++i];
		else if (arg === '--purge') opts.purge = true;
		else if (arg === '--json') opts.json = true;
		else if (arg === '--install-only') opts.installOnly = true;
		else if (arg === '--no-launcher-update') opts.noLauncherUpdate = true;
		i += 1;
	}
	return opts;
}

function printJson(value) {
	console.log(JSON.stringify(value, null, 2));
}

function printChecks(result) {
	for (const check of result.checks) {
		const mark = check.ok ? 'OK  ' : 'FAIL';
		console.log(`  [${mark}] ${check.name}: ${check.detail}`);
	}
	console.log(result.ok ? 'doctor: healthy' : 'doctor: unhealthy');
}

async function main() {
	const [command, ...rest] = process.argv.slice(2);
	const opts = parseArgs(rest);
	const home = cmds.atlasInstallRoot();
	const materialize = () => materializePlatformPackage(home, { env: process.env });

	try {
			switch (command) {
			case 'install': {
				let r;
				if (opts.from) r = cmds.install(home, opts);
				else if (opts.manifest) r = await cmds.installFromRelease(home, opts);
				else r = materialize();
				if (!r) throw new cmds.CliError('platform runtime package is missing; reinstall @systemsl2/atlas');
				if (opts.json) {
					printJson(r);
					break;
				}
				console.log(`installed ${r.version} -> ${r.path}`);
				break;
			}
			case 'update': {
				let launcher = { updated: false };
				if (!opts.noLauncherUpdate && !opts.from && !opts.manifest) launcher = await updateLauncher();
				if (launcher.updated) {
					console.log(`launcher updated ${launcher.current} -> ${launcher.latest}`);
					process.exitCode = handoffUpdatedLauncher(rest.filter((arg) => arg !== '--no-launcher-update'));
					break;
				}
				let r;
				if (opts.from) r = cmds.update(home, opts);
				else if (opts.manifest) r = await cmds.updateFromRelease(home, opts);
				else r = materialize();
				if (!r && !opts.from) {
					const state = readInstallState(home);
					opts.manifest = opts.manifest || state?.releaseManifest || releaseManifest();
					if (opts.manifest) r = await cmds.updateFromRelease(home, opts);
				}
				if (!r) throw new cmds.CliError('updated platform runtime package is missing');
				if (opts.json) {
					printJson({ ...r, launcher });
					break;
				}
				console.log(`updated ${r.previous ?? '(none)'} -> ${r.version}`);
				break;
			}
			case 'rollback': {
				const r = cmds.rollback(home, opts);
				if (opts.json) {
					printJson(r);
					break;
				}
				console.log(`rolled back ${r.rolledBackFrom ?? '(unknown)'} -> ${r.version}`);
				break;
			}
			case 'uninstall': {
				const r = cmds.uninstall(home, opts);
				if (opts.json) {
					printJson(r);
					break;
				}
				console.log(r.removed.length ? `removed:\n  ${r.removed.join('\n  ')}` : 'nothing to remove');
				break;
			}
			case 'doctor': {
				if (!cmds.readCurrent(home)) materialize();
				const r = cmds.doctor(home);
				if (opts.json) printJson(r);
				else printChecks(r);
				if (!r.ok) process.exitCode = 1;
				else if (!opts.installOnly && !opts.json && resolveRuntimeEntrypoint(home)) {
					process.exitCode = launchRuntime(home, ['doctor']);
				}
				break;
			}
			case 'versions': {
				if (!cmds.readCurrent(home)) materialize();
				const list = cmds.versions(home);
				if (opts.json) {
					printJson(list);
					break;
				}
				if (list.length === 0) {
					console.log('no versions installed');
					break;
				}
				for (const v of list) console.log(`${v.current ? '* ' : '  '}${v.version}`);
				break;
			}
			default: {
				if (!cmds.readCurrent(home)) materialize();
				if (cmds.readCurrent(home)) {
					process.exitCode = launchRuntime(home, command ? [command, ...rest] : []);
					break;
				}
				console.log('usage: atlas <install|update|rollback|uninstall|doctor|versions|runtime-command> [--manifest url] [--channel stable] [--version x]');
				console.log('No ATLAS runtime is installed. Run `atlas install`.');
				if (command) process.exitCode = 1;
				break;
			}
		}
	} catch (err) {
		if (err instanceof cmds.CliError) {
			if (opts.json) {
				printJson({ error: { code: 'atlas_cli_error', message: err.message } });
			} else {
				console.error(`error: ${err.message}`);
			}
			process.exitCode = 1;
			return;
		}
		throw err;
	}
}

main().catch((err) => {
	throw err;
});
