#!/usr/bin/env python3
"""
CloudSentinel HoneyFS Seeder
Exports VirtualFileSystem.generate_realistic_files() output to the honeyfs/
directory for hot-loading via from_honeyfs().

Usage:
    python honeyfs_seed.py [--profile ubuntu-22.04] [--output honeyfs/]
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

# Project root is the cloudsentinel package directory
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = PROJECT_ROOT / "honeyfs"


def is_text_content(content: bytes) -> bool:
    """Check if content is human-readable text (not binary blob)."""
    try:
        content.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def seed_honeyfs(output_dir: Path, os_profile: str = "ubuntu-22.04") -> int:
    """Generate and export a full deceptive VFS to the honeyfs directory."""
    from cloudsentinel.vfs import VirtualFileSystem

    # Generate realistic VFS with all honeytokens
    vfs = VirtualFileSystem.generate_realistic_files(os_profile)

    # Clean existing honeyfs (preserve .gitkeep or custom files)
    if output_dir.exists():
        # Only remove known VFS-generated dirs to avoid nuking custom content
        for subdir in ["etc", "root", "var", "tmp", "proc", "home"]:
            target = output_dir / subdir
            if target.exists():
                shutil.rmtree(target)

    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for entry_path, entry in sorted(vfs._entries.items()):
        rel_path = entry_path.lstrip("/")
        if not rel_path:
            continue

        full_path = output_dir / rel_path

        if entry.get("type") == "dir":
            full_path.mkdir(parents=True, exist_ok=True)
        elif entry.get("type") == "file":
            full_path.parent.mkdir(parents=True, exist_ok=True)
            content = entry.get("content", b"")
            full_path.write_bytes(content)
            count += 1

    print(f"[HoneyFS] Seeded {count} files into {output_dir.resolve()}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed CloudSentinel honeyfs directory")
    parser.add_argument(
        "--profile",
        default="ubuntu-22.04",
        choices=["ubuntu-22.04", "alpine-3.18"],
        help="OS profile for deception (default: ubuntu-22.04)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    count = seed_honeyfs(args.output, args.profile)
    if count > 0:
        print(f"[HoneyFS] Done. {count} deception files ready for from_honeyfs() loading.")
    else:
        print("[HoneyFS] WARNING: No files were seeded. Check VFS generation.")


if __name__ == "__main__":
    main()
