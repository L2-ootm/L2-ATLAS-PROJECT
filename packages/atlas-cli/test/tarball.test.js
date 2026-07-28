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

function createSymlinkOrSkip(t, target, linkPath) {
	try {
		fs.symlinkSync(target, linkPath);
		return true;
	} catch (error) {
		if (error.code === 'EPERM' || error.code === 'EACCES') {
			t.skip(`symlinks unavailable on this runner: ${error.code}`);
			return false;
		}
		throw error;
	}
}

function tarHeader(name, { type = '0', size = 0, linkName = '' } = {}) {
	const block = Buffer.alloc(512);
	block.write(name, 0, 100, 'utf8');
	block.write('0000644\0', 100, 'ascii');
	block.write('0000000\0', 108, 'ascii');
	block.write('0000000\0', 116, 'ascii');
	block.write(size.toString(8).padStart(11, '0') + '\0', 124, 'ascii');
	block.write('00000000000\0', 136, 'ascii');
	block.fill(0x20, 148, 156);
	block.write(type, 156, 'ascii');
	block.write(linkName, 157, 100, 'utf8');
	block.write('ustar', 257, 'ascii');
	block.write('00', 263, 'ascii');
	let sum = 0;
	for (let i = 0; i < 512; i++) sum += block[i];
	block.write(sum.toString(8).padStart(6, '0'), 148, 'ascii');
	block[154] = 0;
	block[155] = 0x20;
	return block;
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
	const block = tarHeader('../evil.txt', { size: 4 });
	const content = Buffer.alloc(512);
	content.write('evil', 0, 'utf8');
	const archive = path.join(tempDir('evil'), 'evil.tar.gz');
	fs.writeFileSync(archive, zlib.gzipSync(Buffer.concat([block, content, Buffer.alloc(1024)])));

	const dest = tempDir('evildest');
	assert.throws(() => extractTarGz(archive, dest), /unsafe path/);
	assert.equal(fs.existsSync(path.join(path.dirname(dest), 'evil.txt')), false);
});

test('tar.gz roundtrip preserves the runtime python/bin/python3 symlink', (t) => {
	const src = tempDir('python-link-src');
	const bin = path.join(src, 'python', 'bin');
	fs.mkdirSync(bin, { recursive: true });
	fs.writeFileSync(path.join(bin, 'python3.13'), 'embedded-python');
	if (!createSymlinkOrSkip(t, 'python3.13', path.join(bin, 'python3'))) return;

	const archive = path.join(tempDir('python-link-out'), 'bundle.tar.gz');
	createTarGz(src, archive);
	const dest = tempDir('python-link-dest');
	extractTarGz(archive, dest);

	const python3 = path.join(dest, 'python', 'bin', 'python3');
	assert.equal(fs.lstatSync(python3).isSymbolicLink(), true);
	assert.equal(fs.readlinkSync(python3), 'python3.13');
	assert.equal(fs.readFileSync(python3, 'utf8'), 'embedded-python');
});

test('create rejects absolute and escaping symlink targets', (t) => {
	const outside = path.join(tempDir('link-outside'), 'outside.txt');
	fs.writeFileSync(outside, 'outside');

	const absoluteSrc = tempDir('absolute-link-src');
	if (!createSymlinkOrSkip(t, outside, path.join(absoluteSrc, 'absolute-link'))) return;
	assert.throws(
		() => createTarGz(absoluteSrc, path.join(tempDir('absolute-link-out'), 'bundle.tar.gz')),
		/unsafe symlink target/
	);

	const escapingSrc = tempDir('escaping-link-src');
	if (!createSymlinkOrSkip(t, '../outside.txt', path.join(escapingSrc, 'escaping-link'))) return;
	assert.throws(
		() => createTarGz(escapingSrc, path.join(tempDir('escaping-link-out'), 'bundle.tar.gz')),
		/unsafe symlink target/
	);
});

test('extract rejects an archive symlink whose target escapes the destination', () => {
	const block = tarHeader('python/bin/python3', {
		type: '2',
		linkName: '../../../outside-python'
	});
	const archive = path.join(tempDir('evil-link'), 'evil-link.tar.gz');
	fs.writeFileSync(archive, zlib.gzipSync(Buffer.concat([block, Buffer.alloc(1024)])));

	const dest = tempDir('evil-link-dest');
	assert.throws(() => extractTarGz(archive, dest), /unsafe symlink target/);
	assert.equal(fs.existsSync(path.join(dest, 'python', 'bin', 'python3')), false);
});

test('extract rejects an archive symlink with an absolute target', () => {
	const absolute = process.platform === 'win32' ? 'C:\\Windows\\System32' : '/etc/passwd';
	const block = tarHeader('python/bin/python3', {
		type: '2',
		linkName: absolute
	});
	const archive = path.join(tempDir('absolute-link'), 'absolute-link.tar.gz');
	fs.writeFileSync(archive, zlib.gzipSync(Buffer.concat([block, Buffer.alloc(1024)])));

	const dest = tempDir('absolute-link-dest');
	assert.throws(() => extractTarGz(archive, dest), /unsafe symlink target/);
	assert.equal(fs.existsSync(path.join(dest, 'python', 'bin', 'python3')), false);
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
