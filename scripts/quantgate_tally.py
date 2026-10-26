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
  --map V=true|false|missing   text outcomes (e.g. Success, Stalled, Safety) to true/false/missing; unmapped values stop
  --where FIELD=VALUE  count only trials where FIELD equals VALUE (as text), e.g. the same object and instruction
  --audit FILE         one JSON line per input trial: source file, line, id, build, counted or excluded and the reason
  Logs may be JSONL or CSV (one row per trial; empty cells are null). A field name is first matched exactly (a CSV
  column `eval.outcome`), then as a nested path (`eval` -> `outcome`).
  --safety FIELD       per-trial safety event (true/false; empty = not recorded, never counted as "none")
  --detail FIELD       with --pair: shown for each regressed pair (e.g. the failure reason); --regressions FILE lists them
  --pair FIELD         paired design: the field naming the same task across builds; see judge's `design` column
  --engine FILE        the candidate's engine: writes its sha256 to engine_sha256, so preflight can tie the row to it
Any judge column can be added with --set column=value (e.g. --set placement_ok=yes --set mode=improvement).
Usage: python scripts/quantgate_tally.py <log.jsonl> [<log.jsonl> ...] --candidate C --reference R [options]"""
import argparse, csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quantgate_judge as qj


class TallyError(ValueError): pass


def lookup(r, path):
    """(found, value). A key spelled exactly like the path wins (a CSV column named `eval.outcome`); otherwise the dots
    walk nested objects (`eval` -> `outcome`)."""
    if isinstance(r, dict) and path in r: return True, r[path]
    for k in path.split("."):
        if not isinstance(r, dict) or k not in r: return False, None
        r = r[k]
    return True, r


def get(r, path):
    return lookup(r, path)[1]


def no_field(r, path):
    keys = sorted(r) if isinstance(r, dict) else []
    import difflib
    near = difflib.get_close_matches(path, keys, n=3, cutoff=0.6)
    return (f"has no field {path!r} (neither a key spelled {path!r} nor nested {' -> '.join(path.split('.'))}); its fields: "
            f"{', '.join(keys[:12])}{' ...' if len(keys) > 12 else ''}" + (f"; did you mean {', '.join(near)}?" if near else ""))


def truth(v, what):
    if isinstance(v, bool): return v
    raise TallyError(f"{what} must be true or false, not {v!r}")


def name(v):
    """Build names are compared as text, so a log's 3 matches the command line's "3"; booleans and empty values are refused."""
    return None if v is None or isinstance(v, bool) or v == "" else str(v)


def tally(trials, candidate, reference, group="cell", success="success", require=(), forbid=(), drop=("invalid", "aborted"), id_field="trial_id",
          placement=None, missing="error", pair=None, notes=None, valmap=None, where_eq=(), audit=None, srcs=None,
          safety=None, detail=None, regressions=None):
    """missing: what a trial whose outcome is null or absent means. error (default) stops; fail counts it as a failure;
    drop leaves it out. Decide it from the source's own definition and write it down, since it changes the count.
    pair: the field linking the same task across builds (a paired design): reported, and marked design=paired."""
    notes = [] if notes is None else notes
    audit = [] if audit is None else audit
    srcs = srcs or [None] * len(trials)
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
    by_pair = {candidate: {}, reference: {}}            # pair id -> (ok, safety event or None, detail, trial id, audit index)
    saf = {candidate: [0, 0], reference: [0, 0]}        # [events, trials with a safety record]
    regressions = [] if regressions is None else regressions
    def note(i, status, reason, g=None, ok=None, raw_out=None):
        src = srcs[i - 1] or ("", i)
        audit.append({"source": src[0], "line": src[1], "id": get(trials[i - 1], id_field), "build": g, "status": status, "reason": reason,
                      **({"success": ok, "outcome_raw": raw_out} if status == "counted" else {})})
    for i, r in enumerate(trials, 1):
        raw = get(r, group); g = name(raw)
        seen.setdefault(g, set()).add(type(raw).__name__)
        if len(seen[g]) > 1: raise TallyError(f"build {g!r} appears in field {group!r} both as {' and '.join(sorted(seen[g]))}; make the names one type")
        if g not in out: note(i, "excluded", f"build {g!r} is neither candidate nor reference", g); continue
        miss = [f"{k}={v}" for k, v in where_eq if name(get(r, k)) != v]
        if miss: note(i, "excluded", "condition not met: " + ", ".join(f"{m.split('=')[0]} is {get(r, m.split('=')[0])!r}, wanted {m.split('=', 1)[1]!r}" for m in miss), g); continue
        flagged = [d for d in drop if get(r, d) is True]
        if flagged: note(i, "excluded", f"{flagged[0]} is true (--drop)", g); continue
        where = f"trial {get(r, id_field) or i}"
        raw_out = get(r, success)
        if ext is not None:
            t = get(r, id_field)
            if t not in ext: raise TallyError(f"{where}: no outcome in {f}")
            ok = truth(get(ext[t], field), f"{where}: {field}")
        else:
            found, v = lookup(r, success)
            if not found and missing == "error": raise TallyError(f"{where} {no_field(r, success)}")
            if valmap is not None and v is not None:
                key = str(v).strip()
                if key not in valmap: raise TallyError(f"{where}: {success} is {v!r}, which --map does not cover; mapped: {', '.join(sorted(valmap))}")
                v = valmap[key]
            if v is None:
                if missing == "drop": n_missing += 1; note(i, "excluded", f"{success} is null or missing (--missing drop)", g); continue
                if missing == "fail": n_missing += 1; v = False
                else: raise TallyError(f"{where}: {success} is null or missing. Decide what that means in this source (a failure, "
                                       f"or not run) and say so: --missing fail or --missing drop")
            if isinstance(v, str): raise TallyError(f"{where}: {success} is the text {v!r}. Say which texts are a success: e.g. --map {v}=true or "
                                                    f"--map {v}=false for each outcome the source uses (--map NAME=missing for 'not run')")
            ok = truth(v, f"{where}: {success}")
        ok = ok and all(truth(get(r, k), f"{where}: {k}") for k in require) and not any(get(r, k) is True for k in forbid)
        out[g][0] += ok; out[g][1] += 1
        note(i, "counted", "counted" + (" (null outcome as failure, --missing fail)" if raw_out is None and missing == "fail" else ""), g, ok, raw_out)
        ev = None
        if safety:   # a safety event (true), none (false), or not recorded (absent or null): absent is never "none"
            fs, ev = lookup(r, safety)
            if ev is not None and not isinstance(ev, bool): raise TallyError(f"{where}: {safety} must be true, false or empty, not {ev!r}")
            if ev is not None: saf[g][1] += 1; saf[g][0] += ev
        if pair:
            pk = get(r, pair)
            if pk in (None, ""): raise TallyError(f"{where}: no {pair!r} to pair on")
            pairs[g][pk] = pairs[g].get(pk, 0) + 1
            by_pair[g][pk] = (ok, ev, get(r, detail) if detail else None, get(r, id_field), len(audit) - 1)
        if placement and ok:   # placement error is measured on successful trials only, as in the study (E2)
            if pext is not None:
                t = get(r, id_field)
                if t not in pext: raise TallyError(f"{where}: no placement in {pf}")
                v = get(pext[t], pfield)
            else: v = get(r, pfield)
            if isinstance(v, str):
                try: v = float(v)
                except ValueError: pass
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 0: raise TallyError(f"{where}: {pfield} must be a non-negative number on a successful trial, not {v!r}")
            place[g].append(float(v))
    for b in (candidate, reference):
        if out[b][1] == 0:
            kinds = ", ".join(f"{k!r} ({'/'.join(sorted(t))})" for k, t in sorted(seen.items(), key=lambda x: str(x[0])))
            raise TallyError(f"no trials for {b!r} in field {group!r}; builds seen: {kinds}")
    if missing != "error" and n_missing: notes.append(f"{n_missing} trial(s) with a null or missing {success} {'counted as failures' if missing == 'fail' else 'left out'} (--missing {missing})")
    trans = None
    if pair:
        trans = {"both_success": 0, "improved": 0, "regressed": 0, "both_fail": 0}
        for pk in sorted(set(by_pair[candidate]) & set(by_pair[reference]), key=str):
            c, rf = by_pair[candidate][pk], by_pair[reference][pk]
            t = "both_success" if c[0] and rf[0] else "improved" if c[0] else "regressed" if rf[0] else "both_fail"
            trans[t] += 1
            for x in (c, rf): audit[x[4]].update({"pair": pk, "transition": t})
            if t == "regressed":
                regressions.append({"pair": pk, "candidate_trial": c[3], "reference_trial": rf[3], "candidate_safety_event": c[1],
                                    **({"candidate_detail": c[2], "reference_detail": rf[2]} if detail else {})})
        sreg = sum(x["candidate_safety_event"] is True for x in regressions); sunk = sum(x["candidate_safety_event"] is None for x in regressions)
        notes.append(f"pairs: {trans['improved']} improved, {trans['regressed']} regressed, {trans['both_success']} both succeed, {trans['both_fail']} both fail"
                     + (f"; of the regressions, {sreg} with a safety event" + (f", {sunk} with no safety record" if sunk else "") if safety else
                        "; safety: not provided (--safety FIELD)"))
        for x in regressions:
            notes.append(f"  regressed: pair {x['pair']!r}: candidate trial {x['candidate_trial']!r} failed, reference trial {x['reference_trial']!r} succeeded"
                         + (f"; safety event: {'yes' if x['candidate_safety_event'] else 'no' if x['candidate_safety_event'] is False else 'not recorded'}" if safety else "")
                         + (f"; {detail}: {x['candidate_detail']!r}" if detail else ""))
    if pair:
        both = set(pairs[candidate]) & set(pairs[reference]); once = all(v == 1 for b in pairs for v in pairs[b].values())
        notes.append(f"paired on {pair!r}: {len(both)} pairs with both builds, {len(set(pairs[candidate]) ^ set(pairs[reference]))} unpaired"
                     + ("" if once else "; some pair ids repeat within a build"))
    row = {"candidate": candidate, "reference": reference, "cand_successes": out[candidate][0], "cand_trials": out[candidate][1],
            "ref_successes": out[reference][0], "ref_trials": out[reference][1]}
    if placement: row["_placement"] = place
    if pair:
        row["design"] = "paired"; row["pairs_improved"] = trans["improved"]; row["pairs_regressed"] = trans["regressed"]
        if safety:
            row["safety_regressions"] = sum(x["candidate_safety_event"] is True for x in regressions)
            row["safety_unrecorded_regressions"] = sum(x["candidate_safety_event"] is None for x in regressions)
    if safety:
        row["safety_events_cand"], row["safety_recorded_cand"] = saf[candidate]; row["safety_events_ref"], row["safety_recorded_ref"] = saf[reference]
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


def read_jsonl(paths, id_field="trial_id", session_field="session", also=None, srcs=None):
    """Read the logs and refuse any trial counted twice: the same file given twice, or the same trial in two places
    (a copied file, overlapping exports). A trial is keyed by session + id when the log has a session field, else by id.
    A duplicate would shrink the interval without a new trial and can turn HOLD into GO (usability review 4)."""
    rows, first, files = [], {}, {}
    for p in paths:
        rp = os.path.realpath(p)
        if rp in files: raise TallyError(f"log given twice: {p} (same file as {files[rp]})")
        files[rp] = p
        try: f = open(p, encoding="utf-8-sig", newline="")
        except FileNotFoundError: raise TallyError(f"log not found: {p}")
        if p.lower().endswith(".csv"):   # one row per trial; empty cells are null, true/false (any case) are booleans
            rd = csv.DictReader(f)
            it = ((n, {k.strip(): ({"true": True, "false": False}.get(v.strip().lower(), v.strip()) if v.strip() else None) for k, v in row.items() if k})
                  for n, row in enumerate(rd, 2))
        else:
            def it_jsonl():
                for n, line in enumerate(f, 1):
                    if not line.strip(): continue
                    try: yield n, json.loads(line)
                    except json.JSONDecodeError as e: raise TallyError(f"{p} line {n}: not JSON ({e.msg})")
            it = it_jsonl()
        for n, r in it:
            if not isinstance(r, dict): raise TallyError(f"{p} line {n}: expected one JSON object per trial")
            t = get(r, id_field)
            if t in (None, ""): raise TallyError(f"{p} line {n}: no {id_field!r}; every trial needs a unique id (--id FIELD)")
            key = (get(r, session_field), t, name(get(r, also)) if also else None)   # also: with --pair, a task id is unique per build
            if key in first: raise TallyError(f"duplicate trial {t!r}" + (f" (session {key[0]!r})" if key[0] is not None else "") +
                                              f": {p} line {n} and {first[key]}; each trial may be counted once"
                                              + ("" if also else ". If this id is a task that every build ran (a paired design), use --pair FIELD"))
            first[key] = f"{p} line {n}"; rows.append(r)
            if srcs is not None: srcs.append((p, n))
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
    ap.add_argument("--map", action="append", default=[], metavar="VALUE=true|false|missing", help="turn a text outcome into one, e.g. --map Success=true --map Stalled=false; any unmapped value stops")
    ap.add_argument("--where", action="append", default=[], metavar="FIELD=VALUE", help="count only trials where FIELD equals VALUE (as text); the rest are excluded with the reason")
    ap.add_argument("--safety", metavar="FIELD", help="per-trial safety event: true, false, or empty when not recorded (never read as none)")
    ap.add_argument("--detail", metavar="FIELD", help="with --pair: a field to show for each regressed pair, e.g. the failure reason")
    ap.add_argument("--regressions", metavar="JSONL", help="with --pair: write each regressed pair (trial ids, safety, detail)")
    ap.add_argument("--audit", metavar="JSONL", help="write one line per input trial: source, line, id, counted or excluded, and why")
    ap.add_argument("--pair", metavar="FIELD", help="the field naming the same task across builds (paired design): ids are then unique per build, and the row is marked design=paired")
    ap.add_argument("--append", metavar="CSV"); a = ap.parse_args(argv)
    try:
        notes, audit, srcs, regs = [], [], [], []
        valmap = None
        if a.map:
            valmap = {}
            for m in a.map:
                k, eq, v = m.rpartition("=")
                if not eq or v.strip().lower() not in ("true", "false", "missing"): raise TallyError(f"--map needs VALUE=true|false|missing, not {m!r}")
                valmap[k.strip()] = {"true": True, "false": False, "missing": None}[v.strip().lower()]
        where_eq = []
        for w in a.where:
            k, eq, v = w.partition("=")
            if not eq or not k.strip(): raise TallyError(f"--where needs FIELD=VALUE, not {w!r}")
            where_eq.append((k.strip(), v.strip()))
        row = tally(read_jsonl(a.logs, a.id, also=a.group if a.pair else None, srcs=srcs), a.candidate, a.reference, a.group, a.success, a.require, a.forbid,
                    ("invalid", "aborted") if a.drop is None else a.drop, a.id, a.placement, a.missing, a.pair, notes, valmap, where_eq, audit, srcs,
                    a.safety, a.detail, regs)
        if (a.detail or a.regressions) and not a.pair: raise TallyError("--detail and --regressions need --pair (a regression is a pair that went from success to failure)")
        if a.regressions:
            with open(a.regressions, "w") as fr: fr.write("".join(json.dumps(x, default=str) + "\n" for x in regs))
        if a.audit:
            with open(a.audit, "w") as fa: fa.write("".join(json.dumps(x, default=str) + "\n" for x in audit))
            ex = {}
            for x in audit:
                if x["status"] == "excluded": ex[x["reason"].split(":")[0]] = ex.get(x["reason"].split(":")[0], 0) + 1
            notes.append(f"audit: {sum(x['status'] == 'counted' for x in audit)} counted, {sum(x['status'] == 'excluded' for x in audit)} excluded"
                         + (f" ({'; '.join(f'{k}: {v}' for k, v in ex.items())})" if ex else "") + f" -> {a.audit}")
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
