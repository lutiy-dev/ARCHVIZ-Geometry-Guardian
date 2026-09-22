from __future__ import annotations

from dataclasses import dataclass

from .runtime import BenchmarkCase


@dataclass(frozen=True, slots=True)
class BenchmarkSplit:
    development: tuple[BenchmarkCase, ...]
    evaluation: tuple[BenchmarkCase, ...]


def split_cases_by_tag(
    cases: list[BenchmarkCase],
    *,
    development_suffix: str = "::dev",
    evaluation_suffix: str = "::eval",
) -> BenchmarkSplit:
    development = []
    evaluation = []

    for case in cases:
        if case.case_id.endswith(development_suffix):
            development.append(case)
        elif case.case_id.endswith(evaluation_suffix):
            evaluation.append(case)

    return BenchmarkSplit(
        development=tuple(development),
        evaluation=tuple(evaluation),
    )


def validate_frozen_split(split: BenchmarkSplit) -> list[str]:
    errors: list[str] = []

    if not split.development:
        errors.append("development split is empty")
    if not split.evaluation:
        errors.append("evaluation split is empty")

    dev_categories = {case.category for case in split.development}
    eval_categories = {case.category for case in split.evaluation}
    missing_from_eval = dev_categories - eval_categories
    if missing_from_eval:
        errors.append(
            "evaluation split misses development categories: "
            + ", ".join(sorted(missing_from_eval))
        )

    return errors
