"""`docs/api-contracts/*.yaml` 가 전부 실제로 파싱되는지 확인합니다.

이 파일들은 **사무실에서 읽히는 문서**입니다. 홈에서는 아무도 로드하지
않으므로 — Flask 도, Nuxt 도, 다른 어떤 테스트도 열지 않습니다 — 구문이
깨져도 알아챌 경로가 없습니다. 실제로 `recipe-tat.yaml` 이 깨진 채로
브랜치에 실렸고, 리뷰어가 손으로 파싱해 보고서야 발견됐습니다. 깨진
계약서는 사무실에서 어댑터를 쓰는 사람이 처음 만나게 되고, 그 사람은
문서를 고칠 수도(사무실은 GitHub 로그인이 안 됩니다) 원본을 확인할 수도
없습니다.

여기서 보는 것은 **구문뿐**입니다. 스키마가 코드와 맞는지는
`scripts/verify/check_contract.py` + `tests/test_check_contract.py` 의 일이고, 이
테스트는 그보다 훨씬 아래 — "이 파일이 YAML 이기는 한가" — 를 지킵니다.

`yaml` 은 `pytest.importorskip` 으로 감싸지 않습니다. 없으면 수집 단계에서
크게 터지는 편이 낫습니다. skip 은 초록색으로 보이지만 아무것도 검사하지
않으므로, 이 파일이 존재하는 이유 자체를 지웁니다. (PyYAML 은
`back_dev_home/requirements.txt` 의 `langchain` → `langchain-core` 를 통해
설치됩니다. 런타임 코드가 직접 import 하지는 않으므로 직접 선언을 추가하지
않았습니다 — 선언은 클라우드 설치 목록을 늘리는 일이고, 이 의존은 테스트
전용입니다.)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_DIR = REPO_ROOT / "docs" / "api-contracts"


def _contract_files() -> list[Path]:
    return sorted(CONTRACT_DIR.glob("*.yaml"))


def test_the_contract_directory_is_not_empty():
    """디렉터리가 비면 아래 parametrize 가 0건이 되어 조용히 통과합니다.

    "검사할 게 없다"와 "전부 통과"는 pytest 출력에서 구분되지 않으므로,
    로스터 자체를 한 번 못박아 둡니다.
    """
    assert _contract_files(), f"no *.yaml under {CONTRACT_DIR}"


@pytest.mark.parametrize("path", _contract_files(), ids=lambda p: p.name)
def test_api_contract_yaml_parses(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        pytest.fail(f"{path.relative_to(REPO_ROOT)} is not valid YAML: {exc}")

    # `safe_load` 는 순수 주석 파일이나 빈 파일에 대해 예외 없이 None 을
    # 돌려줍니다 — 그것도 계약서로서는 고장입니다.
    assert isinstance(document, dict), (
        f"{path.relative_to(REPO_ROOT)} parsed to {type(document).__name__}, "
        "expected a top-level mapping"
    )
