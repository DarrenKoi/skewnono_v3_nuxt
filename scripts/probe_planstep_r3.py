"""Probe the office OpenSearch index ``sknn-planstep-r3`` end to end.

Purpose: verify the 3-hop data path the cdsem **device_statistics** office
adapter has to walk, before any of it is written. The adapter is still a stub,
and this index was an unknown source until 2026-07-30.

    r3_device_grp (Redis)          -> lot_cd
      + "_BASE"                    -> prod_id
    sknn-planstep-r3 (OpenSearch)  -> sort prod_id, oper_seq, samp_seq;
                                      skip_yn != "Y" -> oper_desc, recipe_id
    cdsem_idp_ver (OpenSearch)     -> full_name == recipe_id, highest version
                                      -> parameters -> para_* counts

Every hop is a place the chain can quietly break, so each gets its own stage:
a documented field that is absent, a `text` mapping that makes `term` match
nothing, a `_BASE` suffix convention that does not hold for every product, a
recipe_id with no IDP document, a `parameters` blob shaped differently than the
contract needs. A stage that fails prints what it found and keeps going — the
point is one report covering the whole path, not the first error.

Run FROM THE REPO ROOT at the office (config self-loads from
``back_dev_home/.env``; ``-m`` puts the root on ``sys.path``):

    .venv/bin/python -m scripts.probe_planstep_r3

    # widen / narrow the sampling
    .venv/bin/python -m scripts.probe_planstep_r3 --recipes 10 --devices 5

Whatever this proves belongs in TWO places (CLAUDE.md): the schema of record in
``docs/datatables/planstep_r3.txt`` (and ``idp_ver.txt`` for the parameters
blob) AND ``device_statistics/providers/`` mock docstrings. Mark each fact
``office 확인 YYYY-MM-DD``.

Read-only: only count / search / aggregate / mapping reads, plus Redis GET.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from back_dev_home._runtime.office_redis import (
    STORE_ERRORS,
    load_env_file,
    read_dataframe,
    redis_client,
)
from ops_store import OSIndex, OSSearch, create_client


INDEX = "sknn-planstep-r3"
IDP_INDEX = "cdsem_idp_ver"

# The Redis key holding the R3 device catalog this index's prod_id must join to.
RND_KEY = "r3_device_grp"

# Documented 2026-07-30. Presence and mapping type of each is what stage [1]
# checks — a field documented here but missing in the mapping is the finding.
DOCUMENTED_FIELDS = (
    "det_fac_id",
    "prod_id",
    "oper_id",
    "main_oper_id",
    "main_oper_yn",
    "oper_desc",
    "oper_seq",
    "samp_seq",
    "eqp_id",
    "recipe_id",
    "bak_eqp_yn",
    "bak_eqp_id_lval",
    "skip_yn",
    "eqp_grp_id",
    "reticle_id",
    "chg_tm",
)

# Low-cardinality fields worth a full value distribution: each encodes a
# convention the adapter branches on.
ENUM_FIELDS = ("det_fac_id", "main_oper_yn", "skip_yn", "bak_eqp_yn", "eqp_grp_id")

NUMERIC_FIELDS = ("oper_seq", "samp_seq")

# user-confirmed 2026-07-31: "Y" means SKIPPED, exactly as the field name reads.
# The field has THREE values — "Y", "N", and blank — so "is this step measured"
# is `!= "Y"`, never `== "N"`. (An earlier note claiming "Y" meant "currently
# measuring" was withdrawn; docs/datatables/planstep_r3.txt has the history.)
SKIPPED = "Y"

PROD_ID_SUFFIX = "_BASE"


def _rule(title: str = "") -> None:
    print(f"\n{'─' * 78}")
    if title:
        print(title)
        print("─" * 78)


def _properties(client: Any, index: str) -> dict[str, Any]:
    """The mapping's property dict, whichever wrapper shape comes back."""
    mapping = OSIndex(client=client, index=index).get_mapping()
    for body in mapping.values():
        props = body.get("mappings", {}).get("properties")
        if props:
            return props
    return {}


