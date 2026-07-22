# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 lateral-recipe adapter backed by the office IDP version index.

"Lateral check" answers: for one recipe, which tools in the fab hold it, at
which IDP version, generated when.

Source: OpenSearch aliases ``cdsem_idp_ver`` / ``hvsem_idp_ver``. One document
per **(recipe, version)** — searching a ``full_name`` returns the recipe's
whole version history, and the highest ``version`` is the current one. Fields
used here:

* ``full_name``         — the recipe name the user searched (exact match goes
                          through ``full_name.keyword``; the ``text`` mapping
                          is analyzed and would match on shared tokens).
* ``fab_name``          — fab filter, stored uppercase.
* ``version`` (long)    — IDP version; higher is newer.
* ``modified`` (date)   — when that version was generated.
* ``eqp_id`` []         — tools holding this version (보유). This is the only
                          readiness signal read; the index's companion
                          ``not_found_eqp_id`` (미보유) is not fetched, since
                          "absent from eqp_id" already means not ready.

The equipment roster (eqp_id / model / vendor / available) does NOT come from
this index — it comes from ``sem_list.data.get_sem_list()``, the same source
behind the tool-inventory view. This index only decides ready/version/when per
tool. That split is deliberate: if lateral supplied its own roster, the same
fab could show a different tool count here than in the inventory view with no
way to tell which was right.

Timestamps: the office indices store KST wall-clock with no offset. The
frontend formats with ``new Date(iso).getHours()`` (local time), so
``recipe_generated_at`` is emitted with an explicit ``+09:00``. Emitting it
as ``Z`` instead would tag a 12:00 KST wall-clock as 12:00 UTC, which a KST
browser then renders as 21:00 — 9 hours LATE.

OFFICE-VERIFY: this assumes ``modified`` arrives offset-less, which is the
convention for the meas_hist indices. ``fetch_hits`` returns ``_source``
verbatim, so a naive stored value stays naive and is tagged correctly. If
ingestion instead writes a ``Z``-suffixed KST wall-clock (the "KST-as-UTC"
spelling used elsewhere), ``_kst_iso`` would convert it and land 9 hours off.
Check one real ``modified`` value on the first office run.

At the office: fill in OPENSEARCH_* in ``back_dev_home/.env``,
``cp office_example.py office.py``, set
``SKEWNONO_LATERAL_RECIPE_PROVIDER=office``, then run the Verify command in
MIGRATION.md.
"""

from datetime import datetime
from typing import Any

from back_dev_home.ebeam.hitachi._office_search import (
    KST,
    fetch_hits,
    query as _query,
    text as _text,
)
from back_dev_home.ebeam.hitachi._tool_specs import ToolType, model_to_tool_type
from back_dev_home.ebeam.hitachi.lateral_recipe.contracts import (
    LateralRecipeResponse,
    LateralRecipeRow,
    LateralRecipeVersion,
)
from back_dev_home.sem_list.data import get_sem_list


__all__ = ["get_lateral_recipe"]


# tool_type -> OpenSearch alias for the IDP version index.
INDEX: dict[ToolType, str] = {
    "cd-sem": "cdsem_idp_ver",
    "hv-sem": "hvsem_idp_ver",
}

# Exact-match fields go through their .keyword sub-fields: the base mappings
# are `text` (analyzed), so a term query on them matches nothing and a match
# query on them matches too much.
FULL_NAME_KW = "full_name.keyword"
FAB_NAME_KW = "fab_name.keyword"

# One document per version. A recipe with more versions than this is not
# something the index is expected to hold; the cap exists so a mapping
# surprise cannot pull an unbounded result set. Truncation is detected below.
MAX_VERSION_DOCS = 200

# Trim the fetched fields: `parameters` and `raw_data` are object blobs this
# endpoint never reads, and 200 docs' worth of them would dwarf the response.
# `not_found_eqp_id` (미보유) is deliberately NOT fetched — a tool is reported
# ready purely by its presence in `eqp_id`, so the negative list would be dead
# weight. It becomes necessary only if `recipe_ready` ever grows a third state
# distinguishing "confirmed missing" from "never evaluated".
SOURCE_FIELDS = ["version", "modified", "eqp_id"]


def _as_list(value: Any) -> list[str]:
    """A multi-valued OpenSearch text field as a list of non-empty strings.

    A field indexed with one value comes back as a bare string, not a
    one-element list, so both shapes have to be accepted.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = [value]
    return [cleaned for cleaned in (_text(item) for item in items) if cleaned]


def _kst_iso(value: Any) -> str | None:
    """A ``modified`` value as an ISO string with an explicit +09:00 offset.

    Naive input is KST wall-clock (the office storage convention), so it is
    tagged rather than converted. Input that already carries an offset is
    converted into KST so the emitted wall-clock is always Korean local time.
    """
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=KST).isoformat()
    return parsed.astimezone(KST).isoformat()


