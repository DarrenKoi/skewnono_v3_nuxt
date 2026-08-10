"""Home-runnable regression tests for the tracked office adapter template.

사무실 Redis/OpenSearch 는 집에서 닿지 않으므로 카탈로그 읽기만 가짜로
바꾸고 조인 로직은 진짜를 돌립니다. office.py 는 이 템플릿의 사본이라,
여기서 잡히지 않는 실수는 사무실에서 처음 드러납니다.
"""

import pytest

from back_dev_home.ebeam.device_statistics.providers import office_example


_R3 = [{"lot_cd": "R001", "fac_id": "R3", "ctn_desc": "R3 설명", "prod_catg_cd": "DRAM"}]
_HVM = [{"lot_cd": "R001", "fac_id": "M16", "ctn_desc": "M16 설명", "tech_nm": "TP"}]


@pytest.fixture(autouse=True)
def _overlapping_catalogs(monkeypatch):
    """같은 lot_cd 가 두 카탈로그에 모두 있는 상황 — mock 은 만들지 못합니다."""
    monkeypatch.setattr(office_example, "_r3_rows", lambda: list(_R3))
    monkeypatch.setattr(office_example, "_hvm_rows", lambda: list(_HVM))
    office_example._lot_index.cache_clear()
    office_example._lot_meta.cache_clear()
    yield
    office_example._lot_index.cache_clear()
    office_example._lot_meta.cache_clear()


def test_lot_index_and_lot_meta_resolve_the_same_catalog():
    """한 파일 안의 두 함수가 서로 반대 순서였습니다.

    _lot_index 는 r3→hvm 이라 M 이 이기고, _lot_meta 는 hvm→r3 이라 R3 가
    이겼습니다. 그래서 겹치는 lot 은 fac_id 를 M-fab 행에서, ctn_desc 를 R3
    행에서 가져오는 잡종이 됐습니다 — 어느 쪽 우선순위를 고르든 버그입니다.
    """
    assert office_example._lot_index()["R001"] == "M16"
    assert office_example._lot_meta()["R001"]["ctn_desc"] == "M16 설명"


def test_m_fab_wins_an_overlapping_lot_cd():
    """user-confirmed 2026-08-10 — device_desc 가 현재 상태를 반영합니다."""
    meta = office_example._lot_meta()["R001"]
    assert meta["ctn_desc"] == "M16 설명"
    # M-fab device 는 원천에 prod_catg_cd 가 없으므로 "" 이고,
    # memory_class_auto 는 "unknown"(수동 분류)으로 떨어집니다.
    assert meta["prod_catg_cd"] == ""
    assert not office_example._is_r3(office_example._lot_index()["R001"])
