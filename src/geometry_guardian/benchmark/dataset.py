from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DatasetFileFingerprint:
    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class BenchmarkDatasetLock:
    dataset_id: str
    version: str
    files: tuple[DatasetFileFingerprint, ...]
    manifest_sha256: str


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_payload(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def collect_dataset_files(manifest_path: str | Path) -> list[Path]:
    manifest = Path(manifest_path)
    data = _manifest_payload(manifest)
    base = manifest.parent
    result: list[Path] = [manifest]

    for case in data.get("cases", []):
        for key in ("reference_path", "after_path", "region_gt_path"):
            value = case.get(key)
            if not value:
                continue
            path = Path(value)
            if not path.is_absolute():
                path = base / path
            result.append(path)

    # Stable order and deduplication.
    return sorted(set(path.resolve() for path in result), key=lambda p: str(p))


def create_dataset_lock(
    manifest_path: str | Path,
    *,
    dataset_id: str,
    version: str,
) -> BenchmarkDatasetLock:
    manifest = Path(manifest_path).resolve()
    base = manifest.parent

    files = []
    for path in collect_dataset_files(manifest):
        if not path.exists():
            raise FileNotFoundError(path)
        files.append(
            DatasetFileFingerprint(
                relative_path=str(path.relative_to(base)),
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
            )
        )

    return BenchmarkDatasetLock(
        dataset_id=dataset_id,
        version=version,
        files=tuple(files),
        manifest_sha256=sha256_file(manifest),
    )


def write_dataset_lock(lock: BenchmarkDatasetLock, path: str | Path) -> None:
    payload = {
        "schema_version": "0.1",
        "dataset_id": lock.dataset_id,
        "version": lock.version,
        "manifest_sha256": lock.manifest_sha256,
        "files": [
            {
                "relative_path": item.relative_path,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
            }
            for item in lock.files
        ],
    }
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def verify_dataset_lock(
    manifest_path: str | Path,
    lock_path: str | Path,
) -> list[str]:
    manifest = Path(manifest_path).resolve()
    lock_data = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    base = manifest.parent
    errors: list[str] = []

    actual_manifest_sha = sha256_file(manifest)
    if actual_manifest_sha != lock_data.get("manifest_sha256"):
        errors.append("manifest checksum mismatch")

    for item in lock_data.get("files", []):
        path = base / item["relative_path"]
        if not path.exists():
            errors.append(f"missing file: {item['relative_path']}")
            continue

        actual_sha = sha256_file(path)
        if actual_sha != item["sha256"]:
            errors.append(f"checksum mismatch: {item['relative_path']}")

        actual_size = path.stat().st_size
        if actual_size != item["size_bytes"]:
            errors.append(f"size mismatch: {item['relative_path']}")

    return errors
