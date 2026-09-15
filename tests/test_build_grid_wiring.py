"""`scripts/build_grid.py`가 무결성 모듈을 **실제로 거치는지** 본다.

attempt-022에서 발견한 것: `build_grid.py`는 docstring에 "`IG-1`은
edgeqgate.calibration이 강제한다"고 적어두고 그 모듈을 부르지 않았다.
자체 `np.random.default_rng`로 프레임을 뽑았고 `calib_composition`은 시드
문자열에만 들어갔다 — 즉 구성 축이 **시드 변경과 구별되지 않았다.**

`tests/test_calibration.py`는 라이브러리가 옳게 동작함을 증명하지만, 생산 경로가
그 라이브러리를 **호출하는지**는 증명하지 못한다. 이 파일이 그 틈을 막는다.
소스 수준 검사인 이유는 `build_grid`를 import하면 torch·modelopt·GPU가 필요하고
CI에서 돌지 않기 때문이다.
"""
import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "build_grid.py"
TREE = ast.parse(SRC.read_text())


def _called_names() -> set[str]:
    out = set()
    for node in ast.walk(TREE):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


def test_calls_the_calibration_builder():
    assert "build_calibration_set" in _called_names()


def test_calls_the_audit_leak_verifier():
    assert "verify_no_audit_leak" in _called_names()


def test_no_private_rng_for_frame_selection():
    """자체 RNG로 프레임을 뽑으면 구성 축·`IG-1`·누출 재검사가 전부 우회된다."""
    assert "default_rng" not in SRC.read_text()


def test_composition_is_not_merely_a_seed_ingredient():
    """`calib_composition`이 해시 시드 문자열에만 등장하면 축이 작동하지 않는다.

    회귀 방지: 옛 코드는 `f"{v.code}|{v.calib_composition}|{size}"`를
    sha256에 넣는 것이 구성 축 구현의 전부였다.
    """
    text = SRC.read_text()
    for node in ast.walk(TREE):
        if isinstance(node, ast.JoinedStr):
            rendered = "".join(
                v.value for v in node.values if isinstance(v, ast.Constant)
            )
            has_comp = any(
                isinstance(v, ast.FormattedValue)
                and isinstance(v.value, ast.Attribute)
                and v.value.attr == "calib_composition"
                for v in node.values
            )
            assert not (has_comp and "|" in rendered), (
                "calib_composition이 시드 문자열 재료로만 쓰이고 있다"
            )
    assert "calib_composition=" in text or "composition=v.calib_composition" in text


def test_records_whether_success_labels_were_approximated():
    """라벨 없이 돌린 결과를 나중에 라벨 있는 결과와 섞지 않도록 셀마다 남긴다."""
    assert "calib_approximated" in SRC.read_text()
