"""
统计检验（audit E7 / 任务书 §19）。

- bootstrap_ci: 非参数 Bootstrap 95% CI（带随机种子，可复现）。
- mcnemar_test: 配对二分类 McNemar 精确检验（判断两版本差异是否显著）。
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from math import comb


def bootstrap_ci(
    values: Sequence[float],
    stat_fn=None,
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict:
    """对 values 的均值（或 stat_fn）做 Bootstrap 置信区间。

    Returns: {"mean": ..., "ci_low": ..., "ci_high": ..., "n_boot": n_boot}
    """
    if not values:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n_boot": 0}
    stat = (lambda v: sum(v) / len(v)) if stat_fn is None else stat_fn
    rng = random.Random(seed)
    n = len(values)
    observed = stat(values)
    boot_stats = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        boot_stats.append(stat(sample))
    boot_stats.sort()
    lo = int(alpha / 2 * n_boot)
    hi = int((1 - alpha / 2) * n_boot) - 1
    return {
        "mean": round(observed, 4),
        "ci_low": round(boot_stats[max(lo, 0)], 4),
        "ci_high": round(boot_stats[min(hi, n_boot - 1)], 4),
        "n_boot": n_boot,
        "seed": seed,
    }


def mcnemar_test(pairs: Iterable[tuple[bool, bool]]) -> dict:
    """配对 McNemar 精确检验。

    pairs: (version_a_correct, version_b_correct) 序列。
    统计 b = A 错 B 对；c = A 对 B 错。H0: b == c（两版本无差异）。
    返回 p 值（二项精确检验）与方向判断。
    """
    b = c = 0
    for a_ok, b_ok in pairs:
        if not a_ok and b_ok:
            b += 1
        elif a_ok and not b_ok:
            c += 1
    n_discordant = b + c
    if n_discordant == 0:
        return {"p_value": 1.0, "significant": False, "b": 0, "c": 0, "better": "tie"}
    # 精确二项双侧 p = 2 * P(X <= min(b,c)) 其中 X ~ Binomial(n, 0.5)
    k = min(b, c)
    p = 2.0 * sum(comb(n_discordant, i) * (0.5**n_discordant) for i in range(k + 1))
    p = min(p, 1.0)
    better = "a" if c > b else ("b" if b > c else "tie")
    return {
        "p_value": round(p, 6),
        "significant": p < 0.05,
        "b": b,
        "c": c,
        "better": better,
        "n_discordant": n_discordant,
    }
