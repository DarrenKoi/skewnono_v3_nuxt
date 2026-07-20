# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office adapter for recipe_search — NOT CONNECTED YET.

Implement every function listed in recipe_search/MIGRATION.md against the
office data sources (Redis-backed recipe-name list, IDP recipe-open payload).
Normalize results to recipe_search/contracts.py shapes.
"""


def _not_connected():
    raise NotImplementedError(
        "The recipe_search office adapter has not been connected yet. "
        "Set SKEWNONO_RECIPE_SEARCH_PROVIDER=mock until it is ready."
    )


def get_recipe_catalog(tool_type, fab_name=None):
    return _not_connected()


def get_recipe_open_data(recipe_id=None, fac_id=None, tool_category=None):
    return _not_connected()


def get_recipe_compare_data(tool_type, fab_name, recipe_names):
    return _not_connected()