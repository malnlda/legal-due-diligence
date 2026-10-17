#!/usr/bin/env python3
"""Install or verify this skill in supported agent runtimes."""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Iterable, Mapping, Sequence


SKILL_NAME = "legal-due-diligence"
RUNTIME_ENTRIES = ("SKILL.md", "agents", "references")
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "tests",
}
EXCLUDED_FILES = {".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


class SyncError(RuntimeError):
    """Raised when the package or destination cannot be synchronized safely."""


@dataclass(frozen=True)
class Entry:
    kind: str
    digest: str | None = None


@dataclass(frozen=True)
class Difference:
    kind: str
    path: str


@dataclass(frozen=True)
class Target:
    runtime: str
    path: Path


def _is_excluded(relative_path: Path) -> bool:
    return (
        any(part in EXCLUDED_PARTS for part in relative_path.parts)
        or relative_path.name in EXCLUDED_FILES
        or relative_path.suffix in EXCLUDED_SUFFIXES
    )


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_source_manifest(source_root: Path) -> dict[str, Entry]:
    """Return the self-contained runtime package manifest."""
    source_root = source_root.resolve()
    manifest: dict[str, Entry] = {}

    for entry_name in RUNTIME_ENTRIES:
        entry_path = source_root / entry_name
        if not entry_path.exists():
            raise SyncError(f"required runtime entry is missing: {entry_name}")
        if entry_path.is_symlink():
            raise SyncError(f"runtime entry must not be a symbolic link: {entry_name}")

        candidates: Iterable[Path]
        if entry_path.is_dir():
            candidates = (entry_path, *sorted(entry_path.rglob("*")))
        elif entry_path.is_file():
            candidates = (entry_path,)
        else:
            raise SyncError(f"unsupported runtime entry type: {entry_name}")

        for candidate in candidates:
            relative = candidate.relative_to(source_root)
            if _is_excluded(relative):
                continue
            key = relative.as_posix()
            if candidate.is_symlink():
                raise SyncError(f"runtime package must not contain symbolic links: {key}")
            if candidate.is_dir():
                manifest[key] = Entry("directory")
            elif candidate.is_file():
                manifest[key] = Entry("file", _digest(candidate))
            else:
                raise SyncError(f"unsupported runtime entry type: {key}")

    return manifest


def _scan_target(target: Path) -> dict[str, Entry] | None:
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        return {".": Entry("non-directory")}
    if not target.exists():
        return None

    manifest: dict[str, Entry] = {}
    for root_text, directory_names, file_names in os.walk(target, followlinks=False):
        root = Path(root_text)
        for name in list(directory_names):
            path = root / name
            relative = path.relative_to(target).as_posix()
            if path.is_symlink():
                manifest[relative] = Entry("symbolic-link")
                directory_names.remove(name)
            else:
                manifest[relative] = Entry("directory")
        for name in file_names:
            path = root / name
            relative = path.relative_to(target).as_posix()
            if path.is_symlink():
                manifest[relative] = Entry("symbolic-link")
            elif path.is_file():
                manifest[relative] = Entry("file", _digest(path))
            else:
                manifest[relative] = Entry("other")
    return manifest


def compare_target(source_root: Path, target: Path) -> list[Difference]:
    """Compare a destination with the canonical runtime package."""
    expected = build_source_manifest(source_root)
    actual = _scan_target(target)
    if actual is None:
        return [Difference("missing target", ".")]
    if actual.get(".") == Entry("non-directory"):
        return [Difference("wrong type", ".")]

    differences: list[Difference] = []
    for relative, expected_entry in sorted(expected.items()):
        actual_entry = actual.get(relative)
        if actual_entry is None:
            differences.append(Difference("missing", relative))
        elif actual_entry.kind != expected_entry.kind:
            differences.append(Difference("wrong type", relative))
        elif (
            expected_entry.kind == "file"
            and actual_entry.digest != expected_entry.digest
        ):
            differences.append(Difference("modified", relative))

    for relative in sorted(set(actual) - set(expected)):
        differences.append(Difference("stale", relative))
    return differences


def _remove_path(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _validate_target(source_root: Path, target: Path) -> None:
    source = source_root.resolve()
    destination = target.expanduser().resolve(strict=False)
    if destination == source or source in destination.parents:
        raise SyncError(f"destination must not be the repository or inside it: {target}")


def synchronize_target(
    source_root: Path, target: Path, *, dry_run: bool = False
) -> list[Difference]:
    """Mirror the runtime package into target and return pre-sync differences."""
    source_root = source_root.resolve()
    target = target.expanduser()
    _validate_target(source_root, target)
    differences = compare_target(source_root, target)
    if dry_run or not differences:
        return differences

    expected = build_source_manifest(source_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent)
    )
    backup: Path | None = None
    installed = False

    try:
        for relative, entry in sorted(expected.items()):
            destination = staging / relative
            if entry.kind == "directory":
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_root / relative, destination)

        if target.exists() or target.is_symlink():
            backup = Path(
                tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=target.parent)
            )
            backup.rmdir()
            os.replace(target, backup)
        try:
            os.replace(staging, target)
        except BaseException:
            if backup is not None and not target.exists() and not target.is_symlink():
                os.replace(backup, target)
                backup = None
            raise
        installed = True
    finally:
        _remove_path(staging)
        if installed and backup is not None:
            _remove_path(backup)

    return differences


