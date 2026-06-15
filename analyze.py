#!/usr/bin/env python3
"""Phase 2 — compute impact scores + plain-English evidence -> web/dashboard.json.

Deterministic (no LLM, no randomness). Quality is measured as RATES/MEDIANS so that
high-volume authors do not auto-win; only Process Influence (D5) is allowed to scale
with volume. Scores are RELATIVE to PostHog's active cohort. Signals that cannot be
computed from real data are marked "not measured" and excluded; visible weights are
re-normalized over the dimensions that ARE measured.
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.dataset import is_human, is_posthog_company, load_prs
from lib.github import parse_iso
from lib.scoring import median, percentile_ranks, rank_desc, weighted
from lib import signals as S

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "web" / "dashboard.json"
REPO = "PostHog/posthog"
PR_URL = f"https://github.com/{REPO}/pull/"

RANK_MIN = 3          # engineers with >=3 merged PRs appear in the ranking
NORM_MIN = 3          # normalization cohort (active set is not skewed to one-offs)

# Effective dimension weights. D6 (Issue Discovery) and D7 (Dependency Hygiene) are
# NOT measured (no issue data fetched / needs diff semantics), so the PRD's 7-dimension
# weights are re-normalized over the five measured dimensions (sum of nominal = 90).
DIM_WEIGHTS = {"d1": 30, "d2": 25, "d3": 15, "d4": 15, "d5": 5}
DIM_LABELS = {
    "d1": "PR Reviewability & Intent",
    "d2": "Post-Merge Health",
    "d3": "Requirement-Aligned Tests",
    "d4": "Code Reduction & Cleanup",
    "d5": "Process Influence",
}
SUB_WEIGHTS = {
    "d1": {"size": 25, "scope": 25, "intent": 25, "testing": 12.5, "friction": 12.5},
    "d2": {"clean_churn": 40, "revert_avoid": 30, "fix_forward": 30},
    "d3": {"requirement_linkage": 50, "regression_coverage": 50},
    "d4": {"safe_reduction": 57, "dead_code": 43},
    "d5": {"reviews_given": 40, "centrality": 40, "changes_requested": 20},
}
ASSOC_RANK = {"OWNER": 4, "MEMBER": 3, "COLLABORATOR": 2, "CONTRIBUTOR": 1}


# --------------------------------------------------------------------------- #
# Per-PR derived facts
# --------------------------------------------------------------------------- #
def pr_size(pr):
    return (pr.get("additions") or 0) + (pr.get("deletions") or 0)


def scope_focus(pr):
    dirs = {S.top_level_dir(p) for p in S.files_of(pr)}
    k = len(dirs)
    if k == 0:
        return 0.5
    if k == 1:
        return 1.0
    if k == 2:
        return 0.75
    if k == 3:
        return 0.5
    return max(0.2, 0.5 - (k - 3) * 0.1)


def intent_clarity(pr):
    body = pr.get("bodyText", "") or ""
    described = 1.0 if len(body) >= 200 else (0.5 if len(body) >= 60 else 0.0)
    conv = 1.0 if S.has_conventional_title(pr.get("title", "")) else 0.0
    linked = 1.0 if S.requirement_linked(pr) else 0.0
    return 0.5 * described + 0.25 * conv + 0.25 * linked


def testing_signal(pr):
    if any(S.is_test_path(p) for p in S.files_of(pr)):
        return 1.0
    body = (pr.get("bodyText", "") or "").lower()
    if any(w in body for w in ("test", "screenshot", "qa", "migration", "manually verified")):
        return 0.4
    return 0.0


def is_cleanup(pr):
    ctype = S.conventional_type(pr.get("title", ""))
    if ctype in {"refactor", "chore", "perf"}:
        return True
    t = (pr.get("title", "") or "").lower()
    return any(w in t for w in ("remove", "delete", "deprecat", "cleanup", "clean up",
                                "dead code", "unused", "simplif"))


def review_thread_count(pr):
    return (pr.get("reviewThreads") or {}).get("totalCount", 0)


def human_reviewers(pr, accounts):
    """Distinct human reviewers of a PR and whether each requested changes."""
    out = {}
    for r in ((pr.get("reviews") or {}).get("nodes") or []):
        login = (r.get("author") or {}).get("login")
        if not is_human(login, accounts):
            continue
        cr = (r.get("state") == "CHANGES_REQUESTED")
        out[login] = out.get(login, False) or cr
    return out


# --------------------------------------------------------------------------- #
# Corrective-churn / revert indexing over the full in-window universe
# --------------------------------------------------------------------------- #
W30 = 30 * 86400


def build_indices(universe):
    """Reverse-reference + revert indices.

    Corrective churn is HIGH-CONFIDENCE only: a later bug/fix PR that *explicitly
    references* the original PR (#N) within 30 days. Same-file follow-up is deliberately
    NOT used — in this monorepo hot files (e.g. generated.ts: 714 PRs, snapshots.yml: 453)
    make same-file matching ~62% noise, which the PRD warns against ('same-file follow-up
    != fault; high-risk areas churn more').
    """
    refs_of = {pr["number"]: S.references(pr) for pr in universe}

    referenced_by = defaultdict(list)   # target_num -> [(epoch, qnum, is_fix, is_regression, author)]
    for pr in universe:
        epoch = parse_iso(pr["mergedAt"]).timestamp()
        fix = S.is_bugfix(pr)
        reg = ("regression" in (pr.get("bodyText", "") or "").lower()
               or S.is_revert_pr(pr))
        qa = (pr.get("author") or {}).get("login")
        for tgt in refs_of[pr["number"]]:
            referenced_by[tgt].append((epoch, pr["number"], fix, reg, qa))

    revert_targets = {}
    for pr in universe:
        if S.is_revert_pr(pr):
            tgt = S.revert_target(pr)
            if tgt is not None:
                revert_targets[tgt] = pr["number"]
    return referenced_by, revert_targets


def corrective_followup(pr, referenced_by):
    """(churned, tier, example_pr): a DIFFERENT engineer's fix PR that explicitly references
    this PR within 30 days. Self-fixes are excluded -- responsible fast iteration by the same
    author is not post-merge instability."""
    epoch = parse_iso(pr["mergedAt"]).timestamp()
    author = (pr.get("author") or {}).get("login")
    best = None  # (priority, tier, qnum)
    for qe, qn, qfix, qreg, qa in referenced_by.get(pr["number"], ()):
        if qe <= epoch or qe - epoch > W30 or not qfix:
            continue
        if not qa or qa == author:           # cross-author only
            continue
        cand = (2, "Very high", qn) if qreg else (1, "High", qn)
        if best is None or cand[0] > best[0]:
            best = cand
    if best:
        return True, best[1], best[2]
    return False, None, None


# --------------------------------------------------------------------------- #
# Review graph + PageRank
# --------------------------------------------------------------------------- #
def pagerank(out_edges, nodes, d=0.85, iters=80):
    n = len(nodes)
    if n == 0:
        return {}
    pr = {x: 1.0 / n for x in nodes}
    outsum = {s: sum(w.values()) for s, w in out_edges.items()}
    dangling = [x for x in nodes if outsum.get(x, 0) == 0]
    for _ in range(iters):
        new = {x: (1 - d) / n for x in nodes}
        dmass = d * sum(pr[x] for x in dangling) / n
        for x in nodes:
            new[x] += dmass
        for s, w in out_edges.items():
            if outsum.get(s, 0) == 0:
                continue
            share = d * pr[s] / outsum[s]
            for dst, wt in w.items():
                new[dst] += share * wt
        pr = new
    return pr


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    human_prs, meta, accounts = load_prs(human_only=True)
    universe, _, _ = load_prs(human_only=False)   # later fixers/reverters can be anyone
    cutoff = meta["cutoff"]

    by_author = defaultdict(list)
    for pr in human_prs:
        by_author[(pr["author"] or {})["login"]].append(pr)

    pr_count = {a: len(p) for a, p in by_author.items()}
    cohort = sorted([a for a, c in pr_count.items() if c >= RANK_MIN])
    print(f"Active cohort (>= {RANK_MIN} PRs): {len(cohort)} engineers "
          f"(normalization cohort >= {NORM_MIN}).")

    referenced_by, revert_targets = build_indices(universe)

    # ---- review graph (humans only; reviews on OTHERS' PRs) ----
    reviews_given = defaultdict(int)         # distinct PRs reviewed
    cr_given = defaultdict(int)              # distinct PRs where changes requested
    rev_to_auth = defaultdict(lambda: defaultdict(int))   # reviewer -> author (viz)
    auth_to_rev = defaultdict(lambda: defaultdict(int))   # author -> reviewer (pagerank)
    graph_nodes = set()
    for pr in human_prs:
        author = (pr["author"] or {})["login"]
        for reviewer, cr in human_reviewers(pr, accounts).items():
            if reviewer == author:
                continue
            reviews_given[reviewer] += 1
            if cr:
                cr_given[reviewer] += 1
            rev_to_auth[reviewer][author] += 1
            auth_to_rev[author][reviewer] += 1
            graph_nodes.add(reviewer)
            graph_nodes.add(author)
    centrality = pagerank(auth_to_rev, graph_nodes)

    # ---- per-engineer raw metrics ----
    comp = {}       # login -> raw components (rates as numer/denom, plus specials)
    disp = {}       # login -> display facts for evidence
    for login in cohort:
        prs = by_author[login]
        n = len(prs)
        sizes = [pr_size(p) for p in prs]
        files_each = [(p.get("changedFiles") or 0) for p in prs]
        reviewed = [p for p in prs if review_thread_count(p) > 0 or
                    ((p.get("reviews") or {}).get("totalCount", 0) > 0)]

        churn_hits, revert_hits = [], []
        for p in prs:
            churned, tier, qn = corrective_followup(p, referenced_by)
            if churned:
                churn_hits.append((p["number"], qn, tier))
            if p["number"] in revert_targets:
                revert_hits.append((p["number"], revert_targets[p["number"]]))

        bugfixes = [p for p in prs if S.is_bugfix(p)]
        bf_with_test = [p for p in bugfixes
                        if any(S.is_test_path(f) for f in S.files_of(p))]
        nonrevert = [p for p in prs if not S.is_revert_pr(p)]
        net_neg = [p for p in nonrevert if (p.get("deletions") or 0) > (p.get("additions") or 0)]
        cleanups = [p for p in prs if is_cleanup(p) and
                    (p.get("deletions") or 0) > (p.get("additions") or 0)]
        dep_prs = [p for p in prs if any(S.is_dep_path(f) for f in S.files_of(p))]
        dep_removals = [p for p in dep_prs
                        if (p.get("deletions") or 0) > (p.get("additions") or 0)]

        med_size = median(sizes)
        req_linked = sum(1 for p in prs if S.requirement_linked(p))

        # Shrinkable metrics stored as (numerator, denominator) so they can be
        # regressed toward the cohort prior by sample size; None = not applicable.
        comp[login] = {
            # specials (oriented higher=better; not shrunk: medians/counts)
            "size": -med_size,
            "friction": (-median([review_thread_count(p) for p in reviewed])
                         if reviewed else None),
            "reviews_given": float(reviews_given.get(login, 0)),
            "changes_requested": float(cr_given.get(login, 0)),
            "centrality": float(centrality.get(login, 0.0)),
            "_rates": {
                "scope": (sum(scope_focus(p) for p in prs), n),
                "intent": (sum(intent_clarity(p) for p in prs), n),
                "testing": (sum(testing_signal(p) for p in prs), n),
                "clean_churn": (n - len(churn_hits), n),
                "revert_avoid": (n - len(revert_hits), n),
                "fix_forward": (len(bugfixes), n),
                "requirement_linkage": (req_linked, n),
                "regression_coverage": ((len(bf_with_test), len(bugfixes)) if bugfixes else None),
                "safe_reduction": ((len(net_neg), len(nonrevert)) if nonrevert else None),
                "dead_code": (len(cleanups), n),
            },
        }
        disp[login] = {
            "n": n, "med_size": int(med_size), "med_files": int(median(files_each)),
            "churn_hits": churn_hits, "churn_rate": len(churn_hits) / n,
            "revert_hits": revert_hits, "revert_rate": len(revert_hits) / n,
            "bugfixes": len(bugfixes), "bf_with_test": len(bf_with_test),
            "req_link_rate": req_linked / n,
            "net_neg": net_neg, "cleanups": len(cleanups),
            "dep_prs": len(dep_prs), "dep_removals": len(dep_removals),
            "reviews_given": reviews_given.get(login, 0),
            "cr_given": cr_given.get(login, 0),
            "example_prs": sorted(p["number"] for p in prs)[:3],
            "biggest_reduction": (max(net_neg, key=lambda p: (p.get("deletions") or 0)
                                      - (p.get("additions") or 0)) if net_neg else None),
            "example_bf_test": (bf_with_test[0]["number"] if bf_with_test else None),
        }

    # ---- empirical-Bayes shrinkage: regress each rate toward the cohort prior ----
    # adj = (numer + K*prior) / (denom + K). Small samples (e.g. 7-PR engineers with a
    # lucky 100% rate) are pulled to the cohort mean; engineers with many PRs keep their
    # earned rates. Neutralizes BOTH high-volume and low-volume luck. K=20.
    SHRINK_K = 20
    rate_keys = ["scope", "intent", "testing", "clean_churn", "revert_avoid", "fix_forward",
                 "requirement_linkage", "regression_coverage", "safe_reduction", "dead_code"]
    priors = {}
    for m in rate_keys:
        tot_n = sum(comp[l]["_rates"][m][0] for l in cohort if comp[l]["_rates"].get(m))
        tot_d = sum(comp[l]["_rates"][m][1] for l in cohort if comp[l]["_rates"].get(m))
        priors[m] = (tot_n / tot_d) if tot_d else 0.0
    raw = {}
    for login in cohort:
        r = {k: comp[login][k] for k in
             ("size", "friction", "reviews_given", "changes_requested", "centrality")}
        for m in rate_keys:
            v = comp[login]["_rates"].get(m)
            r[m] = None if v is None else (v[0] + SHRINK_K * priors[m]) / (v[1] + SHRINK_K)
        raw[login] = r

    # ---- percentile-rank each sub-metric across the cohort ----
    sub_pct = defaultdict(dict)   # login -> {submetric: pct}
    all_subs = [s for w in SUB_WEIGHTS.values() for s in w]
    for sub in all_subs:
        vals = {login: raw[login][sub] for login in cohort if raw[login].get(sub) is not None}
        for login, p in percentile_ranks(vals).items():
            sub_pct[login][sub] = p

    # ---- dimension scores + impact ----
    results = {}
    for login in cohort:
        dims = {}
        for d, subw in SUB_WEIGHTS.items():
            parts = {s: sub_pct[login].get(s) for s in subw}
            dims[d] = weighted(parts, subw)        # 0..1
        impact = weighted(dims, DIM_WEIGHTS) * 100.0
        results[login] = {"dims": dims, "impact": impact}

    impact_rank = rank_desc({l: results[l]["impact"] for l in cohort})
    volume_rank = rank_desc({l: float(pr_count[l]) for l in cohort})

    # ---- assemble per-engineer records ----
    engineers = []
    for login in cohort:
        prs = by_author[login]
        assoc = max((p.get("authorAssociation") or "NONE" for p in prs),
                    key=lambda a: ASSOC_RANK.get(a, 0))
        # authorAssociation misclassifies employees with private org membership as
        # CONTRIBUTOR, so combine three approximate signals: a team-level association, a
        # PostHog company field, or being a frequent reviewer (>=3 reviews on others' PRs --
        # external contributors almost never review). Label is approximate context only.
        reviewed_others = reviews_given.get(login, 0)
        is_team = (ASSOC_RANK.get(assoc, 0) >= 2 or reviewed_others >= 3
                   or is_posthog_company(accounts, login))
        acct = accounts.get(login) or {}
        dims = results[login]["dims"]
        contributions = {d: round(dims[d] * DIM_WEIGHTS[d] / sum(DIM_WEIGHTS.values()) * 100, 1)
                         for d in dims}
        strength = max(contributions, key=lambda d: contributions[d])
        engineers.append({
            "login": login,
            "name": acct.get("name") if isinstance(acct, dict) else None,
            "avatar": acct.get("avatar") if isinstance(acct, dict) else None,
            "company": acct.get("company") if isinstance(acct, dict) else None,
            "url": f"https://github.com/{login}",
            "association": assoc,
            "association_label": "team" if is_team else "external",
            "impact_score": round(results[login]["impact"], 1),
            "impact_rank": impact_rank[login],
            "volume_rank": volume_rank[login],
            "pr_count": pr_count[login],
            "primary_strength": DIM_LABELS[strength],
            "primary_strength_dim": strength,
            "sub_scores": {d: {"label": DIM_LABELS[d],
                               "contribution": contributions[d],
                               "max": round(DIM_WEIGHTS[d] / sum(DIM_WEIGHTS.values()) * 100, 1),
                               "percentile": round(dims[d] * 100)}
                           for d in dims},
            "metric_percentiles": {s: round(sub_pct[login].get(s) * 100)
                                   for s in all_subs if sub_pct[login].get(s) is not None},
            "not_measured": ["d6", "d7"] + (
                ["regression_coverage"] if raw[login].get("regression_coverage") is None else []) + (
                ["friction"] if raw[login].get("friction") is None else []),
            "facts": _json_facts(disp[login]),
            "evidence": build_evidence(login, disp[login], impact_rank[login],
                                       volume_rank[login], len(cohort), dims),
        })
    engineers.sort(key=lambda e: e["impact_rank"])

    # ---- review graph for viz (top reviewers by centrality) ----
    top_for_graph = sorted(graph_nodes, key=lambda x: centrality.get(x, 0), reverse=True)[:30]
    node_set = set(top_for_graph)
    graph_edges = []
    for rv in top_for_graph:
        for au, w in rev_to_auth.get(rv, {}).items():
            if au in node_set and w >= 2:
                graph_edges.append({"from": rv, "to": au, "weight": w})
    review_graph = {
        "nodes": [{"login": x, "centrality": round(centrality.get(x, 0) * 1000, 2),
                   "reviews_given": reviews_given.get(x, 0)} for x in top_for_graph],
        "edges": graph_edges,
    }

    dashboard = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": REPO,
        "window": {"from": cutoff, "to": meta["fetched_at"], "days": meta["window_days"]},
        "totals": {
            "merged_prs_all_authors": meta["merged_in_window_all_authors"],
            "merged_prs_humans": meta["merged_in_window_humans"],
            "distinct_human_authors": meta["distinct_human_authors"],
            "non_user_excluded": meta["non_user_excluded"],
            "cohort_size": len(cohort),
        },
        "weights": {DIM_LABELS[d]: round(DIM_WEIGHTS[d] / sum(DIM_WEIGHTS.values()) * 100, 1)
                    for d in DIM_WEIGHTS},
        "methodology": METHODOLOGY,
        "not_measured": NOT_MEASURED,
        "engineers": engineers,
        "review_graph": review_graph,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dashboard, indent=2))
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(engineers)} engineers).")

    print_top5(engineers, volume_rank, cohort, pr_count)


def _json_facts(d):
    return {
        "merged_prs": d["n"], "median_pr_size": d["med_size"],
        "median_files": d["med_files"], "churn_rate_pct": round(d["churn_rate"] * 100, 1),
        "churned_prs": len(d["churn_hits"]), "reverted_prs": len(d["revert_hits"]),
        "bugfix_prs": d["bugfixes"], "bugfix_with_tests": d["bf_with_test"],
        "requirement_linkage_pct": round(d["req_link_rate"] * 100),
        "net_negative_prs": len(d["net_neg"]), "cleanup_prs": d["cleanups"],
        "dependency_prs": d["dep_prs"], "dependency_removals": d["dep_removals"],
        "reviews_given": d["reviews_given"], "changes_requested_given": d["cr_given"],
    }


def _prs(numbers):
    return [{"number": n, "url": f"{PR_URL}{n}"} for n in numbers if n]


def build_evidence(login, d, irank, vrank, cohort_n, dims):
    """3-4 deterministic, data-backed evidence lines with real PR references."""
    ev = []
    n = d["n"]
    ev.append({
        "text": (f"Merged {n} PRs in the window — impact rank #{irank} of {cohort_n} active "
                 f"engineers, #{vrank} by raw PR volume. Typical PR: {d['med_size']} lines "
                 f"across {d['med_files']} files."),
        "prs": _prs(d["example_prs"]),
    })

    # Post-merge health (high-confidence: later fix PR explicitly references the original)
    if d["churn_hits"]:
        cn, qn, tier = d["churn_hits"][0]
        ev.append({
            "text": (f"Post-merge health: {len(d['churn_hits'])} of {n} PRs "
                     f"({round(d['churn_rate']*100,1)}%) were fixed by a DIFFERENT engineer's "
                     f"referencing PR within 30 days; {len(d['revert_hits'])} reverted. "
                     f"e.g. #{cn} → #{qn} ({tier} confidence)."),
            "prs": _prs([cn, qn]),
        })
    else:
        ev.append({
            "text": (f"Post-merge health: across {n} merged PRs, none required a fix from "
                     f"another engineer's referencing PR and {len(d['revert_hits'])} were reverted."),
            "prs": _prs([h[1] for h in d["revert_hits"][:2]]),
        })

    # Tests on bugfixes (or requirement linkage)
    if d["bugfixes"] > 0:
        pct = round(d["bf_with_test"] / d["bugfixes"] * 100)
        ev.append({
            "text": (f"Tests with fixes: {d['bf_with_test']}/{d['bugfixes']} bug/regression PRs "
                     f"({pct}%) shipped a test file; {round(d['req_link_rate']*100)}% of all PRs "
                     f"link a tracked issue."),
            "prs": _prs([d["example_bf_test"]] if d["example_bf_test"] else []),
        })
    else:
        ev.append({
            "text": (f"Requirement linkage: {round(d['req_link_rate']*100)}% of {n} PRs "
                     f"reference a tracked issue (no bug/regression PRs in window)."),
            "prs": [],
        })

    # Review influence
    ev.append({
        "text": (f"Review influence: reviewed {d['reviews_given']} other engineers' PRs "
                 f"({d['cr_given']} with changes requested); review-graph centrality "
                 f"{round(dims['d5']*100)}th percentile."),
        "prs": [],
    })

    # Simplicity (only if notable)
    if d["biggest_reduction"] is not None and len(d["net_neg"]) >= 3:
        br = d["biggest_reduction"]
        net = (br.get("deletions") or 0) - (br.get("additions") or 0)
        ev.append({
            "text": (f"Simplification: {len(d['net_neg'])} net-negative non-revert PRs "
                     f"(e.g. #{br['number']} removed {net} net lines); {d['cleanups']} cleanup PRs."),
            "prs": _prs([br["number"]]),
        })
    return ev[:4]


def print_top5(engineers, volume_rank, cohort, pr_count):
    print("\n" + "=" * 72)
    print("PHASE 2 — TOP 5 BY IMPACT (relative to PostHog's active cohort)")
    print("=" * 72)
    for e in engineers[:5]:
        sb = e["sub_scores"]
        breakdown = " · ".join(f"{DIM_LABELS[d].split()[0]} {sb[d]['contribution']:.0f}/"
                               f"{sb[d]['max']:.0f}" for d in ["d1", "d2", "d3", "d4", "d5"])
        print(f"\n#{e['impact_rank']}  {e['login']}  [{e['association_label']}]  "
              f"impact {e['impact_score']}/100   (volume rank #{e['volume_rank']}, "
              f"{e['pr_count']} PRs)")
        print(f"     primary strength: {e['primary_strength']}")
        print(f"     {breakdown}")
        for line in e["evidence"][:3]:
            print(f"       - {line['text']}")

    impact_top5 = [e["login"] for e in engineers[:5]]
    vol_top5 = [l for l, _ in sorted(pr_count.items(), key=lambda kv: -kv[1])[:5]]
    print("\n" + "-" * 72)
    print("IMPACT vs VOLUME (proof that impact != volume):")
    print(f"  Top 5 by impact: {impact_top5}")
    print(f"  Top 5 by volume: {vol_top5}")
    only_impact = [l for l in impact_top5 if l not in vol_top5]
    print(f"  In impact-top5 but NOT volume-top5: {only_impact}")
    for e in engineers[:5]:
        print(f"    {e['login']}: impact #{e['impact_rank']} vs volume #{e['volume_rank']}")
    print("=" * 72)


METHODOLOGY = (
    "Each engineer with >=3 merged PRs in the 90-day window is scored on five measured "
    "dimensions. Every sub-metric is computed from real PR data as a RATE or MEDIAN (not a "
    "total, except Process Influence which legitimately scales with review volume), then "
    "percentile-ranked across the active cohort. A dimension score is the weighted mean of "
    "its sub-metric percentiles; the impact score is the weighted sum of dimension scores, "
    "scaled to 0-100. Scores are RELATIVE to PostHog's active engineers, not an absolute "
    "grade. Dimensions that cannot be computed from real data are marked 'not measured' and "
    "the visible weights are re-normalized over the five that can. Small-sample rates are "
    "regressed toward the cohort mean (empirical-Bayes shrinkage, K=20) so a handful of lucky "
    "PRs cannot outrank a large body of work. Post-merge corrective churn counts only when a "
    "DIFFERENT engineer's fix PR explicitly references the original within 30 days; self-fixes "
    "and same-file coincidences are deliberately excluded as too noisy to be fair. "
    "'Code Reduction & Cleanup' (D4) measures net code removal and cleanup PRs, NOT general "
    "readability — a low score means the engineer ships additive feature work, not poor quality."
)
NOT_MEASURED = [
    {"dimension": "Issue Discovery, Triage & Resolution (D6, nominal 5%)",
     "reason": "Requires issue-thread text and NLP judgment; issues were not fetched. "
               "Excluded from the total and weights re-normalized."},
    {"dimension": "Dependency & Duplication Hygiene (D7, nominal 5%)",
     "reason": "Needs diff-level semantics to judge justification/duplication. Dependency-file "
               "change counts are shown as context but not scored."},
    {"dimension": "Low noisy-churn / AI-style rewrite (within D1)",
     "reason": "Requires diff-content analysis (similar old/new blocks); not computable from "
               "metadata. D1 sub-weights re-normalized over the measurable sub-metrics."},
    {"dimension": "Behavior-focused assertions, edge cases, test naming (within D3)",
     "reason": "Requires reading test source; only test-file presence on bug/feature PRs and "
               "issue linkage are measured."},
    {"dimension": "Duplicate-logic removal, naming, control-flow, design fit (within D4)",
     "reason": "Requires diff semantics; only safe net-reduction and cleanup PRs are measured."},
    {"dimension": "Substantive-comment / design-input quality (within D5)",
     "reason": "Requires NLP on review comments; measured via review volume, changes-requested, "
               "and review-graph centrality instead."},
]

if __name__ == "__main__":
    main()
