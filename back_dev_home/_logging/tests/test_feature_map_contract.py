"""Contract test: page_to_feature must return the slug the shared fixture claims.

The frontend's resolvePageIdentity and the backend's page_to_feature must
partition pages identically: two paths produce the same identity IFF the backend
maps them to the same slug. The fixture in
front-dev-home/app/utils/__fixtures__/pageIdentityContract.json is the shared
table; this half pins the slug column, and the frontend test pins the identity
partition against the same column.

page_to_feature already takes a query-inclusive FRONTEND path, so there is no
translation step here — feeding it an /api/... path would test the wrong
function against the wrong vocabulary.
"""

import json
from pathlib import Path

import pytest

from back_dev_home._logging import feature_map

_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / 'front-dev-home/app/utils/__fixtures__/pageIdentityContract.json'
)


def load_contract():
    """Load the shared fixture from the frontend."""
    with open(_FIXTURE, encoding='utf-8') as handle:
        return json.load(handle)


def contract_path(row) -> str:
    """The row's path with its query re-attached, as a router would present it."""
    query = row.get('query') or {}
    if not query:
        return row['path']
    pairs = []
    for key, value in query.items():
        if isinstance(value, list):
            value = value[0] if value else ''
        pairs.append(f'{key}={value}')
    return row['path'] + '?' + '&'.join(pairs)


@pytest.mark.parametrize(
    'fixture_row', load_contract(), ids=lambda row: f"{contract_path(row)} -> {row['slug']}"
)
def test_backend_maps_correctly(fixture_row):
    """Verify page_to_feature maps each fixture path to its expected slug."""
    path = contract_path(fixture_row)
    expected = fixture_row['slug']
    actual = feature_map.page_to_feature(path)

    assert actual == expected, (
        f"page_to_feature({path!r}) returned {actual!r}, fixture expects {expected!r}"
    )
