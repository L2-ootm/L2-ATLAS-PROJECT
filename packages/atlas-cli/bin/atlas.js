#!/usr/bin/env node
'use strict';

const cmds = require('../src/commands');

function parseArgs(argv) {
	const opts = {};
	let i = 0;
	while (i < argv.length) {
		const arg = argv[i];
		if (arg === '--from') opts.from = argv[++i];
		else if (arg === '--version') opts.version = argv[++i];
		else if (arg === '--to') opts.to = argv[++i];
		else if (arg === '--purge') opts.purge = true;
		i += 1;
	}
	return opts;
}

function printChecks(result) {
	for (const check of result.checks) {
		const mark = check.ok ? 'OK  ' : 'FAIL';
		console.log(`  [${mark}] ${check.name}: ${check.detail}`);
	}
	console.log(result.ok ? 'doctor: healthy' : 'doctor: unhealthy');
}

function main() {
	const [command, ...rest] = process.argv.slice(2);
	const opts = parseArgs(rest);
	const home = cmds.atlasHome();

	try {
		switch (command) {
			case 'install': {
				const r = cmds.install(home, opts);
				console.log(`installed ${r.version} -> ${r.path}`);
				break;
			}
			case 'update': {
				const r = cmds.update(home, opts);
				console.log(`updated ${r.previous ?? '(none)'} -> ${r.version}`);
				break;
			}
			case 'rollback': {
				const r = cmds.rollback(home, opts);
				console.log(`rolled back ${r.rolledBackFrom ?? '(unknown)'} -> ${r.version}`);
				break;
			}
			case 'uninstall': {
				const r = cmds.uninstall(home, opts);
				console.log(r.removed.length ? `removed:\n  ${r.removed.join('\n  ')}` : 'nothing to remove');
				break;
			}
			case 'doctor': {
				const r = cmds.doctor(home);
				printChecks(r);
				if (!r.ok) process.exitCode = 1;
				break;
			}
			case 'versions': {
				const list = cmds.versions(home);
				if (list.length === 0) {
					console.log('no versions installed');
					break;
				}
				for (const v of list) console.log(`${v.current ? '* ' : '  '}${v.version}`);
				break;
			}
			default:
				console.log('usage: atlas-cli <install|update|rollback|uninstall|doctor|versions> [--from dir] [--version x] [--to x] [--purge]');
				if (command) process.exitCode = 1;
		}
	} catch (err) {
		if (err instanceof cmds.CliError) {
			console.error(`error: ${err.message}`);
			process.exitCode = 1;
			return;
		}
		throw err;
	}
}

main();
