'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

/**
 * Write a file so a crash mid-write can never leave it truncated/corrupt:
 * write to a sibling temp file, then rename over the target. `fs.rename` is
 * a single filesystem metadata operation on both POSIX and Windows (same
 * volume), so the target always reflects either the old content or the
 * complete new content, never a partial write.
 *
 * Doesn't make multi-file updates transactional (writeCurrent + writeInstallState
 * are still two separate atomic writes, not one) — it only removes the
 * single-file truncation/corruption window that plain writeFileSync leaves open.
 */
function atomicWriteFileSync(filePath, content, encoding = 'utf8') {
	const dir = path.dirname(filePath);
	const tmpPath = path.join(dir, `.${path.basename(filePath)}.${process.pid}-${crypto.randomBytes(4).toString('hex')}.tmp`);
	fs.writeFileSync(tmpPath, content, encoding);
	fs.renameSync(tmpPath, filePath);
}

module.exports = { atomicWriteFileSync };
