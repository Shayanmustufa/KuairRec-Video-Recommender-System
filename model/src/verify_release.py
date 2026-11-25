"""Verify and extract the published KuaiRec archive without third-party packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from model.src.common import repository_root

RECORD_URL = "https://zenodo.org/records/18164998"
EXPECTED_SIZE = 431_964_858
EXPECTED_MD5 = "261550d472c48eff4990fb13c0e5bcf7"


def verify_and_extract(archive_path: Path, destination: Path, manifest_path: Path) -> dict[str, object]:
    size = archive_path.stat().st_size
    if size != EXPECTED_SIZE:
        raise ValueError(
            f"Archive size mismatch: expected {EXPECTED_SIZE}, received {size}"
        )
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    with archive_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            md5.update(chunk)
            sha256.update(chunk)
    if md5.hexdigest() != EXPECTED_MD5:
        raise ValueError(
            f"Archive MD5 mismatch: expected {EXPECTED_MD5}, received {md5.hexdigest()}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(
            f"Refusing to overwrite non-empty dataset directory: {destination}"
        )
    staging_parent = Path(
        tempfile.mkdtemp(prefix="kuairec-extract-", dir=destination.parent)
    )
    try:
        with zipfile.ZipFile(archive_path) as archive:
            _validate_archive_paths(archive, staging_parent)
            bad_member = archive.testzip()
            if bad_member is not None:
                raise ValueError(f"Corrupt archive member: {bad_member}")
            archive.extractall(staging_parent)
        interaction_files = list(staging_parent.rglob("big_matrix.csv"))
        if len(interaction_files) != 1:
            raise ValueError(
                f"Expected exactly one big_matrix.csv in archive, found {len(interaction_files)}"
            )
        data_root = interaction_files[0].parent
        if destination.exists():
            destination.rmdir()
        shutil.move(str(data_root), str(destination))
    finally:
        if staging_parent.exists():
            shutil.rmtree(staging_parent)

    manifest: dict[str, object] = {
        "dataset": "KuaiRec Dataset with Raw Features",
        "release": "KuaiRec 2.0",
        "zenodo_record": RECORD_URL,
        "doi": "10.5281/zenodo.18164998",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive_path": _relative_path(archive_path),
        "archive_size_bytes": size,
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest(),
        "extracted_data_directory": _relative_path(destination),
        "extracted_files": sorted(
            path.name for path in destination.iterdir() if path.is_file()
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _relative_path(path: Path) -> str:
    root = repository_root()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.name


def _validate_archive_paths(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"Unsafe archive member path: {member.filename}")
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValueError(f"Symbolic links are not allowed in dataset archive: {member.filename}")


def main() -> None:
    root = repository_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=root / "data" / "raw" / "KuaiRec.zip")
    parser.add_argument("--destination", type=Path, default=root / "data" / "raw" / "KuaiRec")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=root / "data" / "processed" / "release_manifest.json",
    )
    args = parser.parse_args()
    print(json.dumps(verify_and_extract(args.archive, args.destination, args.manifest), indent=2))


if __name__ == "__main__":
    main()
