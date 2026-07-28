'use strict';

// Dependency-free .tar.gz create/extract (Node stdlib only).
//
// Replaces the system `tar` binary: MSYS/Git GNU tar on Windows parses a
// leading `C:` as a remote-host spec ("Cannot connect to C: resolve failed"),
// which broke every release-manifest path on the operator's own OS (see
// .debug/2026-07-08-atlas-cli-windows-tar-defect-and-tree-review.md §1).
//
// Create emits plain ustar (universally readable, including by GNU/bsd tar).
// Extract additionally understands GNU 'L' long-name entries and PAX `path`
// overrides so CI-built artifacts from real tar implementations stay
// consumable. Entries are confined to the destination (no absolute paths, no
// `..` escapes). Archives are release bundles (small), so whole-buffer
// gzip/gunzip is deliberate.

const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');

const BLOCK = 512;

function toPosix(p) {
	return p.split(path.sep).join('/');
}

function writeOctal(buf, offset, length, value) {
	buf.write(value.toString(8).padStart(length - 1, '0'), offset, 'ascii');
}

function splitUstarName(name) {
	if (Buffer.byteLength(name) <= 100) return { name, prefix: '' };
	let splitAt = -1;
	for (let i = 0; i < name.length; i++) {
		if (name[i] !== '/') continue;
		const prefix = name.slice(0, i);
		const rest = name.slice(i + 1);
		if (rest && Buffer.byteLength(prefix) <= 155 && Buffer.byteLength(rest) <= 100) {
			splitAt = i;
		}
	}
	if (splitAt < 0) throw new Error(`path too long for ustar: ${name}`);
	return { prefix: name.slice(0, splitAt), name: name.slice(splitAt + 1) };
}

function header(entryName, size, mode, typeflag, mtimeSeconds, linkName = '') {
	const buf = Buffer.alloc(BLOCK);
	const { name, prefix } = splitUstarName(entryName);
	if (Buffer.byteLength(linkName) > 100) {
		throw new Error(`link target too long for ustar: ${entryName} -> ${linkName}`);
	}
	buf.write(name, 0, 100, 'utf8');
	writeOctal(buf, 100, 8, mode & 0o7777);
	writeOctal(buf, 108, 8, 0); // uid
	writeOctal(buf, 116, 8, 0); // gid
	writeOctal(buf, 124, 12, size);
	writeOctal(buf, 136, 12, mtimeSeconds);
	buf.fill(0x20, 148, 156); // checksum field: spaces while summing
	buf.write(typeflag, 156, 1, 'ascii');
	buf.write(linkName, 157, 100, 'utf8');
	buf.write('ustar', 257, 'ascii'); // magic "ustar\0", version "00"
	buf[262] = 0;
	buf.write('00', 263, 'ascii');
	buf.write(prefix, 345, 155, 'utf8');
	let sum = 0;
	for (let i = 0; i < BLOCK; i++) sum += buf[i];
	buf.write(sum.toString(8).padStart(6, '0'), 148, 'ascii');
	buf[154] = 0;
	buf[155] = 0x20;
	return buf;
}

function archivePathInside(root, candidate) {
	const resolvedRoot = path.resolve(root);
	const resolvedCandidate = path.resolve(candidate);
	return resolvedCandidate === resolvedRoot || resolvedCandidate.startsWith(resolvedRoot + path.sep);
}

function safeRelativeLinkTarget(entryName, linkName) {
	const normalizedEntry = entryName.replace(/\\/g, '/');
	const normalizedLink = linkName.replace(/\\/g, '/');
	if (
		!normalizedLink ||
		path.posix.isAbsolute(normalizedLink) ||
		path.win32.isAbsolute(linkName)
	) {
		throw new Error(`unsafe symlink target in archive: ${entryName} -> ${linkName}`);
	}
	const archiveRoot = '/__atlas_archive_root__';
	const resolved = path.posix.resolve(archiveRoot, path.posix.dirname(normalizedEntry), normalizedLink);
	if (resolved !== archiveRoot && !resolved.startsWith(`${archiveRoot}/`)) {
		throw new Error(`unsafe symlink target in archive: ${entryName} -> ${linkName}`);
	}
	return normalizedLink;
}

