"""SWAP SURFACE for recipe_usage (VeritySEM / Provision).

Routes import only this module. What is swapped is three RAW loaders --
``load_list_rows`` / ``load_usage_rows`` / ``load_resident`` in
``providers/mock.py`` or ``providers/office.py`` -- returning the Redis keys'
own column shape. The aggregation into ``contracts.py`` happens here, once,
through ``providers/_shape.py``, so the gitignored ``office.py`` copy carries
no rule that could go stale.

The roster is ``sem_list``'s own dispatcher, never a provider of this feature:
at the office that pairing is declared in ``_OFFICE_DEPENDENCIES``.
"""

from datetime import date, datetime, timedelta, timezone

from backend._runtime.data_provider import get_data_provider
from backend.ebeam.recipe_usage.contracts import (
    AmatToolType,
    CatalogResponse,
    RecipeDetailResponse,
    StatusResponse,
)
from backend.ebeam.recipe_usage.providers._shape import (
    Roster,
    WindowError,
    build_catalog,
    build_recipe_detail,
    build_status,
    family_roster,
)
from backend.sem_list.data import get_sem_list


__all__ = ["WindowError", "get_catalog", "get_recipe_detail", "get_status"]

_KST = timezone(timedelta(hours=9), "KST")


def _provider():
    if get_data_provider("recipe_usage") == "office":
        from backend.ebeam.recipe_usage.providers import office
        return office
    from backend.ebeam.recipe_usage.providers import mock
    return mock


def _roster(tool_type: AmatToolType) -> Roster:
    return family_roster(get_sem_list(), tool_type)


def get_catalog(
    tool_type: AmatToolType, fab_names: tuple[str, ...]
) -> CatalogResponse:
    return build_catalog(
        tool_type,
        fab_names,
        _roster(tool_type),
        _provider().load_list_rows(tool_type),
        _provider().load_resident(tool_type),
    )


def get_recipe_detail(
    tool_type: AmatToolType, recipe_id: str, fab_names: tuple[str, ...]
) -> RecipeDetailResponse:
    return build_recipe_detail(
        tool_type,
        recipe_id,
        fab_names,
        _roster(tool_type),
        _provider().load_list_rows(tool_type),
        _provider().load_usage_rows(tool_type),
        _provider().load_resident(tool_type),
    )


def get_status(
    tool_type: AmatToolType,
    fab_names: tuple[str, ...],
    start: date | None,
    end: date | None,
) -> StatusResponse:
    """Raises `WindowError` for a reversed or over-long window."""
    return build_status(
        tool_type,
        fab_names,
        _roster(tool_type),
        _provider().load_usage_rows(tool_type),
        start,
        end,
        today=datetime.now(_KST).date(),
    )
