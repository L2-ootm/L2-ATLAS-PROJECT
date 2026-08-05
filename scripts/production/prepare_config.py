#!/usr/bin/env python3
"""Write the minimal isolated production-gate config atomically."""

from __future__ import annotations

import argparse
import os
import uuid
from pathlib import Path


def write_config(path: Path, gateway_port: int, cockpit_port: int) -> None:
    content = (
        "schema_version: 2\n"
        "revision: 1\n"
        "gateway:\n"
        f"  rust_port: {gateway_port}\n"
        "cockpit:\n"
        f"  port: {cockpit_port}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--gateway-port", type=int, required=True)
    parser.add_argument("--cockpit-port", type=int, required=True)
    args = parser.parse_args()
    write_config(args.path, args.gateway_port, args.cockpit_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
