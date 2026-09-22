import cv2
import numpy as np

from geometry_guardian.benchmark import BenchmarkCase, run_benchmark_case
from geometry_guardian.features import (
    Correspondence,
    CorrespondenceSet,
    FeatureProviderInfo,
)


class FakeProvider:
    device = "cpu"

    def match(self, reference_image, after_image):
        h, w = reference_image.shape[:2]
        matches = []
        index = 0
        for y in (0.15, 0.35, 0.60, 0.82):
            for x in (0.08, 0.30, 0.58, 0.85):
                px = x * w
                py = y * h
                matches.append(
                    Correspondence(
                        (px, py),
                        (px + 3, py - 2),
                        score=0.9,
                        reference_feature_id=index,
                        after_feature_id=index,
                    )
                )
                index += 1

        return CorrespondenceSet(
            provider=FeatureProviderInfo(
                "fake-provider",
                detector="fake",
                matcher="fake",
            ),
            reference_image_size=(w, h),
            after_image_size=(w, h),
            correspondences=matches,
        )


def test_runtime_harness_reads_images_and_reports(tmp_path):
    image = np.zeros((200, 300, 3), dtype=np.uint8)
    ref = tmp_path / "ref.png"
    aft = tmp_path / "aft.png"
    cv2.imwrite(str(ref), image)
    cv2.imwrite(str(aft), image)

    result = run_benchmark_case(
        FakeProvider(),
        BenchmarkCase(
            case_id="identity",
            category="identity",
            reference_path=str(ref),
            after_path=str(aft),
            expected_geometry_change=False,
        ),
        max_translation_px=10,
    )

    assert result.provider_name == "fake-provider"
    assert result.elapsed_ms >= 0
    assert result.peak_vram_mb is None
    assert result.metrics.match_count == 16
    payload = result.to_dict()
    assert payload["case"]["case_id"] == "identity"
    assert payload["runtime"]["elapsed_ms"] >= 0
