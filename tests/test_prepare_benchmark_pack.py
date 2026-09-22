import json

from geometry_guardian.benchmark import initialize_benchmark_pack


def test_initializer_creates_pack_structure(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"fake-image-bytes")

    out = tmp_path / "PACK"
    layout = initialize_benchmark_pack(
        out,
        reference_image=source,
        dataset_id="PACK_TEST",
    )

    assert layout.images_dir.exists()
    assert layout.gt_dir.exists()
    assert layout.manifest_path.exists()
    assert layout.plan_path.exists()

    manifest = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == "PACK_TEST"
    assert manifest["cases"][0]["category"] == "identity"
    assert manifest["cases"][0]["case_id"].endswith("::dev")

    assert (layout.gt_dir / "repetitive_dev.template.json").exists()
    assert (layout.gt_dir / "repetitive_eval.template.json").exists()


def test_initializer_can_include_eval_reference(tmp_path):
    dev = tmp_path / "dev.jpg"
    eva = tmp_path / "eval.jpg"
    dev.write_bytes(b"dev")
    eva.write_bytes(b"eval")

    layout = initialize_benchmark_pack(
        tmp_path / "PACK",
        reference_image=dev,
        evaluation_reference_image=eva,
    )

    manifest = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
    ids = {case["case_id"] for case in manifest["cases"]}
    assert "identity_01::dev" in ids
    assert "identity_02::eval" in ids


def test_initializer_does_not_overwrite_by_default(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"x")
    out = tmp_path / "PACK"

    initialize_benchmark_pack(out, reference_image=source)

    try:
        initialize_benchmark_pack(out, reference_image=source)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected FileExistsError")
