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
  --id FIELD           unique trial id (default: trial_id; with the log's `session` field when present). A trial
                       that appears twice, in one file or across files, or a file given twice, stops with exit 2
  --append CSV         append the row to a judge CSV (writes the header if the file is new)
  --placement SPEC     FIELD or FILE.json:FIELD (like --success), the placement error per successful trial: sets placement_ok by the study's placement rule (E2: mean
                       error of candidate minus reference, 97.5% bootstrap, yes if below --placement-tol, default 5)
  --missing RULE       a null or missing outcome: error (default), fail or drop. Decide it from the source's definition
  --pair FIELD         paired design: the field naming the same task across builds; see judge's `design` column
  --engine FILE        the candidate's engine: writes its sha256 to engine_sha256, so preflight can tie the row to it
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


def name(v):
    """Build names are compared as text, so a log's 3 matches the command line's "3"; booleans and empty values are refused."""
    return None if v is None or isinstance(v, bool) or v == "" else str(v)


def tally(trials, candidate, reference, group="cell", success="success", require=(), forbid=(), drop=("invalid", "aborted"), id_field="trial_id",
          placement=None, missing="error", pair=None, notes=None):
    """missing: what a trial whose outcome is null or absent means. error (default) stops; fail counts it as a failure;
    drop leaves it out. Decide it from the source's own definition and write it down, since it changes the count.
    pair: the field linking the same task across builds (a paired design): reported, and marked design=paired."""
    notes = [] if notes is None else notes
    def source(spec, what):   # FIELD, or FILE.json:FIELD keyed by trial id
        if spec and ":" in spec and spec.split(":", 1)[0].endswith(".json"):
            f, fld = spec.split(":", 1)
            try: return json.load(open(f)), f, fld
            except FileNotFoundError: raise TallyError(f"{what} file not found: {f}")
        return None, None, spec
    ext, f, field = source(success, "outcome")
    pext, pf, pfield = source(placement, "placement")
    candidate, reference = str(candidate), str(reference)
    out, seen, place = {candidate: [0, 0], reference: [0, 0]}, {}, {candidate: [], reference: []}
    n_missing, pairs = 0, {candidate: {}, reference: {}}
    for i, r in enumerate(trials, 1):
        raw = get(r, group); g = name(raw)
        seen.setdefault(g, set()).add(type(raw).__name__)
        if len(seen[g]) > 1: raise TallyError(f"build {g!r} appears in field {group!r} both as {' and '.join(sorted(seen[g]))}; make the names one type")
        if g not in out or any(get(r, d) is True for d in drop): continue
        where = f"trial {get(r, id_field) or i}"
        if ext is not None:
            t = get(r, id_field)
            if t not in ext: raise TallyError(f"{where}: no outcome in {f}")
            ok = truth(get(ext[t], field), f"{where}: {field}")
        else:
            v = get(r, success)
            if v is None:
                if missing == "drop": n_missing += 1; continue
                if missing == "fail": n_missing += 1; v = False
                else: raise TallyError(f"{where}: {success} is null or missing. Decide what that means in this source (a failure, "
                                       f"or not run) and say so: --missing fail or --missing drop")
            ok = truth(v, f"{where}: {success}")
        ok = ok and all(truth(get(r, k), f"{where}: {k}") for k in require) and not any(get(r, k) is True for k in forbid)
        out[g][0] += ok; out[g][1] += 1
        if pair:
            pk = get(r, pair)
            if pk in (None, ""): raise TallyError(f"{where}: no {pair!r} to pair on")
            pairs[g][pk] = pairs[g].get(pk, 0) + 1
        if placement and ok:   # placement error is measured on successful trials only, as in the study (E2)
            if pext is not None:
                t = get(r, id_field)
                if t not in pext: raise TallyError(f"{where}: no placement in {pf}")
                v = get(pext[t], pfield)
            else: v = get(r, pfield)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 0: raise TallyError(f"{where}: {pfield} must be a non-negative number on a successful trial, not {v!r}")
            place[g].append(float(v))
    for b in (candidate, reference):
        if out[b][1] == 0:
            kinds = ", ".join(f"{k!r} ({'/'.join(sorted(t))})" for k, t in sorted(seen.items(), key=lambda x: str(x[0])))
            raise TallyError(f"no trials for {b!r} in field {group!r}; builds seen: {kinds}")
    if missing != "error" and n_missing: notes.append(f"{n_missing} trial(s) with a null or missing {success} {'counted as failures' if missing == 'fail' else 'left out'} (--missing {missing})")
    if pair:
        both = set(pairs[candidate]) & set(pairs[reference]); once = all(v == 1 for b in pairs for v in pairs[b].values())
        notes.append(f"paired on {pair!r}: {len(both)} pairs with both builds, {len(set(pairs[candidate]) ^ set(pairs[reference]))} unpaired"
                     + ("" if once else "; some pair ids repeat within a build"))
    row = {"candidate": candidate, "reference": reference, "cand_successes": out[candidate][0], "cand_trials": out[candidate][1],
            "ref_successes": out[reference][0], "ref_trials": out[reference][1]}
    if placement: row["_placement"] = place
    if pair: row["design"] = "paired"
    return row


