import requests
from gui.version import __version__

API_URL = "https://api.github.com/repos/ruflas/CrunchyExporter/releases/latest"


def _parse(v: str) -> tuple:
    parts = v.strip().lstrip("vV").split(".")
    nums = []
    for p in parts[:3]:
        digits = "".join(c for c in p if c.isdigit())
        nums.append(int(digits) if digits else 0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def check_for_update(timeout: int = 5) -> str | None:
    """
    Returns the latest release tag (e.g. "v1.4.0") if it's newer than the
    currently running version, otherwise None. This is a best-effort,
    non-blocking check — any network/parsing error is swallowed so a flaky
    connection or GitHub being unreachable never affects startup.
    """
    try:
        resp = requests.get(
            API_URL, timeout=timeout,
            headers={"Accept": "application/vnd.github+json"},
        )
        if not resp.ok:
            return None
        tag = resp.json().get("tag_name", "")
        if tag and _parse(tag) > _parse(__version__):
            return tag
    except Exception:
        pass
    return None