def _agg_field(props: dict[str, Any], name: str) -> str:
    """The field name usable for term/terms — `.keyword` only when needed.

    The repo's standing trap (docs/datatables/README.md 표기 규칙): an analyzed
    `text` field matches nothing under `term` and cannot be aggregated, so it
    needs its `.keyword` subfield; a bare `keyword` field must NOT get the
    suffix or it matches nothing either. Deciding per field from the real
    mapping is the only way to be right in both cases.
    """
    spec = props.get(name, {})
    if spec.get("type") == "text" and "keyword" in spec.get("fields", {}):
        return f"{name}.keyword"
    return name


def stage_mapping(client: Any, props: dict[str, Any]) -> None:
    _rule(f"[1] {INDEX} — exists, size, mapping")

    exists = OSIndex(client=client, index=INDEX).exists()
    print(f"  exists (index or alias): {exists}")
    if not exists:
        print("  -> nothing else can run. Check the index name and your access.")
        return

    total = OSSearch(client=client, index=INDEX).count().get("count")
    print(f"  total docs: {total:,}" if isinstance(total, int) else f"  total docs: {total}")

    print(f"\n  {'field':<20} {'mapping type':<14} {'term/agg field'}")
    print(f"  {'-' * 20} {'-' * 14} {'-' * 30}")
    missing = []
    for name in DOCUMENTED_FIELDS:
        spec = props.get(name)
        if spec is None:
            missing.append(name)
            print(f"  {name:<20} {'ABSENT':<14} —")
            continue
        print(f"  {name:<20} {str(spec.get('type')):<14} {_agg_field(props, name)}")

    undocumented = sorted(set(props) - set(DOCUMENTED_FIELDS))
    if undocumented:
        print(f"\n  fields in the index but NOT documented: {', '.join(undocumented)}")
    if missing:
        print(
            f"\n  DOCUMENTED BUT ABSENT: {', '.join(missing)}\n"
            "  -> fix docs/datatables/planstep_r3.txt before writing the adapter."
        )


def stage_values(search: OSSearch, props: dict[str, Any]) -> None:
    _rule("[2] value conventions")

    for name in ENUM_FIELDS:
        if name not in props:
            print(f"\n  {name}: ABSENT — skipped")
            continue
        field = _agg_field(props, name)
        result = search.aggregate({"v": {"terms": {"field": field, "size": 25}}})
        buckets = result.get("aggregations", {}).get("v", {}).get("buckets", [])
        print(f"\n  {name} (via {field}): {len(buckets)} distinct")
        for bucket in buckets:
            print(f"      {str(bucket['key']):<24} {bucket['doc_count']:>10,}")
        if name == "skip_yn":
            skipped = next(
                (b["doc_count"] for b in buckets if str(b["key"]) == SKIPPED), 0
            )
            bucketed = sum(b["doc_count"] for b in buckets)
            print(
                f"      -> skip_yn == {SKIPPED!r} (skipped): {skipped:,}   "
                f"!= {SKIPPED!r} (measured): {bucketed - skipped:,}"
            )
            # The whole reason the adapter tests `!= "Y"` rather than `== "N"`:
            # a third, blank value exists. Docs missing the field entirely never
            # appear in a terms agg, so the gap against the index total is the
            # only way to count them — and it is exactly the population a
            # `== "N"` filter would silently drop.
            total = OSSearch(client=search.client, index=INDEX).count().get("count")
            if isinstance(total, int) and total > bucketed:
                print(
                    f"      -> BLANK/missing skip_yn: {total - bucketed:,} of "
                    f"{total:,} docs carry no 'Y'/'N' value.\n"
                    "         A `== \"N\"` filter would drop every one of them."
                )

    for name in NUMERIC_FIELDS:
        if name not in props:
            print(f"\n  {name}: ABSENT — skipped")
            continue
        stats = search.aggregate({"s": {"stats": {"field": name}}})
        s = stats.get("aggregations", {}).get("s", {})
        print(
            f"\n  {name}: min={s.get('min')} max={s.get('max')} "
            f"avg={s.get('avg')} count={s.get('count')}"
        )

    # chg_tm as stored. The repo convention is offset-less KST wall-clock; a
    # trailing Z or +09:00 shifts every rendered time by 9 hours.
    sample = search.search_raw({"size": 3, "_source": ["chg_tm", "oper_desc", "recipe_id"]})
    hits = sample.get("hits", {}).get("hits", [])
    print("\n  chg_tm raw values (offset must be ABSENT):")
    for hit in hits:
        src = hit.get("_source", {})
        print(f"      {src.get('chg_tm')!r}")
    suspect = [
        src.get("chg_tm")
        for src in (h.get("_source", {}) for h in hits)
        if isinstance(src.get("chg_tm"), str)
        and (src["chg_tm"].endswith("Z") or "+" in src["chg_tm"])
    ]
    if suspect:
        print(
            "      MISMATCH: an offset/Z is present. Times will be 9 hours off "
            "unless the adapter handles it — record this in the datatable doc."
        )
    elif hits:
        print("      -> no offset, matches the KST wall-clock convention.")

    print("\n  sample oper_desc / recipe_id:")
    for hit in hits:
        src = hit.get("_source", {})
        print(f"      {str(src.get('oper_desc'))[:46]:<46} {src.get('recipe_id')}")


