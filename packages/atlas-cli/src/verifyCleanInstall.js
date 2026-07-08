'use strict';

const cmds = require('./commands');

function pushStep(steps, name, ok, detail = '') {
	steps.push({ name, ok, detail });
}

async function verifyCleanInstall(opts) {
	const home = opts.home || cmds.atlasHome();
	const channel = opts.channel || 'stable';
	const platform = opts.platform;
	const steps = [];

	const installResult = await cmds.installFromRelease(home, {
		manifest: opts.manifest,
		channel,
		platform,
		version: opts.version
	});
	pushStep(steps, 'install', true, installResult.version);

	let doctor = cmds.doctor(home);
	pushStep(steps, 'doctor-after-install', doctor.ok, doctor.ok ? 'healthy' : 'unhealthy');
	if (!doctor.ok) return { ok: false, steps };

	const updateResult = await cmds.updateFromRelease(home, {
		manifest: opts.updateManifest,
		channel,
		platform,
		version: opts.updateVersion
	});
	pushStep(steps, 'update', true, `${updateResult.previous ?? '(none)'} -> ${updateResult.version}`);

	doctor = cmds.doctor(home);
	pushStep(steps, 'doctor-after-update', doctor.ok, doctor.ok ? 'healthy' : 'unhealthy');
	if (!doctor.ok) return { ok: false, steps };

	const rollbackResult = cmds.rollback(home, {});
	pushStep(steps, 'rollback', true, `${rollbackResult.rolledBackFrom ?? '(unknown)'} -> ${rollbackResult.version}`);

	doctor = cmds.doctor(home);
	pushStep(steps, 'doctor-after-rollback', doctor.ok, doctor.ok ? 'healthy' : 'unhealthy');
	if (!doctor.ok) return { ok: false, steps };

	cmds.uninstall(home, {});
	pushStep(steps, 'uninstall', true, 'removed installed versions');

	doctor = cmds.doctor(home);
	pushStep(steps, 'doctor-after-uninstall', !doctor.ok, !doctor.ok ? 'no version installed' : 'unexpectedly healthy');

	return { ok: steps.every((s) => s.ok), steps };
}

module.exports = { verifyCleanInstall };
