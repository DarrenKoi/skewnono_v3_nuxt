# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office adapter for lateral_recipe — NOT CONNECTED YET.

Implement get_lateral_recipe listed in lateral_recipe/MIGRATION.md against
the office data sources (Redis-backed tools-in-recipe mapping + OpenSearch
recipe-version lookup). Normalize results to lateral_recipe/contracts.py
shapes.
"""


def _not_connected():
    raise NotImplementedError(
        "The lateral_recipe office adapter has not been connected yet. "
        "Set SKEWNONO_LATERAL_RECIPE_PROVIDER=mock until it is ready."
    )


def get_lateral_recipe(tool_type, fab_name, recipe_name):
    return _not_connected()