"""Configuration check and gate decision for the CI example (.github/workflows/quantgate-gate.yml), usability review 4.

  gate_config_check.py <workflow.yml>                    refuse a config that would silently not gate:
      FAIL_ON not one of block, hold, none (a typo such as `holdd` must not open the gate), and RESULTS or CARD not
      covered by on.pull_request.paths / on.push.paths (a change to them would not run the workflow)
  gate_config_check.py --apply <FAIL_ON> <judge exit> <preflight exit>
      exit 1 when the gate closes: block -> any BLOCK (4); hold -> any HOLD (3) or BLOCK; none -> never
Values come from the workflow's env (RESULTS, CARD, FAIL_ON), overridable by the environment. Exit 2: config error."""
import fnmatch, os, re, sys
import yaml

FAIL_ON = ("block", "hold", "none")


def glob_match(path, pattern):
    """GitHub path filters: ** crosses folders, * stays within one; a pattern starting with ! excludes."""
    rx = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.fullmatch(rx, path) is not None


def covered(path, patterns):
    hit = False
    for p in patterns:   # later patterns win, as in GitHub
        if p.startswith("!"):
            if glob_match(path, p[1:]): hit = False
        elif glob_match(path, p): hit = True
    return hit


def check(wf_path):
    wf = yaml.safe_load(open(wf_path))
    env = {**(wf.get("env") or {}), **{k: os.environ[k] for k in ("RESULTS", "CARD", "FAIL_ON") if k in os.environ}}
    on = wf.get("on", wf.get(True)) or {}   # PyYAML reads the key `on` as True
    errs = []
    if str(env.get("FAIL_ON", "")).strip() not in FAIL_ON: errs.append(f"FAIL_ON={env.get('FAIL_ON')!r}: use one of {', '.join(FAIL_ON)}")
    for k in ("RESULTS", "CARD"):
        f = os.path.normpath(str(env.get(k, ""))).replace(os.sep, "/")
        if not env.get(k): errs.append(f"{k} is not set"); continue
        if not os.path.exists(f): errs.append(f"{k}={f}: file not found in the repository")
        for ev in ("pull_request", "push"):
            if ev in on and isinstance(on[ev], dict) and "paths" in on[ev] and not covered(f, on[ev]["paths"]):
                errs.append(f"{k}={f} is not under on.{ev}.paths, so a change to it would not run the gate")
    for e in errs: print(f"config error: {e}", file=sys.stderr)
    if errs: sys.exit(2)
    print(f"gate config ok: FAIL_ON={env['FAIL_ON']}, RESULTS={env['RESULTS']}, CARD={env['CARD']}")


def apply(fail_on, judge, pre):
    if fail_on not in FAIL_ON: print(f"config error: FAIL_ON={fail_on!r}: use one of {', '.join(FAIL_ON)}", file=sys.stderr); sys.exit(2)
    worst = max(int(judge), int(pre))
    closed = (fail_on == "block" and worst == 4) or (fail_on == "hold" and worst in (3, 4))
    print(f"gate {'closed' if closed else 'open'}: judge exit {judge}, preflight exit {pre}, FAIL_ON={fail_on}")
    sys.exit(1 if closed else 0)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--apply"] and len(a) == 4: apply(*a[1:])
    elif len(a) == 1: check(a[0])
    else: print(__doc__, file=sys.stderr); sys.exit(2)