def stage_prod_id_bridge(search: OSSearch, props: dict[str, Any], limit: int) -> list[str]:
    """Does stripping "_BASE" off prod_id land in r3_device_grp's lot_cd?"""
    _rule("[3] prod_id <-> lot_cd bridge")

    if "prod_id" not in props:
        print("  prod_id ABSENT — bridge cannot be checked.")
        return []

    field = _agg_field(props, "prod_id")
    result = search.aggregate({"p": {"terms": {"field": field, "size": 10000}}})
    buckets = result.get("aggregations", {}).get("p", {}).get("buckets", [])
    prod_ids = [str(b["key"]) for b in buckets]
    print(f"  distinct prod_id: {len(prod_ids):,} (via {field})")
    for bucket in buckets[:8]:
        print(f"      {str(bucket['key']):<28} {bucket['doc_count']:>8,} step(s)")

    with_suffix = [p for p in prod_ids if p.endswith(PROD_ID_SUFFIX)]
    print(
        f"\n  ending with {PROD_ID_SUFFIX!r}: {len(with_suffix):,} / {len(prod_ids):,}"
    )
    others = [p for p in prod_ids if not p.endswith(PROD_ID_SUFFIX)]
    if others:
        print(f"  OTHER suffixes present ({len(others):,}) — e.g. {', '.join(others[:8])}")
        print("      -> stripping only '_BASE' would silently drop these products.")

    derived = {p[: -len(PROD_ID_SUFFIX)] if p.endswith(PROD_ID_SUFFIX) else p for p in prod_ids}

    # The other half of the bridge lives in Redis, so this is the one stage that
    # touches both stores. Failing to reach Redis must not kill the OpenSearch
    # report, hence the local try.
    try:
        client = redis_client()
        raw = client.get(RND_KEY.encode())
        if raw is None:
            print(f"\n  Redis {RND_KEY!r}: MISSING — cannot compare lot_cd vocabulary.")
            return prod_ids[:limit]
        df = read_dataframe(raw, RND_KEY)
    except (RuntimeError, LookupError, *STORE_ERRORS) as err:
        print(f"\n  Redis {RND_KEY!r} unreadable ({type(err).__name__}: {err})")
        return prod_ids[:limit]

    if "lot_cd" not in df.columns:
        print(f"\n  Redis {RND_KEY!r} has no lot_cd column (has {sorted(map(str, df.columns))})")
        return prod_ids[:limit]

    lots = set(df["lot_cd"].dropna().astype(str))
    matched = derived & lots
    print(f"\n  {RND_KEY} lot_cd: {len(lots):,} distinct")
    print(f"  prod_id minus suffix that match a lot_cd: {len(matched):,} / {len(derived):,}")
    if matched:
        print(f"      e.g. {', '.join(sorted(matched)[:8])}")
    unmatched = sorted(derived - lots)
    if unmatched:
        print(f"  NOT in {RND_KEY} ({len(unmatched):,}): {', '.join(unmatched[:8])}")
        print(
            "      -> either the catalog is narrower than the plan index, or the\n"
            "         suffix rule needs refining. Decide which before joining."
        )
    else:
        print("      -> every derived device code exists in the catalog. Bridge holds.")

    return prod_ids[:limit]


