"""Contract test: backend page_to_feature must match frontend identity partitioning.

The frontend's resolvePageIdentity and the backend's page_to_feature must partition
pages identically: two paths produce the same identity IFF the backend maps them to
the same slug. This test ensures drift is caught mechanically.
"""

import json
from pathlib import Path

import pytest

from .._logging import feature_map


def load_contract():
    """Load the shared fixture from the frontend."""
    # Frontend fixture path: front-dev-home/app/utils/__fixtures__/pageIdentityContract.json
    fixture_path = Path(__file__).parent.parent.parent.parent / (
        'front-dev-home/app/utils/__fixtures__/pageIdentityContract.json'
    )
    with open(fixture_path) as f:
        return json.load(f)


def convert_frontend_path_to_api(frontend_path: str) -> str:
    """Convert frontend path to backend API path for contract testing.

    Examples:
    - /ebeam/cd-sem/M14/storage → /api/cdsem/storage
    - /ebeam/hv-sem/R3/storage → /api/hvsem/storage
    - /afm/map608/a.tif → /api/afm
    - /msr-file → /api/msr-file
    - /sem-list → /api/sem-list
    - / → /api/ (special case, handled by fallback)
    """
    if not frontend_path or frontend_path == '/':
        return '/api/'

    parts = [p for p in frontend_path.split('/') if p]

    # Handle e-beam paths: /ebeam/<tool>/<fab?>/...
    if parts[0] == 'ebeam':
        if len(parts) < 2:
            return '/api/'
        tool = parts[1]
        # Normalize tool name: cd-sem → cdsem, hv-sem → hvsem
        tool_normalized = tool.replace('-', '')
        # Skip fab if present (matches fab pattern)
        page_start = 2
        if page_start < len(parts) and parts[page_start].upper() in {
            m.group(1)
            for m in [
                __import__('re').match(r'^([RM]\d{1,2}[A-C]?)$', p, __import__('re').IGNORECASE)
                for p in [parts[page_start]]
            ]
            if m
        }:
            page_start = 3
        # Rest is the page path
        page_parts = parts[page_start:]
        if page_parts:
            return f'/api/{tool_normalized}/' + '/'.join(page_parts)
        return f'/api/{tool_normalized}/'

    # Handle standalone pages: /afm, /msr-file, /sem-list, etc.
    return '/api/' + '/'.join(parts)


@pytest.mark.parametrize('fixture_row', load_contract(), ids=lambda r: f"{r['path']} → {r['slug']}")
def test_backend_maps_correctly(fixture_row):
    """Verify backend maps each fixture path to its expected slug."""
    frontend_path = fixture_row['path']
    expected_slug = fixture_row['slug']

    # Convert frontend path to backend API path
    api_path = convert_frontend_path_to_api(frontend_path)

    # Get the actual slug from the backend
    actual_slug = feature_map.route_to_feature(api_path)

    assert actual_slug == expected_slug, (
        f"Backend mapped {api_path} to '{actual_slug}', "
        f"but expected '{expected_slug}' (from frontend path {frontend_path})"
    )
