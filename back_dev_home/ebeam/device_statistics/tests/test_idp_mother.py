"""cdsem_idp_ver 의 세 field 를 읽는 순수 함수들 — office adapter.

이 세 함수(``_mother_names`` / ``_raw_data_rows`` / ``_ordered_parameters``)는
office 문서를 입력으로 받을 뿐 OpenSearch 를 만지지 않으므로, 집에서 그대로
돌릴 수 있는 유일한 office 경로입니다. mock 은 이미 정렬된 목록과 bool mother 를
만들어 내므로 여기서 다루는 두 사고 — ``parameters`` 의 key 순서가 측정 순서가
아닌 것, ``Mother_Para`` 가 문자열로 실려 오는 것 — 를 **한 번도 재현하지
못합니다**. 그래서 이 파일이 그 자리를 대신합니다.
"""

from back_dev_home.ebeam.device_statistics.providers import office_example as oe


# ────────────────────── raw_data -> mother 이름 ──────────────────────

# 확인된 형태 (user-confirmed 2026-08-10): row dict 의 list.
_ROWS = [
    {"Parameter": "WAFER", "Mother_Para": True, "SEQ": 1},
    {"Parameter": "LEVEL", "Mother_Para": False, "SEQ": 2},
    {"Parameter": "EDGE", "Mother_Para": False, "SEQ": 3},
]


def test_reads_mother_from_the_confirmed_row_list():
    assert oe._mother_names(_ROWS) == {"WAFER"}


def test_no_mother_is_an_empty_set_not_none():
    # 빈 집합과 None 은 다른 뜻입니다 — 전자는 "읽었고 없다", 후자는 "읽을 수
    # 없다". _idp_parameters 가 남기는 경고가 이 구분으로 갈립니다.
    rows = [dict(row, Mother_Para=False) for row in _ROWS]
    assert oe._mother_names(rows) == set()


def test_missing_flag_is_none():
    rows = [{"Parameter": "WAFER", "SEQ": 1}]
    assert oe._mother_names(rows) is None
    assert oe._mother_names(None) is None
    assert oe._mother_names([]) is None


def test_string_false_does_not_become_true():
    # bool("False") is True — recipe_search 가 Addressing/dnumber_removed 에서
    # 겪은 함정입니다. 적재가 문자열로 바뀌어도 mother 가 전부 켜지면 안 됩니다.
    rows = [
        {"Parameter": "WAFER", "Mother_Para": "True"},
        {"Parameter": "LEVEL", "Mother_Para": "False"},
        {"Parameter": "EDGE", "Mother_Para": "N"},
    ]
    assert oe._mother_names(rows) == {"WAFER"}


def test_unreadable_flag_value_is_ignored_not_guessed():
    rows = [{"Parameter": "WAFER", "Mother_Para": "제일 위"}]
    assert oe._mother_names(rows) is None


def test_column_oriented_blob():
    blob = {
        "Parameter": {"0": "WAFER", "1": "LEVEL"},
        "Mother_Para": {"0": True, "1": False},
    }
    assert oe._mother_names(blob) == {"WAFER"}


def test_blob_keyed_by_parameter_name():
    blob = {
        "WAFER": {"Mother_Para": True, "SEQ": 1},
        "EDGE": {"Mother_Para": False, "SEQ": 2},
    }
    assert oe._mother_names(blob) == {"WAFER"}


def test_blob_wrapping_the_three_idp_tables():
    blob = {
        "idp_image_info": _ROWS,
        "wafer_mp_info": [{"P_No": 1}],
        "wafer_align_info": [{"P.No": 1}],
    }
    assert oe._mother_names(blob) == {"WAFER"}


# ────────────────────── parameters_list -> 측정 순서 ──────────────────────

# office 확인 2026-08-10 — 두 field 의 순서가 실제로 다릅니다.
_PARAMS = {"EDGE": 10, "LEVEL": 4, "WAFER": 10}
_ORDER = ["WAFER", "LEVEL", "EDGE"]


def test_parameters_list_decides_the_order():
    ordered = oe._ordered_parameters(_PARAMS, _ORDER)
    assert list(ordered) == _ORDER
    assert ordered == _PARAMS  # 값은 그대로, 순서만 바뀝니다


def test_absent_order_leaves_the_source_order():
    assert list(oe._ordered_parameters(_PARAMS, None)) == list(_PARAMS)
    assert list(oe._ordered_parameters(_PARAMS, [])) == list(_PARAMS)


def test_parameters_missing_from_the_list_are_appended_not_dropped():
    # 두 field 가 어긋날 때 파라미터가 화면에서 사라지는 것이 순서가 어긋나는
    # 것보다 나쁩니다.
    ordered = oe._ordered_parameters(_PARAMS, ["WAFER"])
    assert list(ordered) == ["WAFER", "EDGE", "LEVEL"]
    assert ordered == _PARAMS


def test_names_in_the_list_but_not_in_parameters_are_skipped():
    ordered = oe._ordered_parameters(_PARAMS, ["WAFER", "GHOST", "EDGE", "LEVEL"])
    assert list(ordered) == ["WAFER", "EDGE", "LEVEL"]


# ────────────────────── 질의가 실제로 세 field 를 집는가 ──────────────────────


def test_source_asks_for_every_field_the_readers_need():
    # _source 에서 빠진 field 는 예외가 아니라 "값이 없다"로 나타나므로,
    # 어느 한쪽만 고치는 것을 여기서 막습니다.
    assert "parameters" in oe._IDP_SOURCE
    assert "parameters_list" in oe._IDP_SOURCE
    assert any(field.startswith("raw_data.") for field in oe._IDP_SOURCE)
    # raw_data 를 통째로 받으면 device 당 recipe 100~200 개에 parameter 표가
    # 곱해집니다 — 그 실수를 되돌리지 못하게 못 박아 둡니다.
    assert "raw_data" not in oe._IDP_SOURCE