def stage_steps_per_device(search: OSSearch, props: dict[str, Any], prod_ids: list[str]) -> list[str]:
    """Payload sizing, and the measured-step subset the adapter actually uses."""
    _rule("[4] steps per device, and the skip_yn == 'Y' subset")

    if not prod_ids:
        print("  no prod_id values sampled — skipped.")
        return []

    field = _agg_field(props, "prod_id")
    skip_field = _agg_field(props, "skip_yn") if "skip_yn" in props else None
    measured_recipes: list[str] = []

    for prod_id in prod_ids:
        query = {"term": {field: prod_id}}
        total = search.count(query=query).get("count", 0)

        measured = "?"
        if skip_field:
            # `must_not term "Y"` rather than `term "N"` — the adapter's rule.
            # A positive match on "N" would exclude the blank-valued steps,
            # which is the bug this probe exists to make visible.
            measured_query = {
                "bool": {
                    "filter": [{"term": {field: prod_id}}],
                    "must_not": [{"term": {skip_field: SKIPPED}}],
                }
            }
            measured = search.count(query=measured_query).get("count", 0)

            # Sorted the way the adapter must sort, so the printed order is the
            # real process order rather than relevance order.
            body = {
                "size": 5,
                "query": measured_query,
                "sort": [{field: "asc"}, {"oper_seq": "asc"}, {"samp_seq": "asc"}],
                "_source": ["oper_seq", "samp_seq", "oper_desc", "recipe_id", "eqp_id"],
            }
            hits = search.search_raw(body).get("hits", {}).get("hits", [])
            print(f"\n  {prod_id}: {total:,} step(s), {measured:,} measuring")
            for hit in hits:
                src = hit.get("_source", {})
                print(
                    f"      seq {str(src.get('oper_seq')):>4}/{str(src.get('samp_seq')):<3} "
                    f"{str(src.get('oper_desc'))[:34]:<34} {src.get('recipe_id')}"
                )
                recipe = src.get("recipe_id")
                if isinstance(recipe, str) and recipe:
                    measured_recipes.append(recipe)
            missing_recipe = sum(
                1 for h in hits if not h.get("_source", {}).get("recipe_id")
            )
            if missing_recipe:
                print(
                    f"      NOTE: {missing_recipe} measuring step(s) have no recipe_id "
                    "— the idp_ver join has nothing to key on for those."
                )
        else:
            print(f"\n  {prod_id}: {total:,} step(s) (skip_yn absent, no subset)")

    return measured_recipes


