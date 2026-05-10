from functools import lru_cache
from pathlib import Path

CLOUD_PREFIX = Path("/project/workSpace")


@lru_cache(maxsize=1)
def is_cloud() -> bool:
    try:
        return Path(__file__).resolve().is_relative_to(CLOUD_PREFIX)
    except ValueError:
        return False


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def spa_dir() -> Path:
    return project_root() / "front-dev-home" / ".output" / "public"
