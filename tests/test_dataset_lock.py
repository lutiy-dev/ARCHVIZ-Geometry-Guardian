import json

from geometry_guardian.benchmark import (
    create_dataset_lock,
    verify_dataset_lock,
    write_dataset_lock,
)


def test_dataset_lock_detects_mutation(tmp_path):
    ref = tmp_path / "ref.png"
    aft = tmp_path / "aft.png"
    ref.write_bytes(b"reference")
    aft.write_bytes(b"after")

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "identity::dev",
                        "category": "identity",
                        "reference_path": "ref.png",
                        "after_path": "aft.png",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    lock = create_dataset_lock(
        manifest,
        dataset_id="test-pack",
        version="0.1.0",
    )
    lock_path = tmp_path / "lock.json"
    write_dataset_lock(lock, lock_path)

    assert verify_dataset_lock(manifest, lock_path) == []

    aft.write_bytes(b"changed")
    errors = verify_dataset_lock(manifest, lock_path)
    assert any("aft.png" in error for error in errors)