def stage_idp_join(client: Any, recipes: list[str], limit: int) -> None:
    """Do measured recipe_ids resolve to cdsem_idp_ver.full_name, with parameters?"""
    _rule(f"[5] recipe_id -> {IDP_INDEX}.full_name join (parameter counts)")

    if not recipes:
        print("  no measured recipe_id sampled — skipped.")
        return

    if not OSIndex(client=client, index=IDP_INDEX).exists():
        print(f"  {IDP_INDEX} does not exist or is not visible — skipped.")
        return

    props = _properties(client, IDP_INDEX)
    name_field = _agg_field(props, "full_name")
    search = OSSearch(client=client, index=IDP_INDEX)
    print(f"  matching on {name_field} (mapping: {props.get('full_name', {}).get('type')})")
    print(f"  parameters mapping: {props.get('parameters', {}) or 'ABSENT'}")

    resolved = 0
    for recipe in dict.fromkeys(recipes[:limit]):
        # Exactly the shape the adapter must use: newest version only, and only
        # the parameters source. Pulling full version history per recipe is what
        # idp_ver.txt warns blows up the payload.
        body = {
            "size": 1,
            "query": {"term": {name_field: recipe}},
            "sort": [{"version": "desc"}],
            "_source": ["full_name", "version", "modified", "parameters"],
        }
        hits = search.search_raw(body).get("hits", {}).get("hits", [])
        if not hits:
            print(f"\n  {recipe}: NO idp_ver document -> para_* cannot be derived")
            continue

        resolved += 1
        src = hits[0].get("_source", {})
        params = src.get("parameters")
        print(f"\n  {recipe}: version={src.get('version')} modified={src.get('modified')}")
        print(f"      parameters type: {type(params).__name__}")
        if isinstance(params, list):
            print(f"      length: {len(params)}")
            if params:
                first = params[0]
                print(f"      first element: {str(first)[:160]}")
                if isinstance(first, dict):
                    print(f"      element keys: {sorted(first)}")
        elif isinstance(params, dict):
            # Confirmed shape (user-confirmed 2026-07-30): {parameter_name:
            # point_count}, e.g. {"WAFER": 13, "EDGE": 16}. Both contract shapes
            # derive from this one dict, so bucketize it exactly the way the
            # adapter must and surface whatever falls outside {16,13,9,5}.
            keys = sorted(params)
            print(f"      {len(keys)} key(s): {', '.join(map(str, keys[:14]))}")
            counts: dict[Any, int] = {}
            for value in params.values():
                counts[value] = counts.get(value, 0) + 1
            print(f"      point_count -> #params: {sorted(counts.items(), key=str)}")
            buckets = {n: counts.get(n, 0) for n in (16, 13, 9, 5)}
            leftover = sum(c for v, c in counts.items() if v not in (16, 13, 9, 5))
            print(
                f"      para_16={buckets[16]} para_13={buckets[13]} "
                f"para_9={buckets[9]} para_5={buckets[5]} "
                f"(sum={sum(buckets.values())}, outside those buckets={leftover})"
            )
            if leftover:
                print(
                    "      NOTE: point counts outside {16,13,9,5} exist, so para_all\n"
                    "            cannot be both 'total params' and 'sum of buckets'.\n"
                    "            Decide which, and record it in idp_ver.txt."
                )
            if keys and all("_" not in str(k) for k in keys):
                print(
                    "      NOTE: every key is a bare word with no suffix, so there is\n"
                    "            no per-parameter identity — the outlier and\n"
                    "            bloated-recipe views lose their input (idp_ver.txt)."
                )
        else:
            print(f"      value: {str(params)[:160]}")

    print(f"\n  resolved {resolved}/{len(list(dict.fromkeys(recipes[:limit])))} sampled recipe(s)")
    if resolved:
        print(
            "  -> next: decide how parameters maps to RecipeParamsRow.parameters\n"
            "     ({name, point_count}) and to RecipeInfoRow's para_16/13/9/5.\n"
            "     Record the blob's real structure in docs/datatables/idp_ver.txt."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.probe_planstep_r3",
        description=(
            "Probe sknn-planstep-r3 and the device_statistics 3-hop chain "
            "(r3_device_grp -> planstep -> cdsem_idp_ver)."
        ),
    )
    parser.add_argument(
        "--devices", type=int, default=3, help="prod_id values to drill into (default: 3)."
    )
    parser.add_argument(
        "--recipes", type=int, default=5, help="recipe_ids to join to idp_ver (default: 5)."
    )
    args = parser.parse_args(argv)

    load_env_file("OPENSEARCH_HOST")
    try:
        client = create_client()
    except Exception as err:  # 설정/연결 실패는 여기서 끝내는 편이 명확합니다
        print(f"OpenSearch is not configured or unreachable: {err}", file=sys.stderr)
        return 2

    props = _properties(client, INDEX)
    search = OSSearch(client=client, index=INDEX)

    stage_mapping(client, props)
    if not props:
        print("\nNo mapping properties resolved — stopping.")
        return 2

    stage_values(search, props)
    prod_ids = stage_prod_id_bridge(search, props, args.devices)
    recipes = stage_steps_per_device(search, props, prod_ids)
    stage_idp_join(client, recipes, args.recipes)

    _rule("NEXT")
    print(
        "  Record what this proved in BOTH places (CLAUDE.md):\n"
        "    1. docs/datatables/planstep_r3.txt and idp_ver.txt\n"
        "    2. device_statistics/providers/ mock docstrings\n"
        "  Mark each fact 'office 확인 YYYY-MM-DD', then implement\n"
        "  device_statistics/providers/office.py per its MIGRATION.md.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
