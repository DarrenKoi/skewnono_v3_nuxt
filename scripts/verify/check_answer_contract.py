"""chat <-> RAG answer 계약을 이 기계에서 검사합니다.

계약 자체는 `back_dev_home/chat/answer/contract.py` 이며, chat 이 사무실 turn
마다 같은 `validate_answer()` 를 호출합니다. 이 스크립트는 그 모듈을 사람이
손으로 돌릴 수 있게 감싼 것뿐입니다 - 규칙을 여기에 적지 않습니다.

사용법:
    python -m scripts.verify.check_answer_contract          # 계약 출력 + 자체 검사
    python scripts/verify/check_answer_contract.py --live   # 실제 agent_query 1회
    python -m scripts.verify.check_answer_contract --live "GT2000 얼라인 알람"

인자 없이 돌리면 인덱스도 RAG 체크아웃도 필요하지 않습니다. 계약 전문을
출력하고 내장된 예제 payload 가 검증기를 통과하는지만 봅니다.

`--live` 는 `_rag/skewnono_rag/` 를 import 해 `agent_query` 를 한 번 부르고,
import - 서명 - 반환값 순으로 검사합니다. 실패하면 어긋난 **키 이름**을
출력하므로, 그 줄만 chat 측에 전하면 됩니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import scripts  # noqa: E402,F401  (applies the stdout UTF-8 fix)

from back_dev_home.chat.answer.contract import main  # noqa: E402


if __name__ == "__main__":
    # 무거운 것을 하기 전에 살아 있다는 증거 한 줄 (scripts/README.md 4항).
    print(f"python {sys.version.split()[0]}  stdout={sys.stdout.encoding}")
    raise SystemExit(main(sys.argv[1:]))
