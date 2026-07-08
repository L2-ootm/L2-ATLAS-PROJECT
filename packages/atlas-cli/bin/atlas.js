#!/usr/bin/env node
'use strict';

const cmds = require('../src/commands');

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
	const home = cmds.atlasHome();

	try {
		switch (command) {
			case 'install': {
				const r = opts.manifest ? await cmds.installFromRelease(home, opts) : cmds.install(home, opts);
				if (opts.json) {
					printJson(r);
					break;
				}
				console.log(`installed ${r.version} -> ${r.path}`);
				break;
			}
			case 'update': {
				const r = opts.manifest ? await cmds.updateFromRelease(home, opts) : cmds.update(home, opts);
				if (opts.json) {
					printJson(r);
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
				const r = cmds.doctor(home);
				if (opts.json) printJson(r);
				else printChecks(r);
				if (!r.ok) process.exitCode = 1;
				break;
			}
			case 'versions': {
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
			default:
				console.log('usage: atlas <install|update|rollback|uninstall|doctor|versions> [--from dir | --manifest url] [--channel stable] [--platform os-arch] [--version x] [--to x] [--purge]');
				if (command) process.exitCode = 1;
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