def _target_list(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    environ: Mapping[str, str],
) -> list[Target]:
    explicit = any(
        (
            args.codex,
            args.codex_skills_dir is not None,
            args.hermes,
            args.hermes_home is not None,
            args.claude,
            args.claude_home is not None,
        )
    )
    targets: list[Target] = []

    if args.codex or args.codex_skills_dir is not None or not explicit:
        default_home = Path(environ.get("HOME", str(Path.home())))
        codex_skills_dir = (
            args.codex_skills_dir or (default_home / ".agents" / "skills")
        ).expanduser()
        targets.append(Target("Codex CLI", codex_skills_dir / SKILL_NAME))

    if args.hermes or args.hermes_home is not None:
        hermes_home_text = (
            str(args.hermes_home)
            if args.hermes_home is not None
            else environ.get("HERMES_HOME")
        )
        if not hermes_home_text:
            parser.error(
                "--hermes requires HERMES_HOME; otherwise pass --hermes-home PATH"
            )
        hermes_home = Path(hermes_home_text).expanduser()
        targets.append(
            Target(
                "Hermes Agent",
                hermes_home / "skills" / "legal" / SKILL_NAME,
            )
        )

    if args.claude or args.claude_home is not None:
        claude_home = (args.claude_home or (Path.home() / ".claude")).expanduser()
        targets.append(Target("Claude Code", claude_home / "skills" / SKILL_NAME))

    paths = [target.path.absolute() for target in targets]
    if len(paths) != len(set(paths)):
        parser.error("runtime destinations must be different")
    return targets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install or verify legal-due-diligence from this repository."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="report drift without writing; exit 1 when drift exists",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="show what synchronization would change without writing",
    )
    parser.add_argument(
        "--codex",
        action="store_true",
        help="select Codex CLI (the default when no target is selected)",
    )
    parser.add_argument(
        "--codex-skills-dir",
        type=Path,
        metavar="PATH",
        help="select Codex CLI with a custom skills directory (default: ~/.agents/skills)",
    )
    parser.add_argument(
        "--hermes",
        action="store_true",
        help="select Hermes Agent and require the HERMES_HOME environment variable",
    )
    parser.add_argument(
        "--hermes-home",
        type=Path,
        metavar="PATH",
        help="select Hermes Agent with an explicit profile home",
    )
    parser.add_argument(
        "--claude",
        action="store_true",
        help="select optional Claude Code target (default home: ~/.claude)",
    )
    parser.add_argument(
        "--claude-home",
        type=Path,
        metavar="PATH",
        help="select optional Claude Code target with a custom home",
    )
    return parser


def _print_differences(differences: Sequence[Difference]) -> None:
    for difference in differences:
        print(f"  {difference.kind}: {difference.path}")


def main(
    argv: Sequence[str] | None = None,
    *,
    source_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source_root = source_root or Path(__file__).resolve().parents[1]
    environ = os.environ if environ is None else environ
    targets = _target_list(args, parser, environ)
    drift_found = False

    try:
        for target in targets:
            differences = compare_target(source_root, target.path)
            print(f"[{target.runtime}] {target.path}")
            if not differences:
                print("  in sync")
                continue

            drift_found = True
            _print_differences(differences)
            if args.check:
                continue
            if args.dry_run:
                print("  would synchronize")
                continue

            synchronize_target(source_root, target.path)
            print("  synchronized")
    except (OSError, SyncError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    return 1 if args.check and drift_found else 0


if __name__ == "__main__":
    raise SystemExit(main())