def _version_docs(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_name: str,
) -> list[dict[str, Any]]:
    index = INDEX.get(tool_type)
    if index is None:
        raise ValueError(
            f"Unknown tool_type {tool_type!r}; expected one of {sorted(INDEX)}"
        )

    clauses: list[dict[str, Any]] = [{"term": {FULL_NAME_KW: recipe_name}}]
    if fab_name:
        clauses.append({"term": {FAB_NAME_KW: fab_name.strip().upper()}})

    docs = fetch_hits(
        index,
        _query(clauses),
        size=MAX_VERSION_DOCS,
        sort=[{"version": "desc"}],
        source=SOURCE_FIELDS,
    )
    if len(docs) == MAX_VERSION_DOCS:
        raise LookupError(
            f"Recipe {recipe_name!r} returned {MAX_VERSION_DOCS} version "
            f"documents from {index!r} — the per-recipe cap. Showing a "
            "truncated version history would misreport which tools are "
            "current; raise MAX_VERSION_DOCS or check for duplicate ingestion."
        )
    return docs


def _roster(tool_type: ToolType, fab_name: str | None):
    """Tools of this type in this fab, from sem_list, sorted by eqp_id.

    Mirrors the mock's filter so office and home list the same population.
    """
    wanted = (fab_name or "").strip().upper() or None
    rows = [
        row
        for row in get_sem_list()
        if model_to_tool_type(row["eqp_model_cd"]) == tool_type
        and (wanted is None or row["fab_name"].strip().upper() == wanted)
    ]
    rows.sort(key=lambda r: r["eqp_id"])
    return rows


def get_lateral_recipe(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_name: str,
) -> LateralRecipeResponse:
    docs = _version_docs(tool_type, fab_name, recipe_name)

    # eqp_id -> highest version holding it. A tool that appears under several
    # versions is reported at its newest, which is the one it currently runs.
    version_by_eqp: dict[str, int] = {}
    generated_at_by_version: dict[int, str | None] = {}
    for doc in docs:
        try:
            version = int(doc["version"])
        except (KeyError, TypeError, ValueError):
            continue  # a doc without a usable version cannot place a tool
        generated_at_by_version.setdefault(version, _kst_iso(doc.get("modified")))
        for eqp_id in _as_list(doc.get("eqp_id")):
            # Explicit None check, not a 0 sentinel: version is a `long` and a
            # legitimate version 0 would lose to `0 > 0` and silently report the
            # tool as not holding the recipe. Order-independent, so this does
            # not quietly depend on the caller's `sort` staying descending.
            current = version_by_eqp.get(eqp_id)
            if current is None or version > current:
                version_by_eqp[eqp_id] = version

    rows: list[LateralRecipeRow] = []
    ready_by_version: dict[int, int] = {}
    ready_count = 0
    for sem in _roster(tool_type, fab_name):
        version = version_by_eqp.get(sem["eqp_id"])
        # Not listed under any version means not ready. A tool absent from
        # both eqp_id and not_found_eqp_id ("never evaluated") lands here too
        # — recipe_ready is a bool, so there is nowhere else for it to go.
        if version is not None:
            ready_count += 1
            ready_by_version[version] = ready_by_version.get(version, 0) + 1
        rows.append(LateralRecipeRow(
            eqp_id=sem["eqp_id"],
            eqp_model_cd=sem["eqp_model_cd"],
            vendor_nm=sem["vendor_nm"],
            available=sem["available"],
            recipe_ready=version is not None,
            recipe_version=version,
            recipe_generated_at=(
                generated_at_by_version.get(version) if version is not None else None
            ),
        ))

    # Every version the recipe has ever had, newest first — including ones no
    # tool currently holds, so the version history stays browsable. ready_count
    # is counted from the rows above rather than the documents' no_of_eqp_id,
    # so the number on a card always equals what is countable in the table.
    versions = [
        LateralRecipeVersion(
            recipe_version=version,
            generated_at=generated_at_by_version[version] or "",
            ready_count=ready_by_version.get(version, 0),
        )
        for version in sorted(generated_at_by_version, reverse=True)
    ]
    latest = versions[0] if versions else None

    total = len(rows)
    return LateralRecipeResponse(
        tool_type=tool_type,
        fab_name=fab_name,
        recipe_name=recipe_name,
        total_tools_in_fab=total,
        ready_count=ready_count,
        not_ready_count=total - ready_count,
        latest_recipe_version=latest["recipe_version"] if latest else None,
        latest_generated_at=latest["generated_at"] if latest else None,
        versions=versions,
        rows=rows,
    )


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #   .venv/bin/python -m back_dev_home.ebeam.hitachi.lateral_recipe.providers.office
    import sys

    recipe = sys.argv[1] if len(sys.argv) > 1 else "1/AC_M2_TAT"
    result = get_lateral_recipe("cd-sem", "R3", recipe)
    print(f"{recipe}: {result['ready_count']}/{result['total_tools_in_fab']} tools ready")
    print("versions:", [(v["recipe_version"], v["ready_count"]) for v in result["versions"]])
