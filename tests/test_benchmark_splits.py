from geometry_guardian.benchmark import (
    BenchmarkCase,
    split_cases_by_tag,
    validate_frozen_split,
)


def _case(case_id, category):
    return BenchmarkCase(
        case_id=case_id,
        category=category,
        reference_path="a.png",
        after_path="b.png",
    )


def test_dev_and_eval_split_are_separated():
    cases = [
        _case("identity_01::dev", "identity"),
        _case("identity_02::eval", "identity"),
        _case("night_01::dev", "day_night"),
        _case("night_02::eval", "day_night"),
    ]
    split = split_cases_by_tag(cases)

    assert len(split.development) == 2
    assert len(split.evaluation) == 2
    assert validate_frozen_split(split) == []


def test_eval_must_cover_dev_categories():
    cases = [
        _case("identity_01::dev", "identity"),
        _case("night_01::dev", "day_night"),
        _case("identity_02::eval", "identity"),
    ]
    split = split_cases_by_tag(cases)
    errors = validate_frozen_split(split)
    assert any("day_night" in error for error in errors)
