/**
 * Dependency-free git branch detection for the donor /vcs endpoint — reads
 * `.git/HEAD` directly (no subprocess, no PATH assumptions on Windows).
 * Handles worktrees (`.git` file with a `gitdir:` pointer) and detached HEAD
 * (returns the short commit id, matching what git status would show).
 */
import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';

function gitDirOf(dotGit: string, containingDir: string): string {
	if (statSync(dotGit).isDirectory()) return dotGit;
	// worktree/submodule: a .git FILE containing "gitdir: <path>"
	const pointer = /^gitdir:\s*(.+)\s*$/m.exec(readFileSync(dotGit, 'utf8'));
	if (!pointer) throw new Error('malformed .git pointer file');
	const target = pointer[1]!.trim();
	return isAbsolute(target) ? target : resolve(containingDir, target);
}

/** The current branch name for *startDir* (walking up), or undefined. */
export function readGitBranch(startDir: string): string | undefined {
	let dir = resolve(startDir);
	for (;;) {
		const dotGit = join(dir, '.git');
		if (existsSync(dotGit)) {
			try {
				const head = readFileSync(join(gitDirOf(dotGit, dir), 'HEAD'), 'utf8').trim();
				const ref = /^ref:\s+refs\/heads\/(.+)$/.exec(head);
				if (ref) return ref[1];
				return head ? head.slice(0, 8) : undefined; // detached HEAD
			} catch {
				return undefined;
			}
		}
		const parent = dirname(dir);
		if (parent === dir) return undefined;
		dir = parent;
	}
}
