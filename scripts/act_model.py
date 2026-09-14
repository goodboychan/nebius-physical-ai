"""ACT(Action Chunking Transformer) 추론 그래프 — `G0` 드라이런용.

목적은 정책 성능이 아니라 **그래프/툴체인 리스크**(`K4`) 검증이다. 따라서 위상은
ACT 추론 경로를 그대로 따르되 가중치는 무작위다. `K4`가 묻는 것은 "ACT export에서
TRT INT8 빌드가 실패하는가"이며, 그것은 가중치가 아니라 그래프의 성질이다.

학습 시의 CVAE 인코더는 추론 경로에 없으므로 제외한다 (실제 ACT 배포와 동일).
"""

import torch
import torch.nn as nn
from torchvision.models import resnet18


class ACTInference(nn.Module):
    def __init__(
        self,
        n_cameras: int = 2,
        state_dim: int = 6,        # SO-101 팔로워 관절 수
        action_dim: int = 6,
        chunk_size: int = 100,     # ACT 기본 액션 청크
        d_model: int = 512,
        nhead: int = 8,
        dim_ff: int = 3200,
        enc_layers: int = 4,
        dec_layers: int = 7,
    ):
        super().__init__()
        self.n_cameras = n_cameras
        self.chunk_size = chunk_size
        self.d_model = d_model

        # 카메라마다 별도 backbone (ACT 원구현과 동일하게 공유하지 않는다)
        self.backbones = nn.ModuleList()
        for _ in range(n_cameras):
            r = resnet18(weights=None)
            self.backbones.append(nn.Sequential(*list(r.children())[:-2]))  # (B,512,H/32,W/32)
        self.input_proj = nn.Conv2d(512, d_model, kernel_size=1)
        self.state_proj = nn.Linear(state_dim, d_model)

        enc_layer = nn.TransformerEncoderLayer(
            d_model, nhead, dim_ff, dropout=0.0, activation="relu",
            batch_first=True, norm_first=False,
        )
        # enable_nested_tensor=False: nested tensor 경로가 모듈 호출을 우회해
        # 양자화기가 데이터를 못 보는 것을 막는다 (attempt-003 발견).
        self.encoder = nn.TransformerEncoder(enc_layer, enc_layers, enable_nested_tensor=False)
        dec_layer = nn.TransformerDecoderLayer(
            d_model, nhead, dim_ff, dropout=0.0, activation="relu",
            batch_first=True, norm_first=False,
        )
        self.decoder = nn.TransformerDecoder(dec_layer, dec_layers)

        self.query_embed = nn.Parameter(torch.randn(chunk_size, d_model) * 0.02)
        self.pos_embed = nn.Parameter(torch.randn(1, 1 + n_cameras * 300, d_model) * 0.02)
        self.action_head = nn.Linear(d_model, action_dim)

    def forward(self, images: torch.Tensor, state: torch.Tensor) -> torch.Tensor:
        """images: (B, n_cameras, 3, H, W), state: (B, state_dim) -> (B, chunk_size, action_dim)"""
        b = images.shape[0]
        tokens = []
        for i, backbone in enumerate(self.backbones):
            f = backbone(images[:, i])              # (B, 512, h, w)
            f = self.input_proj(f)                  # (B, d, h, w)
            tokens.append(f.flatten(2).transpose(1, 2))   # (B, h*w, d)
        s = self.state_proj(state).unsqueeze(1)     # (B, 1, d)
        src = torch.cat([s] + tokens, dim=1)        # (B, 1+sum(h*w), d)
        src = src + self.pos_embed[:, : src.shape[1]]

        memory = self.encoder(src)
        tgt = self.query_embed.unsqueeze(0).expand(b, -1, -1)
        out = self.decoder(tgt, memory)             # (B, chunk, d)
        return self.action_head(out)


def make_example_inputs(batch: int = 1, n_cameras: int = 2, h: int = 480, w: int = 640,
                        state_dim: int = 6, device: str = "cuda"):
    return (
        torch.randn(batch, n_cameras, 3, h, w, device=device),
        torch.randn(batch, state_dim, device=device),
    )
