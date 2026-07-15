"""member_info 디렉터리 인덱스를 검색하는 독립 실행형(standalone) 예제입니다.

이 파일은 테스트가 아니며 다른 코드에서 import 하지도 않습니다. 실제 클러스터에 바로
돌려 볼 수 있도록 "복사해서 쓰는" 참고용 코드예요. 검색에 필요한 모든 것 — 접속 정보,
어떤 필드를 어떻게 검색할지, 그리고 검색 헬퍼 함수 — 이 한 파일 안에 다 들어 있어서
ops_index_mgmt 패키지에 의존하지 않습니다(그 패키지는 인덱스를 '만드는' 일만 담당해요).
바깥에서 가져오는 것은 ops_store 하나뿐입니다.

member_info 인덱스(ops_index_mgmt/member_info.py 가 생성)는 몇 가지 정해진 검색 형태에
맞춰 설계되어 있습니다. 아래 헬퍼들은 각 검색에 맞는 필드를 미리 골라 두었으니, nori 로
분석되는 텍스트 필드와 정확히 일치해야 하는 keyword 필드를 헷갈릴 걱정은 안 하셔도 됩니다.

  - search_members : 구글처럼 한 칸에 여러 단어를 넣는 통합 검색입니다. 검색어를 공백과
    쉼표로 나눠서 search_all(이름·부서·파트·직무·RESP_CONT 가 모두 모이는 nori 필드)을
    검색해요. "VeritySEM, 청주", "CG6300, GT2000", "THK Recipe 작성" 같은 입력이 모두
    동작합니다. 기본은 모든 단어가 들어가야 하는 AND(단어를 더할수록 좁아짐, 구글과 동일),
    match_all=False 면 하나만 맞아도 되는 OR 입니다. 장비 코드를 정확히 찾고 싶을 때는
    phrase=True 를 쓰세요.
  - members_in_dept : DEPT_NAME_KOR(정확히 일치하는 keyword)로 한 부서를 통째로 보는
    필터입니다. 전문(full-text) 검색이 아니라 정확 일치예요.
  - filter_members : 통합 검색(text)과 정확일치 facet 들을 한 질의로 조합합니다. 부서·파트·
    근무 캠퍼스(CENTRIC)·근무 위치(PLACE_OF_WORK)·근무 형태(WGRP_NAM)·직원 레벨(RESV014)
    중 아는 것만 골라 끼우면 모두 AND 로 좁혀집니다. "청주 캠퍼스의 계측기술팀 교대근무자"
    처럼 조건을 겹쳐 좁힐 때 쓰세요. text 는 비워도 됩니다(facet 만으로 순수 필터). 이 facet
    필드들은 인덱스에 명시 매핑이 없어 keyword(정확일치)라 search_all 에는 안 들어가지만,
    검색 결과의 _source 안에서 전화번호(OFFICE_TEL_NO/MOBILE_TEL_NO)와 함께 그대로 읽어
    context 로 쓸 수 있습니다. members_at_campus / members_by_work_group / members_by_level
    은 자주 쓰는 한 facet 만 거는 단축 진입점입니다.
  - get_member : EMP_NO 로 한 명을 가져옵니다. EMP_NO 가 문서의 _id 라서 검색이 아니라
    단일 GET 이고, 없는 사번이면 None 을 돌려줍니다.

주의: 이 인덱스에 사용자가 입력한 원문을 query_string / simple_query_string 으로 그대로
넘기지 마세요(member_info.py 참고). RESP_CONT 는 사람들이 자유롭게 쓴 텍스트라 `-`, `*`,
`/`, 괄호가 많은데, 그 파서들은 이런 문자를 연산자로 해석합니다. 여기 헬퍼들은 match /
match_phrase / term 만 쓰므로 입력이 nori 를 거칠 뿐, 특수문자가 문법으로 해석되지 않습니다.

실행 전 준비: 인덱스가 이미 생성되어 있고 데이터가 적재(ingest)되어 있어야 결과가 나옵니다.
"""

from typing import Any

from opensearchpy.exceptions import NotFoundError

from ops_store import OSSearch, create_client

# ── 접속 정보 + 인덱스 상수 — 본인 환경에 맞게 바꿔 주세요 ──────────────────────
OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""  # 비밀번호를 채운 뒤 실행하세요.

