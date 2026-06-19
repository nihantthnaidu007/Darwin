"""Single source of data-root resolution for the darwin package.

The package modules live under src/darwin/ and the tests under tests/, both nested
below the checkout root. The data directories the engine reads and writes
(cases/, mcases/, runs/, reports/, seeds/) live at the checkout root, OUTSIDE the
package. Before the package conversion each module guessed that root with a fixed
Path(__file__).parent.parent literal; that depth is wrong once the modules are nested
in src/darwin/ (or tests/), so resolution moves here.

Resolution precedence (data_root):
  1. an explicit override set in-process by set_data_root (a CLI flag value);
  2. the DARWIN_DATA_ROOT environment variable;
  3. a walk UP from a starting file to the first ancestor that holds a marker
     (pyproject.toml or a cases/ directory), so it is correct regardless of how
     deeply the caller is nested, for both src/darwin/ and tests/.
If none resolves (the installed-without-override case) data_root raises a clear,
actionable error naming the flag and the environment variable the caller must supply.

The walk-up starts from this module's own __file__ by default, so every caller --
a src/darwin module or a tests module -- resolves the same checkout root. The
optional start argument lets a caller resolve from its own location instead; both
yield the same root because the marker is unique to the checkout.
"""

import os
from pathlib import Path

# Either marker identifies the checkout root: pyproject.toml is the build root and
# cases/ is the data root the engine reads. Either alone is sufficient.
_MARKERS = ("pyproject.toml", "cases")

ENV_VAR = "DARWIN_DATA_ROOT"

# In-process override (a CLI flag value), set before any data directory is read.
# Wins over the environment variable and the walk-up.
_override: Path | None = None


def set_data_root(root) -> None:
    """Pin the data root explicitly (e.g. from a CLI flag). Wins over DARWIN_DATA_ROOT
    and the walk-up. Pass None to clear the override."""
    global _override
    _override = Path(root).resolve() if root is not None else None


def _walk_up(start) -> Path | None:
    """Return the first ancestor of `start` (inclusive) that holds a marker, or None
    if the filesystem root is reached without finding one. A file `start` simply fails
    its own marker check and proceeds to its parent directory."""
    p = Path(start).resolve()
    for d in (p, *p.parents):
        if any((d / m).exists() for m in _MARKERS):
            return d
    return None


def data_root(start=None) -> Path:
    """Resolve the checkout data root by the documented precedence. Raises RuntimeError
    naming the override flag and DARWIN_DATA_ROOT when no root can be found."""
    if _override is not None:
        return _override
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env).resolve()
    base = Path(start) if start is not None else Path(__file__)
    found = _walk_up(base)
    if found is not None:
        return found
    raise RuntimeError(
        "darwin: cannot locate the data root (no pyproject.toml or cases/ found "
        f"walking up from {base.resolve()}). Pass an explicit data directory "
        "(--cases-dir / --mcases-dir / --out, as applicable) or set the "
        f"{ENV_VAR} environment variable to the checkout root."
    )


def cases_dir(start=None) -> Path:
    return data_root(start) / "cases"


def mcases_dir(start=None) -> Path:
    return data_root(start) / "mcases"


def runs_dir(start=None) -> Path:
    return data_root(start) / "runs"


def reports_dir(start=None) -> Path:
    return data_root(start) / "reports"


def seeds_dir(start=None) -> Path:
    return data_root(start) / "seeds"


def env_file(start=None) -> Path:
    """The repo-root .env path. Caller is responsible for catching the resolver error
    when running installed (no checkout), where there is no .env to load."""
    return data_root(start) / ".env"
