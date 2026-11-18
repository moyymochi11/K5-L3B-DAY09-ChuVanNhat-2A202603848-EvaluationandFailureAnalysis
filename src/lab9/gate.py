"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    # 1. Any metric value in pr["metrics"] that is NaN or inf or None
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            problems.append(f"metric {k} is NaN or inf")
        elif v is None:
            problems.append(f"metric {k} is None")

    # 2. len(pr["rows"]) != manifest items x len(manifest seeds)
    manifest = pr.get("manifest") or {}
    expected_count = manifest.get("items", 0) * len(manifest.get("seeds") or [])
    if len(pr.get("rows") or []) != expected_count:
        problems.append(f"row count {len(pr.get('rows') or [])} != manifest items x seeds {expected_count}")

    # Check for duplicate (item_id, seed) in PR
    pr_keys = [(r.get("item_id"), r.get("seed")) for r in pr.get("rows") or []]
    if len(set(pr_keys)) != len(pr_keys):
        problems.append("duplicate (item_id, seed) rows in PR")

    # 3. The (item_id, seed) set of PR differs from the baseline's
    base_keys = set((r.get("item_id"), r.get("seed")) for r in base.get("rows") or [])
    if set(pr_keys) != base_keys:
        problems.append("PR (item_id, seed) set differs from baseline")

    # 4. pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is None
    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures is non-empty ({len(pr['evaluator_failures'])})")

    spec_metric_ids = [m["id"] for m in spec.get("metrics") or [] if m.get("id") in GRADERS or m.get("id") in (pr.get("metrics") or {})]
    for r in pr.get("rows") or []:
        for mid in spec_metric_ids:
            if mid in r and r[mid] is None:
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has None for graded metric {mid}")
                break
        if problems and problems[-1].startswith("row "):
            break

    # 5. Check item's slice tags in PR rows differ from baseline's
    base_slice_map = {(r.get("item_id"), r.get("seed")): sorted(r.get("slices") or []) for r in base.get("rows") or []}
    for r in pr.get("rows") or []:
        k = (r.get("item_id"), r.get("seed"))
        if k in base_slice_map:
            if sorted(r.get("slices") or []) != base_slice_map[k]:
                problems.append(f"slices for {k} altered in PR: {r.get('slices')} != {base_slice_map[k]}")
                break

    # 6. base_spec given and a threshold in spec is LOOSER than in base_spec for same eval-set version
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        base_metric_map = {m["id"]: m for m in base_spec.get("metrics") or []}
        for b_id, b_m in base_metric_map.items():
            matching = [m for m in spec.get("metrics") or [] if m.get("id") == b_id]
            if not matching:
                problems.append(f"metric {b_id} from base_spec is missing in PR spec")
                continue
            cur_m = matching[0]
            if b_m.get("blocking") and not cur_m.get("blocking"):
                problems.append(f"metric {b_id} was blocking in base_spec but non-blocking in PR spec")
            b_th = b_m.get("threshold") or {}
            cur_th = cur_m.get("threshold") or {}
            if "min" in b_th:
                if "min" not in cur_th or cur_th["min"] < b_th["min"]:
                    problems.append(f"metric {b_id} min threshold loosened: {cur_th.get('min')} < {b_th['min']}")
            if "max" in b_th:
                if "max" not in cur_th or cur_th["max"] > b_th["max"]:
                    problems.append(f"metric {b_id} max threshold loosened: {cur_th.get('max')} > {b_th['max']}")
            if "max_increase" in b_th:
                if "max_increase" not in cur_th or cur_th["max_increase"] > b_th["max_increase"]:
                    problems.append(f"metric {b_id} max_increase loosened")
            if b_th.get("no_significant_drop") and not cur_th.get("no_significant_drop"):
                problems.append(f"metric {b_id} dropped no_significant_drop")

        base_slice_list = base_spec.get("slices") or []
        cur_slice_map = {s.get("name"): s for s in spec.get("slices") or []}
        for b_s in base_slice_list:
            s_name = b_s.get("name")
            if s_name not in cur_slice_map:
                problems.append(f"slice {s_name} from base_spec missing in PR spec")
                continue
            c_s = cur_slice_map[s_name]
            if b_s.get("blocking") and not c_s.get("blocking"):
                problems.append(f"slice {s_name} was blocking in base_spec but non-blocking in PR spec")
            if "min" in b_s and ("min" not in c_s or c_s["min"] < b_s["min"]):
                problems.append(f"slice {s_name} min loosened: {c_s.get('min')} < {b_s['min']}")
            if b_s.get("no_significant_drop") and not c_s.get("no_significant_drop"):
                problems.append(f"slice {s_name} dropped no_significant_drop")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap") or {}

    for s in spec.get("slices") or []:
        s_name = s.get("name")
        mid = s.get("metric", "pass_rate")
        min_th = s.get("min")
        blocking = s.get("blocking", True)
        slice_id = f"slice:{s_name}/{mid}"

        a_map = per_item(pr, mid, slice_name=s_name)
        if not a_map:
            continue
        val = sum(a_map.values()) / len(a_map)

        verdict = "ok"
        note = ""

        if min_th is not None and val < min_th:
            verdict = "fail"

        if s.get("no_significant_drop"):
            b_map = per_item(base, mid, slice_name=s_name)
            common_keys = sorted(set(a_map) & set(b_map))
            if common_keys:
                d, lo, hi = stats.paired_bootstrap(
                    [a_map[k] for k in common_keys],
                    [b_map[k] for k in common_keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"

        if verdict != "ok" and blocking:
            blocked.append(slice_id)

        label = "ok" if verdict == "ok" else ("BLOCK" if blocking else "warn")
        th_dict = {k: v for k, v in s.items() if k not in ("name", "metric", "blocking")}
        lines.append(f"  {slice_id:<22} {val:<8.4f} {json.dumps(th_dict):<40} {note:<28} {label}")

    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