function collectEntries(dir, base, entries) {
	for (const name of fs.readdirSync(dir).sort()) {
		const full = path.join(dir, name);
		const st = fs.lstatSync(full);
		const rel = toPosix(path.relative(base, full));
		if (st.isDirectory()) {
			entries.push({ typeflag: '5', rel: `${rel}/`, mode: 0o755, size: 0, mtime: st.mtimeMs });
			collectEntries(full, base, entries);
		} else if (st.isFile()) {
			const exec = (st.mode & 0o111) !== 0;
			entries.push({
				typeflag: '0',
				rel,
				mode: exec ? 0o755 : 0o644,
				size: st.size,
				mtime: st.mtimeMs,
				full,
			});
		} else if (st.isSymbolicLink()) {
			const rawTarget = fs.readlinkSync(full);
			const linkName = safeRelativeLinkTarget(rel, toPosix(rawTarget));
			const resolvedTarget = path.resolve(path.dirname(full), rawTarget);
			if (!archivePathInside(base, resolvedTarget)) {
				throw new Error(`unsafe symlink target in source: ${rel} -> ${rawTarget}`);
			}
			let canonicalTarget;
			try {
				canonicalTarget = fs.realpathSync(full);
			} catch {
				throw new Error(`broken symlink in source: ${rel} -> ${rawTarget}`);
			}
			if (!archivePathInside(base, canonicalTarget)) {
				throw new Error(`unsafe symlink target in source: ${rel} -> ${rawTarget}`);
			}
			entries.push({
				typeflag: '2',
				rel,
				linkName,
				mode: 0o777,
				size: 0,
				mtime: st.mtimeMs,
			});
		}
		// Device nodes and other special filesystem entries are not release content.
	}
}

function createTarGz(sourceDir, outFile) {
	const base = path.resolve(sourceDir);
	if (!fs.existsSync(base)) throw new Error(`source directory not found: ${sourceDir}`);
	const entries = [];
	collectEntries(base, base, entries);
	const chunks = [];
	for (const entry of entries) {
		const mtime = Math.max(0, Math.floor(entry.mtime / 1000));
		chunks.push(header(entry.rel, entry.size, entry.mode, entry.typeflag, mtime, entry.linkName));
		if (entry.typeflag === '0' && entry.size > 0) {
			const content = fs.readFileSync(entry.full);
			chunks.push(content);
			const pad = entry.size % BLOCK;
			if (pad) chunks.push(Buffer.alloc(BLOCK - pad));
		}
	}
	chunks.push(Buffer.alloc(BLOCK * 2)); // end-of-archive
	fs.mkdirSync(path.dirname(path.resolve(outFile)), { recursive: true });
	fs.writeFileSync(outFile, zlib.gzipSync(Buffer.concat(chunks)));
}

function readCString(buf, offset, length) {
	const slice = buf.subarray(offset, offset + length);
	const end = slice.indexOf(0);
	return slice.toString('utf8', 0, end === -1 ? length : end);
}

function parsePaxPath(content) {
	// PAX records: "<len> <key>=<value>\n"
	const text = content.toString('utf8');
	let offset = 0;
	let result = null;
	while (offset < text.length) {
		const space = text.indexOf(' ', offset);
		if (space === -1) break;
		const recordLen = parseInt(text.slice(offset, space), 10);
		if (!Number.isFinite(recordLen) || recordLen <= 0) break;
		const record = text.slice(space + 1, offset + recordLen);
		const eq = record.indexOf('=');
		if (eq !== -1 && record.slice(0, eq) === 'path') {
			result = record.slice(eq + 1).replace(/\n$/, '');
		}
		offset += recordLen;
	}
	return result;
}

