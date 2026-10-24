"""From per-trial logs to one judge row: count successes and trials per build in a JSONL log (one JSON object per
trial) and print the CSV row `quantgate.py judge` reads (tester feedback, 2026-10-24).

The success definition is explicit, because the count depends on it. In this study's FP16 log the live automatic judge
gives VC-025 18/20 vs VC-000 9/10; the pre-registered outcome (offline consensus re-judge AND released AND no human
contact) gives 19/20 vs 10/10, the numbers in the analysis:

  python scripts/quantgate_tally.py artifacts/trials/fp16_unsealed/stress_fp16_F0_sealed.jsonl \
      --candidate VC-025 --reference VC-000 \
      --success artifacts/fp16/rejudge/F0_consensus.json:success_geom --and released --not human_contact

Options:
  --group FIELD        field that names the build (default: cell)
  --success SPEC       FIELD (dotted paths allowed, e.g. judge_auto.success; default: success), or FILE.json:FIELD to
                       read the outcome from a file keyed by --id (e.g. a re-judge); a trial missing there is an error
  --and FIELD          also require FIELD to be true (repeatable)
  --not FIELD          also require FIELD to be false or absent (repeatable)
  --drop FIELD         leave out trials where FIELD is true, e.g. invalid or aborted (default: invalid, aborted)
  --append CSV         append the row to a judge CSV (writes the header if the file is new)
Any judge column can be added with --set column=value (e.g. --set placement_ok=yes --set mode=improvement).
Usage: python scripts/quantgate_tally.py <log.jsonl> [<log.jsonl> ...] --candidate C --reference R [options]"""
import argparse, csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quantgate_judge as qj


class TallyError(ValueError): pass


def get(r, path):
    for k in path.split("."):
        if not isinstance(r, dict) or k not in r: return None
        r = r[k]
    return r


def truth(v, what):
    if isinstance(v, bool): return v
    raise TallyError(f"{what} must be true or false, not {v!r}")


def tally(trials, candidate, reference, group="cell", success="success", require=(), forbid=(), drop=("invalid", "aborted"), id_field="trial_id"):
    ext = None
    if ":" in success and success.split(":", 1)[0].endswith(".json"):
        f, field = success.split(":", 1)
        try: ext = json.load(open(f))
        except FileNotFoundError: raise TallyError(f"outcome file not found: {f}")
    out, seen = {candidate: [0, 0], reference: [0, 0]}, set()
    for i, r in enumerate(trials, 1):
        g = get(r, group)
        seen.add(g)
        if g not in out or any(get(r, d) is True for d in drop): continue
        where = f"trial {get(r, id_field) or i}"
        if ext is not None:
            t = get(r, id_field)
            if t not in ext: raise TallyError(f"{where}: no outcome in {f}")
            ok = truth(get(ext[t], field), f"{where}: {field}")
        else: ok = truth(get(r, success), f"{where}: {success}")
        ok = ok and all(truth(get(r, k), f"{where}: {k}") for k in require) and not any(get(r, k) is True for k in forbid)
        out[g][0] += ok; out[g][1] += 1
    for b in (candidate, reference):
        if out[b][1] == 0: raise TallyError(f"no trials for {b!r} in field {group!r}; builds seen: {sorted(map(str, seen))}")
    return {"candidate": candidate, "reference": reference, "cand_successes": out[candidate][0], "cand_trials": out[candidate][1],
            "ref_successes": out[reference][0], "ref_trials": out[reference][1]}


def read_jsonl(paths):
    rows = []
    for p in paths:
        try: f = open(p)
        except FileNotFoundError: raise TallyError(f"log not found: {p}")
        for n, line in enumerate(f, 1):
            if not line.strip(): continue
            try: rows.append(json.loads(line))
            except json.JSONDecodeError as e: raise TallyError(f"{p} line {n}: not JSON ({e.msg})")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog="quantgate.py tally", description="Count successes per build in JSONL trial logs and print the judge CSV row.")
    ap.add_argument("logs", nargs="+"); ap.add_argument("--candidate", required=True); ap.add_argument("--reference", required=True)
    ap.add_argument("--group", default="cell"); ap.add_argument("--success", default="success"); ap.add_argument("--id", default="trial_id")
    ap.add_argument("--and", dest="require", action="append", default=[]); ap.add_argument("--not", dest="forbid", action="append", default=[])
    ap.add_argument("--drop", action="append"); ap.add_argument("--set", action="append", default=[], metavar="COLUMN=VALUE")
    ap.add_argument("--append", metavar="CSV"); a = ap.parse_args(argv)
    try:
        row = tally(read_jsonl(a.logs), a.candidate, a.reference, a.group, a.success, a.require, a.forbid,
                    ("invalid", "aborted") if a.drop is None else a.drop, a.id)
        for s in a.set:
            k, eq, v = s.partition("=")
            if not eq: raise TallyError(f"--set needs COLUMN=VALUE, not {s!r}")
            row[k.strip()] = v.strip()
        cols = list(qj.REQUIRED) + [c for c in qj.OPTIONAL if c in row]
        qj.check_row({k: str(v) for k, v in row.items()}, "tallied row")   # the same checks judge applies
    except (TallyError, qj.InputError) as e: print(f"error: {e}", file=sys.stderr); return 2
    if a.append:
        new = not os.path.exists(a.append)
        if new: header = list(qj.REQUIRED + qj.OPTIONAL)
        else:
            header = next(csv.reader(open(a.append, encoding="utf-8-sig")), None) or []
            missing = [c for c in cols if c not in header]
            if missing: print(f"error: {a.append} has no column(s) {', '.join(missing)}", file=sys.stderr); return 2
        with open(a.append, "a", newline="") as f:
            w = csv.writer(f)
            if new: w.writerow(header)
            w.writerow([row.get(c, "") for c in header])
        print(f"appended to {a.append}: {row['candidate']} {row['cand_successes']}/{row['cand_trials']} vs {row['reference']} {row['ref_successes']}/{row['ref_trials']}")
    else:
        w = csv.writer(sys.stdout); w.writerow(cols); w.writerow([row[c] for c in cols])
    return 0


if __name__ == "__main__":
    sys.exit(main())
