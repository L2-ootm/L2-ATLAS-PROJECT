'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const zlib = require('node:zlib');
const { spawnSync } = require('node:child_process');
const test = require('node:test');

const { createTarGz, extractTarGz } = require('../src/tarball');

function tempDir(label) {
	return fs.mkdtempSync(path.join(os.tmpdir(), `atlas-tarball-${label}-`));
}

test('tar.gz roundtrip preserves nested files, empty files, and content', () => {
	const src = tempDir('src');
	fs.mkdirSync(path.join(src, 'bin'), { recursive: true });
	fs.mkdirSync(path.join(src, 'lib', 'deep', 'deeper'), { recursive: true });
	fs.writeFileSync(path.join(src, 'bin', 'atlas.js'), '#!/usr/bin/env node\nconsole.log(1);\n');
	fs.writeFileSync(path.join(src, 'lib', 'deep', 'deeper', 'mod.js'), 'module.exports = 42;\n');
	fs.writeFileSync(path.join(src, 'empty.txt'), '');
	fs.writeFileSync(path.join(src, 'manifest.json'), JSON.stringify({ v: '1.0' }));

	const archive = path.join(tempDir('out'), 'bundle.tar.gz');
	createTarGz(src, archive);
	const dest = tempDir('dest');
	extractTarGz(archive, dest);

	assert.equal(
		fs.readFileSync(path.join(dest, 'bin', 'atlas.js'), 'utf8'),
		'#!/usr/bin/env node\nconsole.log(1);\n'
	);
	assert.equal(fs.readFileSync(path.join(dest, 'lib', 'deep', 'deeper', 'mod.js'), 'utf8'), 'module.exports = 42;\n');
	assert.equal(fs.readFileSync(path.join(dest, 'empty.txt'), 'utf8'), '');
	assert.equal(fs.readFileSync(path.join(dest, 'manifest.json'), 'utf8'), JSON.stringify({ v: '1.0' }));
});

test('extract rejects entries that escape the destination', () => {
	// Hand-build a tarball with a `../evil.txt` entry.
	const block = Buffer.alloc(512);
	block.write('../evil.txt', 0, 'utf8');
	block.write('0000644\0', 100, 'ascii');
	block.write('0000000\0', 108, 'ascii');
	block.write('0000000\0', 116, 'ascii');
	block.write('00000000004\0', 124, 'ascii');
	block.write('00000000000\0', 136, 'ascii');
	block.fill(0x20, 148, 156);
	block.write('0', 156, 'ascii');
	block.write('ustar', 257, 'ascii');
	block.write('00', 263, 'ascii');
	let sum = 0;
	for (let i = 0; i < 512; i++) sum += block[i];
	block.write(sum.toString(8).padStart(6, '0'), 148, 'ascii');
	block[154] = 0;
	block[155] = 0x20;
	const content = Buffer.alloc(512);
	content.write('evil', 0, 'utf8');
	const archive = path.join(tempDir('evil'), 'evil.tar.gz');
	fs.writeFileSync(archive, zlib.gzipSync(Buffer.concat([block, content, Buffer.alloc(1024)])));

	const dest = tempDir('evildest');
	assert.throws(() => extractTarGz(archive, dest), /unsafe path/);
	assert.equal(fs.existsSync(path.join(path.dirname(dest), 'evil.txt')), false);
});

test('archives created here are readable by the system tar (when available)', (t) => {
	const probe = spawnSync('tar', ['--version'], { encoding: 'utf8' });
	if (probe.error || probe.status !== 0) {
		t.skip('no system tar on PATH');
		return;
	}
	const src = tempDir('interop-src');
	fs.mkdirSync(path.join(src, 'bin'), { recursive: true });
	fs.writeFileSync(path.join(src, 'bin', 'tool.js'), 'ok\n');
	const outDir = tempDir('interop-out');
	createTarGz(src, path.join(outDir, 'bundle.tar.gz'));
	// Relative paths + cwd so MSYS tar never sees a `C:\` drive prefix.
	const dest = path.join(outDir, 'unpacked');
	fs.mkdirSync(dest, { recursive: true });
	const result = spawnSync('tar', ['-xzf', 'bundle.tar.gz', '-C', 'unpacked'], {
		cwd: outDir,
		encoding: 'utf8',
	});
	assert.equal(result.status, 0, result.stderr || result.stdout);
	assert.equal(fs.readFileSync(path.join(dest, 'bin', 'tool.js'), 'utf8'), 'ok\n');
});

test('extract understands system-tar-created archives (when available)', (t) => {
	const probe = spawnSync('tar', ['--version'], { encoding: 'utf8' });
	if (probe.error || probe.status !== 0) {
		t.skip('no system tar on PATH');
		return;
	}
	const work = tempDir('interop2');
	const src = path.join(work, 'src');
	fs.mkdirSync(path.join(src, 'nested'), { recursive: true });
	fs.writeFileSync(path.join(src, 'nested', 'file.txt'), 'from-system-tar\n');
	const result = spawnSync('tar', ['-czf', 'bundle.tar.gz', '-C', 'src', '.'], {
		cwd: work,
		encoding: 'utf8',
	});
	assert.equal(result.status, 0, result.stderr || result.stdout);
	const dest = path.join(work, 'dest');
	extractTarGz(path.join(work, 'bundle.tar.gz'), dest);
	assert.equal(fs.readFileSync(path.join(dest, 'nested', 'file.txt'), 'utf8'), 'from-system-tar\n');
});
