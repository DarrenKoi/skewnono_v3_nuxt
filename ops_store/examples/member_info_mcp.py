"""member_info 디렉터리를 LLM 이 '도구(tool)'로 검색하게 해 주는 MCP 서버입니다.

자체 RAG 파이프라인에 붙이는 용도예요. RAG 파이프라인의 MCP 클라이언트가 이 서버에
접속하면, LLM 이 아래 세 도구를 골라 호출하면서(질의어·필터를 스스로 정하며) 직원 정보를
context 로 끌어옵니다. 미리 top-k 를 박아 넣는 고전 RAG 와 달리, LLM 이 필요한 만큼
좁혀 가며 여러 번 검색하는 agentic retrieval 방식입니다.

설계 요점:
  - 검색 로직은 member_info_search.py(MCP 비의존, 단독 실행·복사 가능)에 그대로 두고,
    이 파일은 그 헬퍼들을 도구로 감싸기만 하는 얇은 어댑터입니다. 검색 규칙이 바뀌면
    한 곳(member_info_search.py)만 고치면 돼요. (헬퍼는 도구 함수 이름과 겹치지 않도록
    `_search_members` / `_filter_members` / `_get_member` 별칭으로 가져옵니다.)
  - 도구의 docstring 이 곧 LLM 프롬프트입니다. LLM 은 본문 코드를 못 보고 이 설명만 읽고
    어떤 도구를 쓸지 고릅니다. 타입 힌트는 FastMCP 가 입력 JSON Schema 로 자동 변환합니다.
  - 반환값은 OpenSearch 원본 응답이 아니라 _shape() 로 추린 '평평한 레코드 목록'입니다.
    _score/_shards 같은 메타는 버리고 사람이 읽을 필드만 남겨 context 토큰을 아낍니다.
  - 연결은 서버 기동 시 한 번만 열어(_search) 모든 도구가 재사용합니다.

운영(별도 서버에서 HTTP 로 띄우기 — 기본):
    pip install mcp
    python -m ops_store.examples.member_info_mcp
    # 0.0.0.0:8000 에 바인딩, 클라이언트는 http://<이 서버>:8000/mcp 로 접속합니다.
    # 포트/바인딩 주소는 환경변수로 바꿉니다:
    MEMBER_INFO_MCP_HOST=0.0.0.0 MEMBER_INFO_MCP_PORT=8000 \
        python -m ops_store.examples.member_info_mcp

로컬 디버깅(서브프로세스 stdio):
    MEMBER_INFO_MCP_TRANSPORT=stdio python -m ops_store.examples.member_info_mcp

별도 서버로 띄우므로 서버 하나를 여러 RAG 워커가 공유합니다. 그래서:
  - 연결(_search, OpenSearch)을 기동 시 한 번 열어 모든 요청이 공유합니다. opensearch-py
    의 연결 풀은 스레드 안전하고, FastMCP 는 동기 도구를 스레드풀에서 돌리므로 동시 검색이
    안전합니다(요청마다 재접속하지 않습니다).
  - stateless_http=True / json_response=True 로 둡니다. 세션 상태를 안 들고(로드밸런서
    뒤에서 sticky 세션이 필요 없음), 응답을 SSE 스트림이 아닌 평범한 JSON 한 방으로 줘서
    자체 파이프라인의 HTTP 클라이언트가 그냥 POST→JSON 으로 호출하기 쉽습니다.

보안 메모: 포트를 여는 순간 네트워크 표면이 생깁니다. 이 도구는 직원 PII(전화번호 등)를
돌려주므로, 사내망 안쪽(방화벽/사설 대역)에서만 접근되게 두세요. 외부에 노출해야 하면
리버스 프록시에서 인증을 거십시오 — 이 파일은 인증을 처리하지 않습니다.

실행 전 준비: member_info_search.py 상단의 접속 상수(host/user/password)를 채워야 하고,
인덱스가 생성되어 데이터가 적재돼 있어야 합니다.
"""

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from ops_store.examples.member_info_search import (
    create_member_search_service,
    filter_members as _filter_members,
    get_member as _get_member,
    search_members as _search_members,
)

# 서버 기동 시 연결을 한 번만 연다 — 도구 호출마다 재사용한다(호출당 재접속 금지).
# 별도 서버에서 이 한 연결을 모든 RAG 요청이 공유한다.
_search = create_member_search_service()

# 별도 서버 + HTTP 운영용 설정. host/port 는 환경변수로 덮어쓸 수 있다.
#   - host 0.0.0.0: 다른 머신(RAG 파이프라인)에서 접속 가능하게 바인딩.
#   - stateless_http: 세션을 안 들어 로드밸런서 뒤에서 sticky 세션이 필요 없음.
#   - json_response: SSE 스트림 대신 평범한 JSON 응답 → 자체 HTTP 클라이언트가 호출하기 쉬움.
_HOST = os.environ.get("MEMBER_INFO_MCP_HOST", "0.0.0.0")
_PORT = int(os.environ.get("MEMBER_INFO_MCP_PORT", "8000"))

mcp = FastMCP(
    "member-info",
    host=_HOST,
    port=_PORT,
    stateless_http=True,
    json_response=True,
)

# LLM 에 돌려줄 때 남길 필드들 — 원본 응답 전체가 아니라 context 로 쓸모 있는 것만 추린다.
# 신원·소속·역할·근무지·연락처를 한 줄에 모아, 한 사람을 설명하기에 충분하되 과하지 않게.
_CONTEXT_FIELDS = (
    "EMP_NO",         # 사번 (_id, 정확 조회 키)
    "NAME_KOR",       # 이름
    "RESV014",        # 직원 레벨
    "DEPT_NAME_KOR",  # 부서
    "PART_NAME_KO",   # 파트
    "JOB_NAME_KOR",   # 직무
    "RESP_CONT",      # 담당 업무(자유 서술) — '이 사람이 무엇을 하는지'의 핵심
    "CENTRIC",        # 근무 캠퍼스
    "PLACE_OF_WORK",  # 근무 위치
    "WGRP_NAM",       # 근무 형태(유연근무 / 교대 근무)
    "OFFICE_TEL_NO",  # 사무실 전화
    "MOBILE_TEL_NO",  # 휴대전화
)

