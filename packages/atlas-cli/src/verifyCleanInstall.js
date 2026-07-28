'use strict';

const cmds = require('./commands');

function pushStep(steps, name, ok, detail = '') {
	steps.push({ name, ok, detail });
}

function pushActivationStep(steps, name, result, detail) {
	const migrationsOk = result?.migrations?.ok === true;
	pushStep(
		steps,
		name,
		migrationsOk,
		migrationsOk ? detail : `required migrations failed: ${result?.migrations?.error || 'missing migration result'}`
	);
	return migrationsOk;
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
	if (!pushActivationStep(steps, 'install', installResult, installResult.version)) {
		return { ok: false, steps };
	}

	let doctor = cmds.doctor(home);
	pushStep(steps, 'doctor-after-install', doctor.ok, doctor.ok ? 'healthy' : 'unhealthy');
	if (!doctor.ok) return { ok: false, steps };

	const updateResult = await cmds.updateFromRelease(home, {
		manifest: opts.updateManifest,
		channel,
		platform,
		version: opts.updateVersion
	});
	if (!pushActivationStep(
		steps,
		'update',
		updateResult,
		`${updateResult.previous ?? '(none)'} -> ${updateResult.version}`
	)) {
		return { ok: false, steps };
	}

	doctor = cmds.doctor(home);
	pushStep(steps, 'doctor-after-update', doctor.ok, doctor.ok ? 'healthy' : 'unhealthy');
	if (!doctor.ok) return { ok: false, steps };

	const rollbackResult = cmds.rollback(home, {});
	if (!pushActivationStep(
		steps,
		'rollback',
		rollbackResult,
		`${rollbackResult.rolledBackFrom ?? '(unknown)'} -> ${rollbackResult.version}`
	)) {
		return { ok: false, steps };
	}

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
