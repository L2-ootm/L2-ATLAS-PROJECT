"""Dependency-free primitives for safely supervising detached ATLAS services.

This module deliberately does not start or stop processes.  It owns the small,
testable safety boundary that lifecycle wrappers can share: durable launch
records, process-instance observation, diagnostic port probes, bounded locks,
and secret-conscious log diagnostics.
"""

from __future__ import annotations

import contextlib
import ctypes
import dataclasses
import datetime as dt
import hashlib
import json
import ntpath
import os
import pathlib
import re
import socket
import stat
import tempfile
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from typing import IO


SCHEMA_VERSION = 1
_SERVICE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_SENSITIVE_PAIR_RE = re.compile(
    r"(?i)\b(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"token|secret|password|passwd|cookie)\b(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_URL_CREDENTIAL_RE = re.compile(r"(://[^\s:/@]+:)[^\s/@]+(@)")


class ServiceStateError(ValueError):
    """A canonical service record is malformed or unsupported."""


class ServiceLockBusy(TimeoutError):
    """Another owner holds the service lifecycle lock."""


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def atlas_home() -> pathlib.Path:
    """Resolve the owner-local state root at call time, never import time."""
    configured = os.environ.get("ATLAS_HOME", "").strip()
    return pathlib.Path(configured) if configured else pathlib.Path.home() / ".atlas"


def _service_key(service: str) -> str:
    if not isinstance(service, str) or not _SERVICE_RE.fullmatch(service):
        raise ValueError(f"invalid service key {service!r}")
    return service


def state_path(service: str) -> pathlib.Path:
    return atlas_home() / f"{_service_key(service)}.service.json"


def legacy_pid_path(service: str) -> pathlib.Path:
    return atlas_home() / f"{_service_key(service)}.pid"


def log_path(service: str) -> pathlib.Path:
    return atlas_home() / "logs" / f"{_service_key(service)}.log"


def lock_path(service: str) -> pathlib.Path:
    return atlas_home() / "locks" / f"{_service_key(service)}.lock"


def argv_fingerprint(argv: Sequence[object]) -> str:
    """Return a stable digest without retaining raw arguments or credentials."""
    encoded = json.dumps(
        [str(value) for value in argv],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclasses.dataclass(frozen=True, slots=True)
class ServiceLaunchRecord:
    """Canonical identity of one service process instance."""

    service: str
    pid: int
    executable_path: str
    process_creation_time: int
    argv_fingerprint: str
    host: str
    port: int
    launched_at: str
    log_path: str
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _service_key(self.service)
        if self.schema_version != SCHEMA_VERSION:
            raise ServiceStateError(
                f"unsupported service state schema {self.schema_version!r}"
            )
        if isinstance(self.pid, bool) or self.pid <= 0:
            raise ServiceStateError("pid must be a positive integer")
        if not self.executable_path.strip():
            raise ServiceStateError("executable_path must not be blank")
        if (
            isinstance(self.process_creation_time, bool)
            or self.process_creation_time <= 0
        ):
            raise ServiceStateError("process_creation_time must be a positive integer")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.argv_fingerprint):
            raise ServiceStateError("argv_fingerprint must be a SHA-256 fingerprint")
        if not self.host.strip():
            raise ServiceStateError("host must not be blank")
        if isinstance(self.port, bool) or not 1 <= self.port <= 65535:
            raise ServiceStateError("port must be between 1 and 65535")
        if not self.launched_at.strip() or not self.log_path.strip():
            raise ServiceStateError("launch time and log path must not be blank")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "service": self.service,
            "pid": self.pid,
            "executable_path": self.executable_path,
            "process_creation_time": self.process_creation_time,
            "argv_fingerprint": self.argv_fingerprint,
            "host": self.host,
            "port": self.port,
            "launched_at": self.launched_at,
            "log_path": self.log_path,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ServiceLaunchRecord:
        if not isinstance(raw, dict):
            raise ServiceStateError("service state must be a JSON object")
        expected = {field.name for field in dataclasses.fields(cls)}
        missing = expected.difference(raw)
        unknown = set(raw).difference(expected)
        if missing:
            raise ServiceStateError(f"service state is missing {sorted(missing)!r}")
        if unknown:
            raise ServiceStateError(
                f"service state has unknown fields {sorted(unknown)!r}"
            )
        try:
            return cls(
                schema_version=_plain_int(raw["schema_version"], "schema_version"),
                service=_plain_str(raw["service"], "service"),
                pid=_plain_int(raw["pid"], "pid"),
                executable_path=_plain_str(raw["executable_path"], "executable_path"),
                process_creation_time=_plain_int(
                    raw["process_creation_time"], "process_creation_time"
                ),
                argv_fingerprint=_plain_str(
                    raw["argv_fingerprint"], "argv_fingerprint"
                ),
                host=_plain_str(raw["host"], "host"),
                port=_plain_int(raw["port"], "port"),
                launched_at=_plain_str(raw["launched_at"], "launched_at"),
                log_path=_plain_str(raw["log_path"], "log_path"),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ServiceStateError):
                raise
            raise ServiceStateError(str(exc)) from exc


def _plain_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ServiceStateError(f"{field} must be an integer")
    return value


def _plain_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ServiceStateError(f"{field} must be a string")
    return value


def create_launch_record(
    *,
    service: str,
    pid: int,
    executable_path: os.PathLike[str] | str,
    process_creation_time: int,
    argv: Sequence[object],
    host: str,
    port: int,
    sensitive_log_path: os.PathLike[str] | str,
    launched_at: str | None = None,
) -> ServiceLaunchRecord:
    return ServiceLaunchRecord(
        service=service,
        pid=pid,
        executable_path=os.fspath(executable_path),
        process_creation_time=process_creation_time,
        argv_fingerprint=argv_fingerprint(argv),
        host=host,
        port=port,
        launched_at=launched_at or _utc_now(),
        log_path=os.fspath(sensitive_log_path),
    )


def load_launch_record(path: os.PathLike[str] | str) -> ServiceLaunchRecord | None:
    """Read a canonical record; return ``None`` only when it does not exist."""
    record_path = pathlib.Path(path)
    try:
        text = record_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ServiceStateError(f"cannot read service state: {exc}") from exc
    try:
        raw = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ServiceStateError(
            f"service state is not valid UTF-8 JSON: {exc}"
        ) from exc
    return ServiceLaunchRecord.from_dict(raw)


def write_launch_record(
    record: ServiceLaunchRecord,
    path: os.PathLike[str] | str,
    *,
    retries: int = 3,
    retry_delay: float = 0.02,
) -> None:
    """Atomically persist *record*, preserving the previous file on failure."""
    if retries < 0 or retry_delay < 0:
        raise ValueError("retries and retry_delay must be non-negative")
    destination = pathlib.Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            record.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    )
    fd, raw_temp = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temp_path = pathlib.Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _owner_only(temp_path)
        last_error: OSError | None = None
        for attempt in range(retries + 1):
            try:
                os.replace(temp_path, destination)
                _owner_only(destination)
                return
            except OSError as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(retry_delay)
        assert last_error is not None
        raise last_error
    finally:
        with contextlib.suppress(OSError):
            temp_path.unlink()


