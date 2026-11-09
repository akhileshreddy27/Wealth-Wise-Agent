"""Percentile ranking shared by stock scoring and fund ranking.

Every factor is turned into a 0..1 percentile *within the peer group*, so a P/E of 25
and a Sharpe of 1.2 become comparable numbers that can be weighted and summed.
"""
from collections.abc import Callable, Sequence
from typing import Any

NEUTRAL = 0.5  # used when a metric is missing or there are no peers to compare against


def percentiles(values: Sequence[float | None], higher_is_better: bool = True) -> list[float | None]:
    """Rank each value against the others: 1.0 = best, 0.0 = worst, ties share the average rank.

    Missing values stay None so the caller can decide how to treat them.
    """
    present = sorted(v for v in values if v is not None)
    n = len(present)
    out: list[float | None] = []
    for v in values:
        if v is None:
            out.append(None)
        elif n == 1:
            out.append(NEUTRAL)
        else:
            below = sum(1 for x in present if x < v)
            equal = sum(1 for x in present if x == v)
            rank = below + (equal - 1) / 2          # 0-based average rank, ascending
            p = rank / (n - 1)
            out.append(round(p if higher_is_better else 1 - p, 4))
    return out


def percentile_table(items: Sequence[Any], metrics: dict[str, tuple[Callable[[Any], float | None], bool]]
                     ) -> list[dict[str, float | None]]:
    """For each item, {metric: percentile} using `metrics = {name: (getter, higher_is_better)}`."""
    table: list[dict[str, float | None]] = [{} for _ in items]
    for name, (get, higher) in metrics.items():
        for row, p in zip(table, percentiles([get(i) for i in items], higher)):
            row[name] = p
    return table


def top_label(p: float, group: str) -> str:
    """0.93 -> 'top 10% of <group>'; 1.0 -> 'best in <group>'."""
    if p == 1:
        return f"best in {group}"
    for cut in (0.05, 0.10, 0.25, 0.33):
        if p >= 1 - cut:
            return f"top {int(cut * 100)}% of {group}"
    return f"above the {group} median"


def bottom_label(p: float, group: str) -> str:
    """0.08 -> 'bottom 10% of <group>'; 0.0 -> 'weakest in <group>'."""
    if p == 0:
        return f"weakest in {group}"
    for cut in (0.05, 0.10, 0.25):
        if p <= cut:
            return f"bottom {int(cut * 100)}% of {group}"
    return f"below the {group} median"