def placement_check(place, candidate, reference, tol_px=5.0, n_boot=10000):
    """The study's placement rule (E2): degradation = mean placement error of the candidate minus the reference, on
    successful trials, with a 97.5% unpaired percentile bootstrap (g6_analysis.boot_ci, fixed seed). yes if the upper
    bound is below tol_px, no if the lower bound is above it, empty (undecided, so judge holds) otherwise."""
    from g6_analysis import boot_ci, aep_decision
    a, b = place[candidate], place[reference]
    if len(a) < 2 or len(b) < 2: return "", f"placement: too few successful trials with a measurement ({len(a)} vs {len(b)}); left undecided"
    d, lo, hi = boot_ci(a, b, lambda x: float(sum(x) / len(x)), n_boot, "QuantGate/tally/E2", 0.975)
    dec = aep_decision(lo, hi, tol_px)
    ok = {"tolerance_compatible": "yes", "materially_degraded": "no"}.get(dec, "")
    return ok, f"placement: degradation {d:+.1f} px, 97.5% interval [{lo:+.1f}, {hi:+.1f}] vs tolerance {tol_px:g} px -> placement_ok={ok or 'undecided'}"


def read_jsonl(paths, id_field="trial_id", session_field="session", also=None):
    """Read the logs and refuse any trial counted twice: the same file given twice, or the same trial in two places
    (a copied file, overlapping exports). A trial is keyed by session + id when the log has a session field, else by id.
    A duplicate would shrink the interval without a new trial and can turn HOLD into GO (usability review 4)."""
    rows, first, files = [], {}, {}
    for p in paths:
        rp = os.path.realpath(p)
        if rp in files: raise TallyError(f"log given twice: {p} (same file as {files[rp]})")
        files[rp] = p
        try: f = open(p)
        except FileNotFoundError: raise TallyError(f"log not found: {p}")
        for n, line in enumerate(f, 1):
            if not line.strip(): continue
            try: r = json.loads(line)
            except json.JSONDecodeError as e: raise TallyError(f"{p} line {n}: not JSON ({e.msg})")
            if not isinstance(r, dict): raise TallyError(f"{p} line {n}: expected one JSON object per trial")
            t = get(r, id_field)
            if t in (None, ""): raise TallyError(f"{p} line {n}: no {id_field!r}; every trial needs a unique id (--id FIELD)")
            key = (get(r, session_field), t, name(get(r, also)) if also else None)   # also: with --pair, a task id is unique per build
            if key in first: raise TallyError(f"duplicate trial {t!r}" + (f" (session {key[0]!r})" if key[0] is not None else "") +
                                              f": {p} line {n} and {first[key]}; each trial may be counted once"
                                              + ("" if also else ". If this id is a task that every build ran (a paired design), use --pair FIELD"))
            first[key] = f"{p} line {n}"; rows.append(r)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog="quantgate.py tally", description="Count successes per build in JSONL trial logs and print the judge CSV row.")
    ap.add_argument("logs", nargs="+"); ap.add_argument("--candidate", required=True); ap.add_argument("--reference", required=True)
    ap.add_argument("--group", default="cell"); ap.add_argument("--success", default="success"); ap.add_argument("--id", default="trial_id")
    ap.add_argument("--and", dest="require", action="append", default=[]); ap.add_argument("--not", dest="forbid", action="append", default=[])
    ap.add_argument("--drop", action="append"); ap.add_argument("--set", action="append", default=[], metavar="COLUMN=VALUE")
    ap.add_argument("--placement", metavar="FIELD", help="placement error per successful trial (e.g. place_px): sets placement_ok by the study's rule")
    ap.add_argument("--placement-tol", type=float, default=5.0, metavar="PX", help="placement tolerance in the field's unit (default 5)")
    ap.add_argument("--engine", metavar="FILE", help="the candidate's engine file: writes its sha256 to engine_sha256")
    ap.add_argument("--missing", choices=["error", "fail", "drop"], default="error", help="a null or missing outcome: stop (default), count as a failure, or leave out")
    ap.add_argument("--pair", metavar="FIELD", help="the field naming the same task across builds (paired design): ids are then unique per build, and the row is marked design=paired")
    ap.add_argument("--append", metavar="CSV"); a = ap.parse_args(argv)
    try:
        notes = []
        row = tally(read_jsonl(a.logs, a.id, also=a.group if a.pair else None), a.candidate, a.reference, a.group, a.success, a.require, a.forbid,
                    ("invalid", "aborted") if a.drop is None else a.drop, a.id, a.placement, a.missing, a.pair, notes)
        for m in notes: print(m, file=sys.stderr)
        if a.placement:
            if not (a.placement_tol > 0): raise TallyError("--placement-tol must be positive")
            row["placement_ok"], note = placement_check(row.pop("_placement"), a.candidate, a.reference, a.placement_tol); print(note, file=sys.stderr)
        if a.engine:
            import hashlib
            try: row["engine_sha256"] = hashlib.sha256(open(a.engine, "rb").read()).hexdigest()
            except FileNotFoundError: raise TallyError(f"engine not found: {a.engine}")
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
