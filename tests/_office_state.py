"""Which office adapters exist on THIS machine.

The "unconnected office adapter" tests were written when every
`providers/office.py` was a stub that raised
`NotImplementedError("... has not been connected")`. Adapters are real now,
and `office.py` is gitignored — so whether a given feature can serve office
data is a property of the developer's checkout, not of the code under test.

That makes the bare assertion environment-dependent: it passes on a machine
with no adapters and fails on one that has them, because the real adapter
dials the company Redis/OpenSearch and times out off-network. These helpers
let each test say which state it is asserting.
"""

from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "back_dev_home"

# The dispatcher's message when SKEWNONO_<FEATURE>_PROVIDER=office but no
# adapter is present. This is the documented contract (see CLAUDE.md):
# naming office with no adapter refuses to boot rather than falling back.
MISSING_ADAPTER_MESSAGE = "does not exist on this machine"


def has_office_adapter(feature_path: str) -> bool:
    """True when `back_dev_home/<feature_path>/providers/office.py` exists.

    `feature_path` is the slug-ish path under back_dev_home, e.g. "sem_list"
    or "ebeam/hitachi/storage".
    """
    return (_BACKEND / feature_path / "providers" / "office.py").is_file()


def skip_reason(feature_path: str) -> str:
    return (
        f"{feature_path} has a real providers/office.py on this machine, so the "
        "'unconnected adapter' state under test does not exist here — the "
        "adapter would dial the company network instead."
    )