INDEX_NAME = "member_info"
SEARCH_ALL_FIELD = "search_all"  # 읽기 좋은 필드들이 모두 모이는 통합 nori 필드
DEPT_FIELD = "DEPT_NAME_KOR"     # 부서 검색이 정확 일치로 거는 keyword 필드

# 아래는 member_info 인덱스에 명시 매핑이 없어 dynamic template 로 전부 keyword(정확
# 일치)가 되는 facet 필드들입니다. search_all(nori 전문검색)에는 안 들어가므로 자유 입력
# 으로는 못 찾고 term 필터로만 좁힙니다. 대신 검색 결과의 _source 안에서 그대로 읽어
# context 로 쓸 수 있어요(전화번호처럼 검색 대상은 아니지만 보여 줄 값들이 여기 모입니다).
PART_FIELD = "PART_NAME_KO"          # 파트 이름
CAMPUS_FIELD = "CENTRIC"             # 근무 캠퍼스 위치
WORK_PLACE_FIELD = "PLACE_OF_WORK"   # 근무 위치
WORK_GROUP_FIELD = "WGRP_NAM"        # 근무 형태 (유연근무 / 교대 근무)
LEVEL_FIELD = "RESV014"              # 직원 레벨
OFFICE_TEL_FIELD = "OFFICE_TEL_NO"   # 사무실 전화 (검색용 아님, context 표시용)
MOBILE_TEL_FIELD = "MOBILE_TEL_NO"   # 휴대전화 (검색용 아님, context 표시용)


def create_member_search_service(client: Any | None = None) -> OSSearch:
    """member_info 인덱스에 연결된 OSSearch 를 돌려줍니다. client 가 없으면 새로 만듭니다.

    client 를 주지 않으면 위의 상수로 접속(ops_store 의 create_client)을 새로 엽니다.
    그래서 스크립트 한 줄로 바로 검색할 수 있어요:

        search_members(create_member_search_service(), "검사")

    이미 열어 둔 연결을 재사용하고 싶다면 client 를 직접 넘겨 주세요.
    """
    actual_client = client or create_client(
        host=OPENSEARCH_HOST,
        user=OPENSEARCH_USER,
        password=OPENSEARCH_PASSWORD,
    )
    return OSSearch(client=actual_client, index=INDEX_NAME)


def split_search_terms(text: str) -> list[str]:
    """구글식 검색어를 공백과 쉼표 기준으로 단어 목록으로 나눕니다.

    쉼표와 공백은 똑같은 구분자로 취급합니다 — "VeritySEM, 청주", "VeritySEM 청주",
    "VeritySEM,청주" 가 모두 ``["VeritySEM", "청주"]`` 가 돼요. 구분자가 겹치거나 끝에
    붙어서 생기는 빈 조각은 버립니다.
    """
    return [term for term in text.replace(",", " ").split() if term]


def _text_clauses(text: str, *, phrase: bool = False) -> list[dict[str, Any]]:
    """search_all 한 필드에 대한 '단어별' match(또는 match_phrase) 절 목록을 만듭니다.

    search_members 와 filter_members 가 공유하는 내부 헬퍼예요. text 를 공백·쉼표로 나눠
    각 단어를 하나의 절로 만듭니다. phrase=True 면 match 대신 match_phrase 를 써서
    "CG6300" 같은 장비 코드의 토큰(cg + 6300)이 흩어지지 않고 붙어서 매칭되게 합니다.
    """
    query_type = "match_phrase" if phrase else "match"
    return [
        {query_type: {SEARCH_ALL_FIELD: term}}
        for term in split_search_terms(text)
    ]


