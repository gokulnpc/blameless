"""Deterministic scoring helpers: medians, means, percentile ranks (no LLM, no randomness)."""


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return 0.0
    m = n // 2
    return float(xs[m]) if n % 2 else (xs[m - 1] + xs[m]) / 2.0


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def percentile_ranks(values: dict) -> dict:
    """Map {key: number} -> {key: percentile in [0,1]} via average-rank for ties.

    A higher input value yields a higher percentile, so callers must orient every
    metric so that 'higher == better' before calling this.
    """
    items = sorted(values.items(), key=lambda kv: kv[1])
    n = len(items)
    if n == 0:
        return {}
    if n == 1:
        return {items[0][0]: 1.0}
    ranks = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and items[j + 1][1] == items[i][1]:
            j += 1
        avg_pos = (i + j) / 2.0
        pct = avg_pos / (n - 1)
        for k in range(i, j + 1):
            ranks[items[k][0]] = pct
        i = j + 1
    return ranks


def weighted(parts: dict, weights: dict) -> float:
    """Weighted mean of available parts; weights re-normalized over present keys.

    parts: {key: value_in_0_1 or None}. Keys with None ('not measured') are excluded
    and the remaining weights are re-normalized. Returns value in [0,1].
    """
    num = 0.0
    den = 0.0
    for k, w in weights.items():
        v = parts.get(k)
        if v is None:
            continue
        num += w * v
        den += w
    return num / den if den else 0.0


def rank_desc(values: dict) -> dict:
    """Map {key: number} -> {key: 1-based rank}, highest value = rank 1 (ties share)."""
    ordered = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
    ranks = {}
    last_val = None
    last_rank = 0
    for idx, (k, v) in enumerate(ordered, 1):
        if v != last_val:
            last_rank = idx
            last_val = v
        ranks[k] = last_rank
    return ranks