# 한 번에 돌려주는 인원 상한 — LLM 이 큰 size 를 부르면 context 가 폭발하므로 막는다.
# (환경 의존 가드레일이 아니라, 프로토콜 차원의 토큰 보호라 둔다.)
_MAX_SIZE = 50


def _record(source: dict[str, Any]) -> dict[str, Any]:
    """한 사람의 _source 에서 context 필드만 골라 평평한 dict 로 만든다(없는 값은 생략)."""
    return {
        field: source[field]
        for field in _CONTEXT_FIELDS
        if source.get(field) is not None
    }


def _shape(response: dict[str, Any]) -> list[dict[str, Any]]:
    """OpenSearch 검색 응답을 LLM 이 읽기 좋은 레코드 목록으로 추린다."""
    return [_record(hit["_source"]) for hit in response["hits"]["hits"]]


@mcp.tool()
def find_members(
    text: str,
    match_all: bool = True,
    phrase: bool = False,
    size: int = 10,
) -> list[dict]:
    """이름·부서·파트·직무·담당업무(RESP_CONT)를 한 칸에서 한꺼번에 검색합니다(구글식 통합 검색).

    어떤 사람을 막연히 찾을 때 가장 먼저 쓰는 도구입니다. text 는 공백·쉼표로 단어들로
    나뉘고, 한국어 형태소 분석(nori)을 거치므로 "검사"가 "검사를"/"장비 검사"까지 잡습니다.
    조건을 정확히 아는 게 아니라 '관련된 사람'을 찾을 때 쓰세요.

    매개변수:
      - text: 검색어. 예) "VeritySEM 청주", "결함 분석", "THK Recipe 작성".
      - match_all: True(기본)면 모든 단어가 들어가야 함(AND, 더할수록 좁아짐).
        False 면 한 단어만 맞아도 됨(OR, 넓게 찾기).
      - phrase: True 면 "CG6300" 같은 장비 코드를 토큰이 흩어지지 않게 정확히 매칭합니다.
      - size: 돌려줄 인원 수(최대 50).

    반환: 사람별 레코드 목록(사번·이름·부서·파트·직무·담당업무·근무지·연락처).
    부서명을 정확히 알거나 캠퍼스/근무형태 등으로 좁히려면 filter_members 를 쓰세요.
    """
    response = _search_members(
        _search, text, size=min(size, _MAX_SIZE), match_all=match_all, phrase=phrase
    )
    return _shape(response)


@mcp.tool()
def filter_members(
    text: str | None = None,
    dept: str | None = None,
    part: str | None = None,
    campus: str | None = None,
    work_place: str | None = None,
    work_group: str | None = None,
    level: str | None = None,
    match_all: bool = True,
    phrase: bool = False,
    size: int = 20,
) -> list[dict]:
    """정확히 아는 조건들로 좁혀 직원을 찾습니다(통합 검색 text 와 조합 가능).

    "청주 캠퍼스의 계측기술팀 교대근무자"처럼 조건이 분명할 때 쓰는 도구입니다. 아래
    facet 들은 모두 정확 일치(글자 그대로)이며 서로 AND 로 묶입니다. 준 것만 적용되고
    나머지는 무시되니, 아는 조건만 채우세요. 부분/유사 검색이 필요한 값은 facet 이 아니라
    text 로 넘기세요.

    매개변수(모두 선택):
      - text: 통합 검색어(search_all, find_members 와 동일한 nori 검색). 비우면 facet 만으로 거름.
      - dept: 부서명 정확히. 예) "계측기술팀".
      - part: 파트명 정확히.
      - campus: 근무 캠퍼스(CENTRIC). 예) "청주", "이천".
      - work_place: 근무 위치(PLACE_OF_WORK).
      - work_group: 근무 형태(WGRP_NAM). 예) "교대 근무", "유연근무".
      - level: 직원 레벨(RESV014). 코드를 글자 그대로.
      - match_all/phrase: text 가 있을 때만 의미 — find_members 와 동일.
      - size: 돌려줄 인원 수(최대 50).

    반환: 사람별 레코드 목록(find_members 와 같은 형태).
    """
    response = _filter_members(
        _search,
        text=text,
        dept=dept,
        part=part,
        campus=campus,
        work_place=work_place,
        work_group=work_group,
        level=level,
        match_all=match_all,
        phrase=phrase,
        size=min(size, _MAX_SIZE),
    )
    return _shape(response)


@mcp.tool()
def lookup_member(emp_no: str) -> dict | None:
    """사번(EMP_NO)으로 한 명을 정확히 조회합니다. 해당 사번이 없으면 null 을 돌려줍니다.

    사번을 이미 아는 경우의 가장 빠른 길입니다(검색이 아니라 _id 단일 조회). 이름으로
    찾을 때는 find_members 를 쓰세요.
    """
    member = _get_member(_search, emp_no)
    return _record(member["_source"]) if member else None


if __name__ == "__main__":
    # 기본은 HTTP(별도 서버 운영). 로컬 디버깅 때만 MEMBER_INFO_MCP_TRANSPORT=stdio 로 전환.
    transport = os.environ.get("MEMBER_INFO_MCP_TRANSPORT", "streamable-http")
    mcp.run(transport=transport)
