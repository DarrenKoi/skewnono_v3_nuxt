"""Office MSR-file adapter hookup point.

CANONICAL METADATA CONTRACT (the entry gate downstream analysis tasks wait on).

The Phase-1 mock cannot supply the site/coordinate identity that layout-dependent
analysis needs, so those fields are UNKNOWN there and the frontend treats them as
such. Before office mode may be selected, this adapter MUST connect a source that
additionally provides, per MSR:

  - ``site_layout_hash`` — a stable identity for the physical site layout, equal
    across MSRs that share one layout. This is the gate that lets multi-MSR
    delta, site variability and same-site gallery move off ``unavailable``.
  - ``recipe_revision`` — the recipe revision, so same-recipe/different-revision
    selections are distinguished rather than silently merged.
  - ``coordinate_transform_version`` — the version of the wafer coordinate
    transform, so coordinates are only compared within one transform.
  - ``sequence_timestamp`` — per-sequence acquisition time for ordering.

Until that source is wired in, both entry points raise ``NotImplementedError``
(rather than emitting fabricated metadata). The mock↔office swap must never
invent any of the fields above — see back_dev_home/msr_file/tests/test_contract.py.
"""


def _not_connected():
    raise NotImplementedError(
        "The msr_file office adapter has not been connected. "
        "Configure the approved MSR source before selecting office mode."
    )


def get_msr_file(*args, **kwargs):
    return _not_connected()


def get_msr_image(*args, **kwargs):
    return _not_connected()
