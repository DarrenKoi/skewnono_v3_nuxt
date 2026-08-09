"""CD/HV 전용 e-beam 라우트가 공유하는 `<tool_slug>` 검증.

여기 모아둔 이유는 오류 메시지 때문입니다. `"tool_slug must be 'cdsem' or
'hvsem'"` 라는 f-string 이 라우트 14곳에 하드코딩돼 있었고, 레지스트리가 4계열로
넓어지자 14개 전부가 한꺼번에 낡았습니다 — 아무것도 깨지지 않은 채로. 메시지를
레지스트리(`SEM_TOOL_SLUGS`)에서 파생시키면 계열이 늘거나 줄어도 문구가 저절로
따라옵니다. `meas_hist/routes.py` 가 tool_type 축에서 이미 쓰는 방식과 같습니다.

`_tool_specs.py` 가 아니라 별도 모듈인 이유: 저쪽은 Flask 를 모르는 순수
레지스트리이고, 여기는 `jsonify` 응답을 만듭니다.
"""

from __future__ import annotations

from flask import jsonify

from back_dev_home.ebeam._tool_specs import (
    SEM_TOOL_SLUGS,
    SLUG_TO_TOOL_TYPE,
    ToolType,
)


def sem_tool_slug_error_message() -> str:
    """레지스트리에서 파생한 400 본문 문구."""
    allowed = " or ".join(repr(slug) for slug in sorted(SEM_TOOL_SLUGS))
    return f"tool_slug must be {allowed}"


def bad_tool_slug_response():
    """CD/HV 전용 라우트가 모르는 슬러그에 돌려주는 400.

    501 이 아니라 400 인 것은 기존 오류 계약 그대로입니다 — 이 브랜치 이전에도
    veritysem/provision 은 400 이었습니다.
    """
    return jsonify({"error": sem_tool_slug_error_message()}), 400


def resolve_sem_tool_type(tool_slug: str) -> ToolType | None:
    """CD/HV 슬러그만 tool_type 으로 풀고, 나머지는 None.

    `resolve_tool_type_from_slug()` 와 다릅니다: 저쪽은 네 계열을 전부 풀어주는
    레지스트리 조회이고, 이쪽은 "이 화면이 담는 범위인가" 라는 질문입니다.
    """
    slug = (tool_slug or "").strip().lower()
    if slug in SEM_TOOL_SLUGS:
        return SLUG_TO_TOOL_TYPE[slug]  # type: ignore[index]
    return None


def is_sem_tool_slug(tool_slug: str) -> bool:
    return (tool_slug or "").strip().lower() in SEM_TOOL_SLUGS