def search_members(
    search: OSSearch,
    text: str,
    *,
    size: int = 10,
    match_all: bool = True,
    phrase: bool = False,
    as_dataframe: bool = False,
) -> Any:
    """구글식 통합 검색입니다. search_all 한 필드에서 여러 단어를 찾습니다.

    text 는 공백과 쉼표로 단어들로 나뉘고(split_search_terms), 각 단어가 search_all 에 대한
    하나의 검색 절이 됩니다. search_all 에는 이름·부서·파트·직무·RESP_CONT 가 모두 모여
    있어서 한 번의 질의로 전부 훑을 수 있고, 양쪽 모두 nori 를 거치므로 "검사"가
    "검사를"/"장비 검사" 까지 잡아 줍니다. 이렇게 쓸 수 있어요:

        search_members(search, "VeritySEM, 청주")              # 장비 AND 사이트
        search_members(search, "THK Recipe 작성")               # 세 단어 모두 필요
        search_members(search, "CG6300, GT2000", match_all=False)  # 둘 중 하나만
        search_members(search, "CG6300", phrase=True)           # 코드 정확 매칭

    매개변수 안내
      - match_all=True (기본): 모든 단어가 들어가야 함(bool.must). 단어를 더할수록 결과가
        좁아집니다 — 구글과 같은 방식이에요.
      - match_all=False: 한 단어만 맞아도 됨(bool.should, OpenSearch 가 minimum_should_match
        를 1 로 처리). 많이 맞을수록 위로 올라오는 넓은 "아무거나" 검색입니다.
      - phrase=True: 각 단어를 match 대신 match_phrase 로 검색합니다. nori 가 "CG6300" 을
        cg + 6300 처럼 쪼개도, match_phrase 는 그 토큰들이 '붙어서 순서대로' 나와야만 맞으므로
        장비 코드를 정확히 찾을 때 좋습니다. (일반 match 는 cg 만 든 다른 문서도 잡을 수 있어요.)

    반환값은 OpenSearch 원본 응답입니다(각 hit 의 `_source` 안에 사번 정보가 들어 있어요).
    as_dataframe=True 면 hit 들을 평평한 pandas DataFrame 으로 받습니다.
    """
    clauses = _text_clauses(text, phrase=phrase)
    if match_all:
        result = search.bool(must=clauses, size=size)  # 모든 단어 필요(AND)
    else:
        result = search.bool(should=clauses, size=size)  # 하나만 맞아도 됨(OR)
    if as_dataframe:
        return search.to_dataframe(result)
    return result


def members_in_dept(
    search: OSSearch,
    dept: str,
    *,
    size: int = 200,
    as_dataframe: bool = False,
) -> Any:
    """한 부서를 통째로 보기: DEPT_NAME_KOR 에 대한 정확 일치(term) 검색입니다.

    전문 검색이 아니라 '필터'예요. DEPT_NAME_KOR 는 정확히 일치하는 keyword 라서 dept 는
    부서명을 글자 그대로 정확히 넣어야 합니다(부분/유사 검색은 search_members 를 쓰세요).
    size 기본값은 한 팀 전체가 한 페이지에 들어오도록 200 으로 두었습니다. 반환값은 원본
    응답이며, as_dataframe=True 면 DataFrame 으로 받습니다.
    """
    result = search.term(DEPT_FIELD, dept, size=size)
    if as_dataframe:
        return search.to_dataframe(result)
    return result


def filter_members(
    search: OSSearch,
    *,
    text: str | None = None,
    dept: str | None = None,
    part: str | None = None,
    campus: str | None = None,
    work_place: str | None = None,
    work_group: str | None = None,
    level: str | None = None,
    match_all: bool = True,
    phrase: bool = False,
    size: int = 50,
    as_dataframe: bool = False,
) -> Any:
    """통합 검색(text)과 정확일치 facet 들을 한 질의로 조합해 좁힙니다.

    RAG context 를 만들 때 가장 유연한 진입점이에요. 자유 입력 한 칸(text, search_all 에
    대한 구글식 검색)에 더해, 정확히 아는 조건들 — 부서(dept)·파트(part)·근무 캠퍼스
    (campus=CENTRIC)·근무 위치(work_place=PLACE_OF_WORK)·근무 형태(work_group=WGRP_NAM)·
    직원 레벨(level=RESV014) — 을 골라 끼울 수 있습니다. 준 facet 들은 모두 정확 일치(term)
    이고 서로 AND 로 묶이며, term 은 점수에 영향을 주지 않는 filter 라서 빠르고 캐시됩니다.

        filter_members(search, text="검사", campus="청주")               # 청주 캠퍼스의 '검사' 관련자
        filter_members(search, dept="계측기술팀", work_group="교대 근무")   # 그 팀의 교대근무자
        filter_members(search, level="G3", part="THK파트")               # text 없이 facet 만으로

    매개변수 안내
      - text 를 비우면(None) facet 만으로 거르는 순수 필터가 됩니다(점수 없이 정확 일치).
      - text 가 있으면 match_all=True(기본)는 모든 단어 필요(AND), match_all=False 는 한
        단어만 맞아도 됨(OR). phrase=True 면 단어들을 match_phrase 로 정확 매칭합니다.
      - facet 값은 keyword 라 글자 그대로 정확히 넣어야 합니다(부분 일치는 text 를 쓰세요).

    반환값은 OpenSearch 원본 응답이며, as_dataframe=True 면 평평한 DataFrame 으로 받습니다.
    """
    facets = {
        DEPT_FIELD: dept,
        PART_FIELD: part,
        CAMPUS_FIELD: campus,
        WORK_PLACE_FIELD: work_place,
        WORK_GROUP_FIELD: work_group,
        LEVEL_FIELD: level,
    }
    filter_clauses = [
        {"term": {field: value}}
        for field, value in facets.items()
        if value is not None
    ]

    must_clauses: list[dict[str, Any]] | None = None
    if text:
        text_clauses = _text_clauses(text, phrase=phrase)
        if match_all:
            must_clauses = text_clauses  # 모든 단어 필요(AND)
        else:
            # OR 검색은 nested bool(should 만 든)로 감싸서 must 에 넣는다. should 절을 filter
            # 와 같은 층에 두면 minimum_should_match 가 1→0 으로 풀려 '하나 이상 맞아야 함'이
            # 사라지고 facet 만으로 전부 통과해 버리는 게 OpenSearch 의 함정이다. nested bool
            # 안에는 filter 가 없어 기본 minimum_should_match 1 이 그대로 유지된다.
            must_clauses = [{"bool": {"should": text_clauses}}]

    result = search.bool(must=must_clauses, filter=filter_clauses or None, size=size)
    if as_dataframe:
        return search.to_dataframe(result)
    return result