function safeTarget(dest, name) {
	const clean = name.replace(/^(\.\/)+/, '');
	if (!clean || clean === '.' || clean === './') return null;
	const destRoot = path.resolve(dest);
	const target = path.resolve(destRoot, clean);
	if (target !== destRoot && !target.startsWith(destRoot + path.sep)) {
		throw new Error(`unsafe path in archive: ${name}`);
	}
	return target;
}

function assertSafeParents(dest, target) {
	const destRoot = path.resolve(dest);
	let cursor = path.dirname(target);
	while (cursor !== destRoot) {
		if (!archivePathInside(destRoot, cursor)) {
			throw new Error(`unsafe extraction parent: ${target}`);
		}
		if (fs.existsSync(cursor) && fs.lstatSync(cursor).isSymbolicLink()) {
			throw new Error(`refusing to extract through symlink parent: ${cursor}`);
		}
		const parent = path.dirname(cursor);
		if (parent === cursor) break;
		cursor = parent;
	}
}

function extractTarGz(archive, dest) {
	fs.mkdirSync(dest, { recursive: true });
	const data = zlib.gunzipSync(fs.readFileSync(archive));
	let offset = 0;
	let overrideName = null;
	const createdSymlinks = [];
	while (offset + BLOCK <= data.length) {
		const block = data.subarray(offset, offset + BLOCK);
		offset += BLOCK;
		if (block.every((b) => b === 0)) break; // end-of-archive
		const size = parseInt(readCString(block, 124, 12).trim() || '0', 8) || 0;
		const content = data.subarray(offset, offset + size);
		offset += Math.ceil(size / BLOCK) * BLOCK;
		const typeflag = String.fromCharCode(block[156] || 0x30); // NUL == regular file
		if (typeflag === 'L') {
			overrideName = readCString(content, 0, content.length);
			continue;
		}
		if (typeflag === 'x') {
			const paxPath = parsePaxPath(content);
			if (paxPath) overrideName = paxPath;
			continue;
		}
		if (typeflag === 'g') continue; // global PAX header — irrelevant here
		const isUstar = readCString(block, 257, 6) === 'ustar';
		const prefix = isUstar ? readCString(block, 345, 155) : '';
		const base = readCString(block, 0, 100);
		const name = overrideName || (prefix ? `${prefix}/${base}` : base);
		overrideName = null;
		const target = safeTarget(dest, name);
		if (target === null) continue;
		assertSafeParents(dest, target);
		if (typeflag === '5' || name.endsWith('/')) {
			fs.mkdirSync(target, { recursive: true });
		} else if (typeflag === '0' || typeflag === '\0') {
			fs.mkdirSync(path.dirname(target), { recursive: true });
			fs.writeFileSync(target, content);
			const mode = parseInt(readCString(block, 100, 8).trim() || '644', 8);
			if (mode & 0o111) {
				try {
					fs.chmodSync(target, 0o755);
				} catch {
					// chmod is advisory on Windows
				}
			}
		} else if (typeflag === '2') {
			const linkName = readCString(block, 157, 100);
			const safeLinkName = safeRelativeLinkTarget(name, linkName);
			fs.mkdirSync(path.dirname(target), { recursive: true });
			fs.symlinkSync(safeLinkName.split('/').join(path.sep), target);
			createdSymlinks.push(target);
		}
		// Hard links and device nodes are not release content.
	}
	for (const linkPath of createdSymlinks) {
		let resolved;
		try {
			resolved = fs.realpathSync(linkPath);
		} catch {
			throw new Error(`broken symlink in archive: ${path.relative(dest, linkPath)}`);
		}
		if (!archivePathInside(dest, resolved)) {
			throw new Error(`unsafe resolved symlink target in archive: ${path.relative(dest, linkPath)}`);
		}
	}
}

module.exports = { createTarGz, extractTarGz };
