"""norm_stats.npz for trt_policy_server.py from a LeRobot checkpoint's processor files.
pre_* keys come from policy_preprocessor_step_3_normalizer_processor (observation.state, observation.images.*);
post_* keys come from policy_postprocessor_step_0_unnormalizer_processor (action). Dots become underscores, which is
the key layout of the G2 file. `--check <existing.npz>` verifies that the rule reproduces an existing file on every key
the server reads.
Usage: python make_norm_stats.py <pretrained_model dir> <out.npz> [--check existing.npz]"""
import sys, os
import numpy as np
from safetensors.numpy import load_file
ck, out = sys.argv[1:3]
pre = load_file(os.path.join(ck, "policy_preprocessor_step_3_normalizer_processor.safetensors"))
post = load_file(os.path.join(ck, "policy_postprocessor_step_0_unnormalizer_processor.safetensors"))
ns = {k.replace(".", "_"): v for k, v in pre.items()}
ns.update({"post_" + k.replace(".", "_"): v for k, v in post.items()})
USED = ["observation_state_mean", "observation_state_std", "observation_images_top_mean", "observation_images_top_std",
        "observation_images_wrist_mean", "observation_images_wrist_std", "post_action_mean", "post_action_std"]
if "--check" in sys.argv:
    ref = np.load(sys.argv[sys.argv.index("--check") + 1])
    bad = [k for k in USED if not np.allclose(np.asarray(ref[k]).reshape(-1), np.asarray(ns[k]).reshape(-1))]
    print("check vs", sys.argv[sys.argv.index("--check") + 1], "mismatch:", bad); sys.exit(1 if bad else 0)
np.savez(out, **{k: ns[k] for k in USED}); print("written", out, {k: ns[k].shape for k in USED})
