"""Link repository paths in the dashboard to the file on GitHub at a fixed commit (the last one that changed a linked file) (developer usability review, 2026-10-24).
A path is linked only if the file exists in that commit, so a link never points at a file the reader cannot open.
Text inside <script>, <style>, <a>, <title> and tag attributes is left alone, so running it twice changes nothing."""
import html, os, re, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "https://github.com/goodboychan/nebius-physical-ai"
PATH = re.compile(r"(?<![\w/.-])((?:artifacts|docs|scripts|dashboard|examples|tests|src|sim)/[A-Za-z0-9_./-]*[A-Za-z0-9_])(#[\w.-]+)?")
git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def commit(*texts):
    """The last commit that changed any linked file, so the page is rebuilt byte-identically after unrelated commits."""
    files = tracked("HEAD"); paths = sorted({m.group(1) for t in texts for m in PATH.finditer(t)} & files)
    return git("log", "-1", "--format=%H", "--", *paths).stdout.strip() if paths else git("rev-parse", "HEAD").stdout.strip()


def tracked(sha):
    return set(git("ls-tree", "-r", "--name-only", sha).stdout.split())


def url(path, sha, files):
    p = path.split("#")[0]
    if p in files: return f"{REPO}/blob/{sha}/{p}"
    if any(f.startswith(p.rstrip("/") + "/") for f in files): return f"{REPO}/tree/{sha}/{p.rstrip('/')}"
    return None


def link_text(text, sha, files):
    """text is already HTML-escaped; wrap each known path in a link."""
    def sub(m):
        u = url(html.unescape(m.group(1)), sha, files)
        return f'<a class="gh" href="{u}" target="_blank" rel="noopener">{m.group(0)}</a>' if u else m.group(0)
    return PATH.sub(sub, text)


def link_html(doc, sha=None):
    doc = re.sub(r'<a class="gh" href="[^"]*" target="_blank" rel="noopener">(.*?)</a>', r"\1", doc)   # relink from scratch
    sha = sha or commit(doc); files = tracked(sha); out, skip = [], []
    for part in re.split(r"(<[^>]+>)", doc):
        if part.startswith("<"):
            m = re.match(r"<(/?)(script|style|a|title|textarea)\b", part, re.I)
            if m and not m.group(1): skip.append(m.group(2).lower())
            elif m and skip: skip.pop()
            out.append(part)
        else: out.append(part if skip else link_text(part, sha, files))
    return "".join(out)