def members_at_campus(
    search: OSSearch,
    campus: str,
    *,
    size: int = 200,
    as_dataframe: bool = False,
) -> Any:
    """한 근무 캠퍼스(CENTRIC) 전원을 나열합니다 — 정확 일치 필터입니다.

    filter_members(campus=...) 의 읽기 좋은 이름의 단축 진입점이에요. size 기본값은 한
    캠퍼스 인원이 한 페이지에 들어오도록 200 으로 두었습니다.
    """
    return filter_members(search, campus=campus, size=size, as_dataframe=as_dataframe)


def members_by_work_group(
    search: OSSearch,
    work_group: str,
    *,
    size: int = 200,
    as_dataframe: bool = False,
) -> Any:
    """근무 형태(WGRP_NAM, 예: "교대 근무"/"유연근무")로 거릅니다 — 정확 일치 필터입니다.

    filter_members(work_group=...) 의 단축 진입점이에요. 부서 안에서 교대근무자만 보고
    싶을 때처럼 다른 조건과 함께 좁히려면 filter_members 를 직접 쓰세요.
    """
    return filter_members(search, work_group=work_group, size=size, as_dataframe=as_dataframe)


def members_by_level(
    search: OSSearch,
    level: str,
    *,
    size: int = 200,
    as_dataframe: bool = False,
) -> Any:
    """직원 레벨(RESV014)로 거릅니다 — 정확 일치 필터입니다.

    filter_members(level=...) 의 단축 진입점이에요. RESV014 는 keyword 라 레벨 코드를 글자
    그대로 정확히 넣어야 합니다.
    """
    return filter_members(search, level=level, size=size, as_dataframe=as_dataframe)


def get_member(search: OSSearch, emp_no: Any) -> dict[str, Any] | None:
    """EMP_NO 로 한 명을 가져옵니다. 해당 사번이 없으면 None 을 돌려줍니다.

    EMP_NO 가 문서의 _id 라서 이건 검색이 아니라 단일 GET 입니다 — 가장 빠른 길이고, 점수
    계산도 없어요. emp_no 는 적재(ingest) 때 _id 를 만든 방식과 맞추기 위해 str 로 변환합니다.
    반환값은 GET 원본 응답입니다(사번 정보는 `_source` 안에 있어요). 없는 사번이면 예외를
    던지지 않고 None 을 반환합니다.
    """
    try:
        return search.client.get(index=INDEX_NAME, id=str(emp_no))
    except NotFoundError:
        return None


def example_one_box_search() -> None:
    """기본 사용법: 구글처럼 한 칸에, 공백이나 쉼표로 단어를 나눠서 검색합니다.

    모든 단어가 들어가야 하므로(AND) "VeritySEM, 청주" 는 그 장비를 다루면서 그 사이트에
    있는 사람을 찾습니다. 단어를 더할수록 결과가 좁아져요 — 구글과 같습니다.
    """
    search = create_member_search_service()
    for text in ("VeritySEM, 청주", "THK Recipe 작성"):
        result = search_members(search, text, size=20)
        print(f"\n=== {text} ===")
        for hit in result["hits"]["hits"]:
            src = hit["_source"]
            print(hit["_score"], src.get("NAME_KOR"), src.get("DEPT_NAME_KOR"))


