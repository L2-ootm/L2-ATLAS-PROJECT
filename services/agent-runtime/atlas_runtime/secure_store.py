"""Cross-platform locking and durable owner-only text replacement."""
from __future__ import annotations

import contextlib
import errno
import getpass
import os
import pathlib
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator


class SecureStoreError(RuntimeError):
    """Expected secure-store failure with a stable operator-facing code."""

    def __init__(self, code: str, message: str, remediation: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation


def _is_windows() -> bool:
    return os.name == "nt"


def _windows_identity() -> str:
    domain = os.environ.get("USERDOMAIN", "").strip()
    user = os.environ.get("USERNAME", "").strip() or getpass.getuser()
    return f"{domain}\\{user}" if domain else user


def _try_lock(handle: object) -> bool:
    if _is_windows():
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK, 13, 36}:
                return False
            raise
        return True

    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise
    return True


def _unlock(handle: object) -> None:
    if _is_windows():
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def file_lock(
    lock_path: pathlib.Path,
    timeout_seconds: float = 15.0,
) -> Iterator[None]:
    """Hold an exclusive OS-handle advisory lock for the context lifetime."""
    lock_path = pathlib.Path(lock_path)
    directory_created = not lock_path.parent.exists()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if directory_created:
        harden_owner_directory(lock_path.parent)
    lock_created = not lock_path.exists()
    deadline = time.monotonic() + max(timeout_seconds, 0.0)

    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        if lock_created:
            harden_owner_permissions(lock_path)

        acquired = False
        while not acquired:
            try:
                acquired = _try_lock(handle)
            except OSError as exc:
                raise SecureStoreError(
                    "store_lock_failed",
                    f"could not lock {lock_path.name}",
                    "check ownership and permissions, then retry",
                ) from exc
            if acquired:
                break
            if time.monotonic() >= deadline:
                raise SecureStoreError(
                    "store_lock_timeout",
                    f"timed out waiting for {lock_path.name}",
                    "retry after the other ATLAS process finishes",
                )
            time.sleep(0.01)

        try:
            yield
        finally:
            try:
                _unlock(handle)
            except OSError as exc:
                raise SecureStoreError(
                    "store_unlock_failed",
                    f"could not unlock {lock_path.name}",
                    "restart the current ATLAS process before retrying",
                ) from exc


def _run_icacls(path: pathlib.Path, grant: str) -> None:
    try:
        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                grant,
            ],
            check=True,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SecureStoreError(
            "store_permission_failed",
            f"could not restrict permissions for {path.name}",
            "ensure the current user owns the ATLAS home directory",
        ) from exc


def harden_owner_permissions(path: pathlib.Path) -> None:
    """Restrict a file to the current user."""
    path = pathlib.Path(path)
    if _is_windows():
        _run_icacls(path, f"{_windows_identity()}:(F)")
        return
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        raise SecureStoreError(
            "store_permission_failed",
            f"could not restrict permissions for {path.name}",
            "ensure the current user owns the file",
        ) from exc


def harden_owner_directory(path: pathlib.Path) -> None:
    """Restrict a directory to the current user."""
    path = pathlib.Path(path)
    if _is_windows():
        _run_icacls(path, f"{_windows_identity()}:(OI)(CI)(F)")
        return
    try:
        os.chmod(path, 0o700)
    except OSError as exc:
        raise SecureStoreError(
            "store_permission_failed",
            f"could not restrict permissions for {path.name}",
            "ensure the current user owns the directory",
        ) from exc


def _fsync_parent(path: pathlib.Path) -> None:
    if _is_windows():
        return
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    directory_fd = os.open(str(path), flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def durable_replace_text(path: pathlib.Path, body: str) -> pathlib.Path:
    """Durably replace UTF-8 text using an owner-only exclusive temp file."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    harden_owner_directory(path.parent)
    temp_path = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY

    fd: int | None = None
    try:
        fd = os.open(str(temp_path), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = None
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        harden_owner_permissions(temp_path)
        os.replace(temp_path, path)
        harden_owner_permissions(path)
        _fsync_parent(path.parent)
        return path
    except SecureStoreError:
        raise
    except OSError as exc:
        raise SecureStoreError(
            "store_write_failed",
            f"could not durably replace {path.name}",
            "check disk space, ownership, and filesystem health, then retry",
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)
        with contextlib.suppress(OSError):
            temp_path.unlink()


def preserve_corrupt(path: pathlib.Path) -> pathlib.Path:
    """Copy malformed input to a deterministic sibling for diagnosis."""
    path = pathlib.Path(path)
    preserved = path.with_name(f"{path.name}.corrupt")
    try:
        shutil.copyfile(path, preserved)
        harden_owner_permissions(preserved)
    except SecureStoreError:
        raise
    except OSError as exc:
        raise SecureStoreError(
            "store_preserve_failed",
            f"could not preserve malformed {path.name}",
            "copy the file manually before repairing it",
        ) from exc
    return preserved


__all__ = [
    "SecureStoreError",
    "durable_replace_text",
    "file_lock",
    "harden_owner_directory",
    "harden_owner_permissions",
    "preserve_corrupt",
]
