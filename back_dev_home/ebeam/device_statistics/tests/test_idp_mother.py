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
#
# ``Region`` 은 image definition 묶음입니다 (user-confirmed 2026-08-18) — 세 row 가
# 같은 Region 1 이므로 한 SEQ 그룹이고, 화면에는 "1/3, 2/3, 3/3" 으로 보입니다.
# WAFER 가 그 image 의 주인(Mother_Para)이고 LEVEL·EDGE 는 같은 image 에서 자기
# cd_value 를 꺼내는 son 입니다.
_ROWS = [
    {"Parameter": "WAFER", "Mother_Para": True, "SEQ": 1, "Region": 1},
    {"Parameter": "LEVEL", "Mother_Para": False, "SEQ": 2, "Region": 1},
    {"Parameter": "EDGE", "Mother_Para": False, "SEQ": 3, "Region": 1},
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


# ────────────────────── raw_data -> Region (SEQ 그룹) ──────────────────────
#
# Region 이 없으면 프론트엔드의 판정이 파라미터마다 자기 cap 으로 돌아가고,
# WAFER(13) mother 의 son 이 이름 때문에 _other(9)에 걸려 고칠 수 없는 위반이
# 됩니다 (utils/ruleEngine.groupCaps). mock 은 이 묶음을 늘 온전히 만들어 내므로
# "원천이 Region 을 안 준다" 는 경우를 재현하지 못합니다 — 그 자리가 여기입니다.


def test_reads_region_from_the_confirmed_row_list():
    assert oe._param_regions(_ROWS) == {"WAFER": 1, "LEVEL": 1, "EDGE": 1}


def test_missing_region_is_an_empty_dict_not_a_guess():
    # 묶을 근거가 없으면 묶지 않습니다. 순서로 추측하면 son 에게 엉뚱한 mother 의
    # cap 이 가고, 그 차이는 예외가 아니라 위반 수로만 나타납니다.
    rows = [{"Parameter": name, "Mother_Para": False} for name in ("WAFER", "LEVEL")]
    assert oe._param_regions(rows) == {}
    assert oe._param_regions(None) == {}
    assert oe._param_regions([]) == {}


def test_region_survives_a_string_typed_ingest():
    # Mother_Para 가 문자열로 실려 온 전례가 있으므로 Region 도 그럴 수 있습니다.
    rows = [{"Parameter": "WAFER", "Region": "2"}]
    assert oe._param_regions(rows) == {"WAFER": 2}


def test_first_row_wins_when_a_parameter_repeats():
    # 한 row 는 image definition 1개이므로 같은 Parameter 가 여러 row 에 나올 수
    # 있습니다 (recipe_idp.txt). 이 표면의 단위는 parameter 라 먼저 나온 것을 씁니다.
    rows = [
        {"Parameter": "WAFER", "Region": 1},
        {"Parameter": "WAFER", "Region": 4},
    ]
    assert oe._param_regions(rows) == {"WAFER": 1}


def test_region_from_a_column_oriented_blob():
    # 이 형태는 _raw_data_rows 가 row 를 **다시 조립**하므로, Region 을 함께 싣지
    # 않으면 이 형태의 문서만 조용히 묶음을 잃습니다.
    blob = {
        "Parameter": {"0": "WAFER", "1": "LEVEL"},
        "Mother_Para": {"0": True, "1": False},
        "Region": {"0": 1, "1": 1},
    }
    assert oe._param_regions(blob) == {"WAFER": 1, "LEVEL": 1}
    assert oe._mother_names(blob) == {"WAFER"}


def test_region_from_a_blob_keyed_by_parameter_name():
    blob = {
        "WAFER": {"Mother_Para": True, "Region": 1},
        "EDGE": {"Mother_Para": False, "Region": 2},
    }
    assert oe._param_regions(blob) == {"WAFER": 1, "EDGE": 2}


def test_region_from_the_blob_wrapping_the_three_idp_tables():
    blob = {
        "idp_image_info": _ROWS,
        "wafer_mp_info": [{"P_No": 1}],
        "wafer_align_info": [{"P.No": 1}],
    }
    assert oe._param_regions(blob) == {"WAFER": 1, "LEVEL": 1, "EDGE": 1}


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