def read_legacy_pid(path: os.PathLike[str] | str) -> int | None:
    """Best-effort compatibility reader for legacy plain integer PID files."""
    try:
        raw = pathlib.Path(path).read_text(encoding="utf-8").strip()
        pid = int(raw, 10)
    except (FileNotFoundError, OSError, UnicodeError, ValueError):
        return None
    return pid if pid > 0 else None


@dataclasses.dataclass(frozen=True, slots=True)
class ProcessObservation:
    pid: int
    exists: bool
    identity_available: bool
    executable_path: str | None = None
    process_creation_time: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class IdentityComparison:
    matches: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


def _same_executable(expected: str, observed: str) -> bool:
    windows_style = (
        os.name == "nt"
        or bool(re.match(r"^[A-Za-z]:[\\/]", expected))
        or bool(re.match(r"^[A-Za-z]:[\\/]", observed))
        or "\\" in expected
        or "\\" in observed
    )
    if windows_style:
        return ntpath.normcase(ntpath.normpath(expected)) == ntpath.normcase(
            ntpath.normpath(observed)
        )
    return os.path.normpath(expected) == os.path.normpath(observed)


def compare_process_identity(
    record: ServiceLaunchRecord, observation: ProcessObservation
) -> IdentityComparison:
    """Fail closed unless the exact recorded process instance is observable."""
    if observation.pid != record.pid:
        return IdentityComparison(False, "pid_mismatch")
    if not observation.exists:
        return IdentityComparison(False, "process_dead")
    if not observation.identity_available:
        return IdentityComparison(False, "identity_unavailable")
    if observation.executable_path is None or observation.process_creation_time is None:
        return IdentityComparison(False, "identity_incomplete")
    if not _same_executable(record.executable_path, observation.executable_path):
        return IdentityComparison(False, "executable_mismatch")
    if record.process_creation_time != observation.process_creation_time:
        return IdentityComparison(False, "creation_time_mismatch")
    return IdentityComparison(True, "exact_match")


