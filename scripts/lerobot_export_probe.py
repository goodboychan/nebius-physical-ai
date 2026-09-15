"""LeRobot ACT가 우리 export 경로(ONNX -> modelopt -> TRT)를 통과하는가.

§9.1이 ACT를 택했으므로 본 실험의 정책은 **LeRobot의 ACT**여야 한다.
scripts/act_model.py는 K4(그래프/툴체인 리스크) 검증용 근사였고, 정책이 아니다.

이 프로브가 답하는 것: 진짜 ACT로 갈아탔을 때 export 경로가 그대로 작동하는가.
attempt-003에서 찾은 fused MHA fast path 문제가 여기서도 나올 가능성이 높다.
"""
import sys, time, traceback
import torch

torch.backends.mha.set_fastpath_enabled(False)   # attempt-003 발견

from lerobot.policies.act.configuration_act import ACTConfig
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.configs.types import FeatureType, PolicyFeature
from lerobot.utils.constants import OBS_IMAGES, OBS_STATE


def log(m): print(f"[lr] {m}", flush=True)


class Wrap(torch.nn.Module):
    """ACTPolicy는 정규화·큐 로직을 포함하므로 내부 모델만 export한다."""
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, state, up, side):
        r = self.m({OBS_STATE: state, OBS_IMAGES: [up, side]})
        return r[0] if isinstance(r, (tuple, list)) else r


def build(dof: int = 6):
    """SO-101 형상 ACT. dof=6은 단일팔, dof=12는 양팔(ALOHA는 14)."""
    cfg = ACTConfig(
        input_features={
            "observation.state": PolicyFeature(type=FeatureType.STATE, shape=(dof,)),
            "observation.images.up": PolicyFeature(type=FeatureType.VISUAL, shape=(3, 480, 640)),
            "observation.images.side": PolicyFeature(type=FeatureType.VISUAL, shape=(3, 480, 640)),
        },
        output_features={"action": PolicyFeature(type=FeatureType.ACTION, shape=(dof,))},
        chunk_size=100,
        n_action_steps=100,
    )
    return cfg, ACTPolicy(cfg)


def main():
    log(f"torch {torch.__version__}")
    import importlib.metadata as md
    log(f"lerobot {md.version('lerobot')}")

    cfg, policy = build()
    n = sum(p.numel() for p in policy.parameters())
    log(f"ACTPolicy 생성 OK — 파라미터 {n/1e6:.1f}M, chunk {cfg.chunk_size}")

    policy = policy.cuda().eval()
    # LeRobot은 카메라를 개별 키가 아니라 OBS_IMAGES 하나에 리스트로 받는다
    # (modeling_act.py: batch[OBS_IMAGES][0].shape[0]).
    batch = {
        OBS_STATE: torch.randn(1, 6).cuda(),
        OBS_IMAGES: [torch.rand(1, 3, 480, 640).cuda(), torch.rand(1, 3, 480, 640).cuda()],
    }
    with torch.no_grad():
        out = policy.model(batch)
    log(f"forward OK — 출력 타입 {type(out)}")
    if isinstance(out, (tuple, list)):
        log(f"  출력 요소: {[tuple(o.shape) if torch.is_tensor(o) else type(o).__name__ for o in out]}")

    # export 대상은 정책의 내부 모델이다. ACTPolicy는 normalize/queue 로직을 포함해
    # 그대로 export하면 제어 흐름이 섞인다.
    w = Wrap(policy.model).cuda().eval()
    ex = (batch[OBS_STATE], batch[OBS_IMAGES][0], batch[OBS_IMAGES][1])
    with torch.no_grad():
        y = w(*ex)
    log(f"래퍼 출력 {tuple(y.shape)}")

    # ONNX constant folding이 CUDA 파라미터와 CPU 상수를 섞어 실패한다
    # (LeRobot ACT의 사인파 위치 임베딩이 CPU에서 만들어진다).
    # export는 GPU가 필요 없으므로 CPU에서 수행한다.
    w = w.cpu()
    ex = tuple(t.cpu() for t in ex)
    log("CPU로 옮겨 export (constant folding의 디바이스 혼합 회피)")

    t0 = time.time()
    torch.onnx.export(w, ex, "/out/lerobot_act.onnx",
                      input_names=["state", "images_up", "images_side"],
                      output_names=["actions"], opset_version=17,
                      do_constant_folding=True, dynamo=False)
    import os
    log(f"ONNX export 성공 — {os.path.getsize('/out/lerobot_act.onnx')/1e6:.0f} MB ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