def example_exact_tool_code() -> None:
    """장비 코드를 정확히 찾기: phrase=True 로 코드 토큰이 흩어지지 않게 합니다.

    nori 가 "CG6300" 을 cg + 6300 처럼 쪼개도, match_phrase 는 두 토큰이 붙어서 순서대로
    나와야만 맞기 때문에 코드 그대로만 잡힙니다.
    """
    search = create_member_search_service()
    result = search_members(search, "CG6300", phrase=True, size=20)
    for hit in result["hits"]["hits"]:
        print(hit["_score"], hit["_source"].get("NAME_KOR"))


def example_any_of_these_terms() -> None:
    """넓게 찾기: 모든 단어가 아니라 '아무거나' 하나만 맞아도 되게(OR) 합니다.

    "CG6300, GT2000" 을 match_all=False 로 검색하면 둘 중 하나라도 관련된 사람을 모두
    찾고, 둘 다 맞는 사람이 위로 올라옵니다.
    """
    search = create_member_search_service()
    result = search_members(search, "CG6300, GT2000", match_all=False, size=20)
    for hit in result["hits"]["hits"]:
        print(hit["_score"], hit["_source"].get("NAME_KOR"))


def example_one_box_search_as_dataframe() -> None:
    """같은 통합 검색을 평평한 pandas DataFrame 으로 받는 예시입니다."""
    search = create_member_search_service()
    df = search_members(search, "결함 분석 청주", size=50, as_dataframe=True)
    print(df[["NAME_KOR", "DEPT_NAME_KOR", "JOB_NAME_KOR"]])


def example_browse_a_department() -> None:
    """부서명을 정확히 넣어 한 팀 전체를 나열합니다(전문 검색이 아닌 필터)."""
    search = create_member_search_service()
    result = members_in_dept(search, "계측기술팀")
    print("인원 수:", result["hits"]["total"]["value"])
    for hit in result["hits"]["hits"]:
        print(hit["_source"].get("NAME_KOR"))


def example_filter_text_and_campus() -> None:
    """통합 검색 + 정확일치 facet 조합: 청주 캠퍼스의 '검사' 관련자.

    text 는 search_all 을 nori 로 훑고, campus 는 CENTRIC 에 정확 일치 필터를 겁니다.
    전화번호처럼 검색 대상은 아니어도 _source 안에 그대로 들어 있어 함께 출력할 수 있어요.
    """
    search = create_member_search_service()
    result = filter_members(search, text="검사", campus="청주", size=20)
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        print(src.get("NAME_KOR"), src.get("CENTRIC"), src.get("MOBILE_TEL_NO"))


def example_filter_facets_only() -> None:
    """text 없이 facet 만으로: 한 팀의 교대근무자 명단(점수 없는 순수 정확 일치 필터)."""
    search = create_member_search_service()
    result = filter_members(search, dept="계측기술팀", work_group="교대 근무", size=50)
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        print(src.get("NAME_KOR"), src.get("WGRP_NAM"), src.get("PLACE_OF_WORK"))


def example_lookup_by_emp_no() -> None:
    """EMP_NO 로 한 명을 정확히 조회합니다 — _id 에 대한 단일 GET 입니다."""
    search = create_member_search_service()
    member = get_member(search, "12345")
    if member is None:
        print("해당 사번 없음")
    else:
        print(member["_source"])


def example_reuse_one_connection() -> None:
    """연결을 한 번만 열고 여러 검색을 이어서 실행합니다.

    create_member_search_service 는 client 가 없으면 새로 만들지만, 직접 client 를 넘기면
    여러 호출에서 같은 연결을 재사용할 수 있습니다(적재용으로 이미 연 연결을 함께 써도 돼요).
    """
    client = create_client(
        host=OPENSEARCH_HOST,
        user=OPENSEARCH_USER,
        password=OPENSEARCH_PASSWORD,
    )
    search = create_member_search_service(client)
    print(search_members(search, "검사")["hits"]["total"])
    print(members_in_dept(search, "계측기술팀")["hits"]["total"])
