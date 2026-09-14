"""자격증명 존재 여부만 보고한다. **값은 절대 출력하지 않는다.**

공개 리포이므로 이 스크립트의 출력이 로그·노트에 붙어도 안전해야 한다.
따라서 길이와 앞 2글자 지문만 찍는다.
"""
import os
import sys
from pathlib import Path

GROUPS = {
    "Nebius Token Factory (D3/D4)": ["NEBIUS_API_KEY", "NEBIUS_BASE_URL"],
    "Nebius Jobs/Endpoint (§5.3, D6)": [
        "NEBIUS_PROJECT_ID", "NEBIUS_TENANT_ID",
        "NEBIUS_SERVICE_ACCOUNT_KEY_FILE", "NEBIUS_REGION",
    ],
    "Tavily (D5)": ["TAVILY_API_KEY"],
    "Hugging Face (SO-101, GR00T)": ["HF_TOKEN"],
}


def load_dotenv_like(path: Path) -> int:
    if not path.is_file():
        return 0
    n = 0
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v:
            os.environ.setdefault(k.strip(), v)
            n += 1
    return n


def fingerprint(v: str) -> str:
    return f"len={len(v)} head={v[:2]}…"


def load_hf_cli_token() -> bool:
    """huggingface-cli login이 남긴 토큰을 줍는다.

    별도로 HF_TOKEN을 받을 필요가 없다. 이미 로그인되어 있으면 그 토큰을 쓴다.
    """
    if os.environ.get("HF_TOKEN"):
        return False
    for p in (Path.home() / ".cache/huggingface/token",
              Path.home() / ".huggingface/token"):
        if p.is_file():
            v = p.read_text().strip()
            if v:
                os.environ["HF_TOKEN"] = v
                print(f"읽음: {p} (huggingface-cli 로그인 토큰)")
                return True
    return False


def main() -> int:
    for p in (Path.home() / ".config/edgeqgate/env", Path(".env.local"), Path(".env")):
        n = load_dotenv_like(p)
        if n:
            print(f"읽음: {p} ({n}개 변수)")
    load_hf_cli_token()

    missing_required = []
    for group, keys in GROUPS.items():
        print(f"\n[{group}]")
        for k in keys:
            v = os.environ.get(k, "")
            if v:
                extra = ""
                if k.endswith("_FILE"):
                    extra = "  (파일 있음)" if Path(v).is_file() else "  ** 경로가 존재하지 않음 **"
                print(f"  OK   {k:<34} {fingerprint(v)}{extra}")
            else:
                print(f"  없음 {k:<34}")
                missing_required.append(k)

    print("\n--- 요약 ---")
    if missing_required:
        print(f"미설정 {len(missing_required)}개: {', '.join(missing_required)}")
    else:
        print("전부 설정됨")
    return 0


if __name__ == "__main__":
    sys.exit(main())
