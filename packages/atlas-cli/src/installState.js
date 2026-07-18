'use strict';

const fs = require('node:fs');
const { installStateFile } = require('./paths');
const { atomicWriteFileSync } = require('./atomicWrite');

function readInstallState(home) {
	const file = installStateFile(home);
	if (!fs.existsSync(file)) return null;
	return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeInstallState(home, state) {
	atomicWriteFileSync(installStateFile(home), JSON.stringify(state, null, 2) + '\n', 'utf8');
}

module.exports = { readInstallState, writeInstallState };
