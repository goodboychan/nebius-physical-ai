"""Devpost gallery, 15 images at 3:2 (1500x1000 PNG, < 5 MB each), in the order of the story. Reuses the v1 slide style
(scripts/make_gallery.py) and the video's animated charts (scripts/video_charts.py, last frame), so numbers come from the
committed CSVs. Stills come from the committed clips and the user's edited clips.
Usage: <venv with av, PIL> python scripts/make_gallery_v2.py <shots dir> <out dir>"""
import os, sys
import av
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SHOTS, OUT = sys.argv[1:3]; os.makedirs(OUT, exist_ok=True)
sys.argv = [sys.argv[0], SHOTS, OUT]
import make_gallery as mg          # runs v1 (writes 01-06 into OUT too); its slide() is reused below
import video_charts as vc
import phone_clips as pc

def still(path, t, rot=0):
    c = av.open(path); st = c.streams.video[0]; im = None
    for f in c.decode(st):
        im = f.to_image().convert("RGB")
        if float(f.pts * st.time_base) >= t: break
    c.close(); return im.rotate(rot) if rot else im
def chart(name, dur, t=None):
    return vc.CHARTS[name](dur if t is None else t, dur).crop((60, 110, 1860, 1010))
def side(a, b):
    h = 720; a = a.resize((int(a.width * h / a.height), h)); b = b.resize((int(b.width * h / b.height), h)); im = Image.new("RGB", (a.width + b.width + 24, h), (16, 20, 19))
    im.paste(a, (0, 0)); im.paste(b, (a.width + 24, 0)); return im
C, E = "dashboard/clips", "video/edit"
S = mg.slide
for f in os.listdir(OUT):
    if f[:2] in ("02", "03", "04", "05", "06"): os.rename(f"{OUT}/{f}", f"{OUT}/_v1_{f}")
os.rename(f"{OUT}/01_thumbnail.png", f"{OUT}/01_thumbnail.png") if os.path.exists(f"{OUT}/01_thumbnail.png") else None
S("02_same_robot_same_task", "Same robot, same task", "One run succeeds, one fails. Before shipping to a tiny Jetson, which model can I trust?",
  [(side(still(f"{C}/g6_success.mp4", 99), still(f"{C}/g6_fail_knock.mp4", 99)), 56, 180, 1388, 760)])
S("03_setup", "One task, one arm, cloud where it does real work", "SO-101 + Jetson Orin Nano Super · training on Nebius Jobs · Cosmos-Reason2 and Nemotron 3 Super on Nebius",
  [(f"{SHOTS}/setup.png", 56, 180, 1388, 760)])
S("04_data", "120 teleoperated demonstrations", "Leader-follower SO-101, overhead and wrist cameras · LeRobot ACT (Action Chunking with Transformers)",
  [(still(f"{C}/demos_top_wrist.mp4", 3.0), 56, 180, 1388, 760)])
bars = lambda t: vc.CHARTS["engine_cost"](t, 11.2).crop((60, 180, 1860, 790))   # title + bars, no pill (the slide subtitle says it)
S("05_engine_cost", "Measured on the Jetson, not assumed", "FP16 is the fastest and the cheapest per inference on this device (trtexec, 15 W)",
  [(bars(2.45), 56, 180, 1388, 375), (bars(5.6 + 2.45), 56, 565, 1388, 375)])   # bars complete, before the pills appear
S("06_success_by_cell", "Blinded real-arm trials", "245 sealed, interleaved trials in the main study; 25 per cell cannot separate the cells",
  [(chart("g6_success", 7.3), 56, 180, 1388, 760)])
S("07_audit_vs_random", "The offline audit did not predict the arm", "Audit-picked INT8 cells 73/75 vs randomly picked 73/75",
  [(chart("audit_vs_random", 3.5), 56, 180, 1388, 760)])
S("08_cost_vs_evidence", "Cost and evidence, side by side", "FP16: cheapest engine, 19/20 on the arm · every comparison with FP32 is still insufficient evidence",
  [(chart("cost_vs_success", 9.5), 56, 180, 1388, 760)])
S("09_what_moved", "What moved the success rate", "Not the precision: gripper friction (8/24 without pads) and a 3 cm start shift (0/3)",
  [(f"{SHOTS}/moved.png", 56, 180, 1388, 760)])
S("10_position_finetune", "A weakness found, fixed and re-tested", "50 shifted demos, 25-min fine-tune on Nebius Jobs · +3 cm 12/12 vs 3/12 · −3 cm 10/12 vs 2/12",
  [(chart("ft_position", 5.5), 56, 180, 1388, 760)])
S("11_ai_judge", "AI components are tested too", "Cosmos-Reason2 on a Nebius AI Endpoint: first setup 1/21 → validated 20/21 → live 22/24, 2/72 false alarms",
  [("artifacts/reports/figures/fig_frames.png", 56, 180, 1388, 760)])
S("12_deployment_review", "The deployment review", "Which candidate to validate first, which to distrust, and whether to approve: not yet",
  [(f"{SHOTS}/review_decisions.png", 56, 180, 1388, 330), (f"{SHOTS}/review_compare.png", 56, 530, 1388, 410)])
S("13_preflight", "Deployment preflight", "Engine hash · normalization manifest · 200 ms chunk deadline · only an explicit GO passes",
  [(f"{SHOTS}/preflight.png", 56, 180, 1388, 760)])
rep = Image.open(f"{SHOTS}/report_meta.png").convert("RGB"); rep = rep.crop((0, 0, rep.width, min(rep.height, int(rep.width * 0.55))))
S("14_report", "Code writes the verdicts, Nemotron explains", "Deployment report: every number and verdict from code; Nemotron 3 Super on Nebius Token Factory writes words only",
  [(rep, 56, 180, 1388, 760)])
S("15_isaac_twin", "Next: the same review on an Isaac Sim twin", "Exploratory: twin calibrated to the real arm on a GB10 desktop, replaying a real trial (grasp assisted)",
  [(still(os.path.expanduser("~/edgeqgate_data/sim_out/t0001_twin_side_by_side.mp4"), 9.0).crop((0, 50, 1280, 530)), 56, 180, 1388, 760)])
for f in sorted(os.listdir(OUT)):
    if f.startswith("_v1_"): os.remove(f"{OUT}/{f}")
print(sorted(os.listdir(OUT)))