def observe_process(pid: int) -> ProcessObservation:
    """Observe one process instance without shelling out to localized tools."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return ProcessObservation(
            pid=int(pid) if isinstance(pid, int) else -1,
            exists=False,
            identity_available=False,
            error="invalid_pid",
        )
    if os.name == "nt":
        return _observe_process_windows(pid)
    return _observe_process_portable(pid)


def _observe_process_windows(pid: int) -> ProcessObservation:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    get_times = kernel32.GetProcessTimes
    get_times.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    )
    get_times.restype = wintypes.BOOL
    query_image = kernel32.QueryFullProcessImageNameW
    query_image.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    query_image.restype = wintypes.BOOL

    handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        error = ctypes.get_last_error()
        return ProcessObservation(
            pid=pid,
            exists=error not in {87, 1168},
            identity_available=False,
            error=f"winerror:{error}",
        )
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not get_times(handle, creation, exit_time, kernel_time, user_time):
            return ProcessObservation(
                pid=pid,
                exists=True,
                identity_available=False,
                error=f"GetProcessTimes:{ctypes.get_last_error()}",
            )
        capacity = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(capacity.value)
        if not query_image(handle, 0, buffer, ctypes.byref(capacity)):
            return ProcessObservation(
                pid=pid,
                exists=True,
                identity_available=False,
                error=f"QueryFullProcessImageNameW:{ctypes.get_last_error()}",
            )
        creation_value = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return ProcessObservation(
            pid=pid,
            exists=True,
            identity_available=True,
            executable_path=buffer.value,
            process_creation_time=creation_value,
        )
    finally:
        close_handle(handle)


def _observe_process_portable(pid: int) -> ProcessObservation:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return ProcessObservation(pid=pid, exists=False, identity_available=False)
    except PermissionError:
        return ProcessObservation(
            pid=pid, exists=True, identity_available=False, error="access_denied"
        )
    except OSError as exc:
        return ProcessObservation(
            pid=pid, exists=False, identity_available=False, error=type(exc).__name__
        )

    proc = pathlib.Path("/proc") / str(pid)
    try:
        executable = os.readlink(proc / "exe")
        # Field 2 may contain spaces and parentheses. Split only after the final ')'.
        stat_text = (proc / "stat").read_text(encoding="utf-8")
        remainder = stat_text[stat_text.rfind(")") + 2 :].split()
        creation_ticks = int(remainder[19])  # field 22, after removing PID/comm
    except (OSError, UnicodeError, ValueError, IndexError) as exc:
        return ProcessObservation(
            pid=pid,
            exists=True,
            identity_available=False,
            error=f"identity_unavailable:{type(exc).__name__}",
        )
    return ProcessObservation(
        pid=pid,
        exists=True,
        identity_available=True,
        executable_path=executable,
        process_creation_time=creation_ticks,
    )


@dataclasses.dataclass(frozen=True, slots=True)
class PortObservation:
    host: str
    port: int
    listening: bool
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


def observe_port(host: str, port: int, *, timeout: float = 0.2) -> PortObservation:
    """Bounded reachability diagnostic. Never use this as process-stop authority."""
    if not host.strip() or not 1 <= port <= 65535:
        raise ValueError("host and port must identify a valid endpoint")
    if not 0 < timeout <= 2.0:
        raise ValueError("port observation timeout must be in (0, 2.0] seconds")
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return PortObservation(host, port, True)
    except OSError as exc:
        return PortObservation(host, port, False, type(exc).__name__)


@dataclasses.dataclass(frozen=True, slots=True)
class ServiceStatus:
    schema_version: int
    service: str
    state: str
    pid: int | None
    identity: IdentityComparison | None
    process: ProcessObservation | None
    port: PortObservation | None
    remediation: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "service": self.service,
            "state": self.state,
            "pid": self.pid,
            "identity": self.identity.to_dict() if self.identity else None,
            "process": self.process.to_dict() if self.process else None,
            "port": self.port.to_dict() if self.port else None,
            "remediation": self.remediation,
        }


def observe_service(
    record: ServiceLaunchRecord,
    *,
    process_observer: Callable[[int], ProcessObservation] = observe_process,
    port_observer: Callable[..., PortObservation] = observe_port,
    port_timeout: float = 0.2,
) -> ServiceStatus:
    """Build JSON-stable status from independently injectable observations."""
    process = process_observer(record.pid)
    identity = compare_process_identity(record, process)
    try:
        port = port_observer(record.host, record.port, timeout=port_timeout)
    except Exception as exc:  # diagnostics must never become stop authority
        port = PortObservation(record.host, record.port, False, type(exc).__name__)
    if not process.exists:
        state, remediation = (
            "stopped",
            "remove stale state after confirming the PID is dead",
        )
    elif identity.matches:
        state, remediation = "running", None
    elif identity.reason in {"identity_unavailable", "identity_incomplete"}:
        state = "unverifiable"
        remediation = (
            "retain state and inspect the process; do not stop it automatically"
        )
    else:
        state = "identity_mismatch"
        remediation = (
            "retain state; the recorded PID belongs to a different process instance"
        )
    return ServiceStatus(
        schema_version=SCHEMA_VERSION,
        service=record.service,
        state=state,
        pid=record.pid,
        identity=identity,
        process=process,
        port=port,
        remediation=remediation,
    )


def _owner_only(path: pathlib.Path) -> None:
    """Apply the strongest dependency-free owner-only mode available."""
    if os.name == "nt":
        _owner_only_windows(path)
        return
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _owner_only_windows(path: pathlib.Path) -> None:
    """Protect *path* with a DACL granting full access only to its owner."""
    from ctypes import wintypes

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    convert = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    )
    convert.restype = wintypes.BOOL
    set_security = advapi32.SetFileSecurityW
    set_security.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID)
    set_security.restype = wintypes.BOOL
    local_free = kernel32.LocalFree
    local_free.argtypes = (wintypes.HLOCAL,)
    local_free.restype = wintypes.HLOCAL

    descriptor = wintypes.LPVOID()
    # Protected DACL; the Owner Rights SID is the sole principal with full access.
    if not convert("D:P(A;;FA;;;OW)", 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not set_security(os.fspath(path), 0x00000004, descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        local_free(descriptor)


def _rotate_logs(path: pathlib.Path, backups: int) -> None:
    if backups < 1:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
        return
    oldest = path.with_name(f"{path.name}.{backups}")
    with contextlib.suppress(FileNotFoundError):
        oldest.unlink()
    for index in range(backups - 1, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        target = path.with_name(f"{path.name}.{index + 1}")
        with contextlib.suppress(FileNotFoundError):
            os.replace(source, target)
            _owner_only(target)
    if path.exists():
        os.replace(path, path.with_name(f"{path.name}.1"))
        _owner_only(path.with_name(f"{path.name}.1"))


def open_sensitive_log(
    path: os.PathLike[str] | str,
    *,
    max_bytes: int = 1_048_576,
    backups: int = 3,
) -> IO[bytes]:
    """Open an owner-only append log, rotating an already-full log at launch."""
    if max_bytes <= 0 or backups < 0:
        raise ValueError("max_bytes must be positive and backups non-negative")
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _owner_only(target.parent)
    try:
        current_size = target.stat().st_size
    except FileNotFoundError:
        current_size = 0
    if current_size >= max_bytes:
        _rotate_logs(target, backups)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    _owner_only(target)
    return os.fdopen(fd, "ab", buffering=0)


@dataclasses.dataclass(frozen=True, slots=True)
class SanitizedTail:
    text: str
    truncated: bool

    def to_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


def _sanitize_text(text: str, redact_values: Iterable[str]) -> str:
    text = _ANSI_OSC_RE.sub("", text)
    text = _ANSI_CSI_RE.sub("", text)
    text = "".join(
        char
        for char in text
        if char in "\n\t" or (ord(char) >= 32 and ord(char) != 127)
    )
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _SENSITIVE_PAIR_RE.sub(r"\1\2[REDACTED]", text)
    text = _URL_CREDENTIAL_RE.sub(r"\1[REDACTED]\2", text)
    for value in sorted(
        {value for value in redact_values if value}, key=len, reverse=True
    ):
        text = text.replace(value, "[REDACTED]")
    return text


def sanitized_log_tail(
    path: os.PathLike[str] | str,
    *,
    max_bytes: int = 16_384,
    max_lines: int = 80,
    redact_values: Iterable[str] = (),
) -> SanitizedTail:
    """Return a bounded, UTF-8-safe, control-free and redacted diagnostic tail."""
    if max_bytes <= 0 or max_lines <= 0:
        raise ValueError("tail bounds must be positive")
    target = pathlib.Path(path)
    try:
        size = target.stat().st_size
        with target.open("rb") as handle:
            if size > max_bytes:
                handle.seek(-max_bytes, os.SEEK_END)
            raw = handle.read(max_bytes)
    except FileNotFoundError:
        return SanitizedTail("", False)
    truncated = size > len(raw)
    text = raw.decode("utf-8", errors="replace")
    if truncated:
        # A seek can begin inside a line; omit that partial line.
        _, separator, remainder = text.partition("\n")
        if separator:
            text = remainder
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
        truncated = True
    return SanitizedTail(_sanitize_text("\n".join(lines), redact_values), truncated)


@contextlib.contextmanager
def service_lock(
    service: str,
    *,
    timeout: float = 2.0,
    poll_interval: float = 0.025,
    path: os.PathLike[str] | str | None = None,
) -> Iterator[pathlib.Path]:
    """Acquire a bounded owner-local cross-process lock for one service."""
    if timeout < 0 or poll_interval <= 0:
        raise ValueError("timeout must be non-negative and poll_interval positive")
    target = pathlib.Path(path) if path is not None else lock_path(service)
    target.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    fd: int | None = None
    while True:
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ServiceLockBusy(f"service {service!r} is busy") from None
            time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
    try:
        assert fd is not None
        payload = json.dumps({"pid": os.getpid(), "acquired_at": _utc_now()}) + "\n"
        os.write(fd, payload.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = None
        _owner_only(target)
        yield target
    finally:
        if fd is not None:
            os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            target.unlink()
