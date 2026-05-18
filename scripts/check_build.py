#!/usr/bin/env python3
"""Pre-push hook: build sdist + wheel, then ``twine check`` the artifacts.

Catches packaging issues before they reach a tag push. The specific failure
that bit v0.1.0 — ``src/gitea_mcp/_version.py`` was committed to git, making
``setuptools_scm`` produce ``0.1.1.dev0`` instead of ``0.1.0`` on the build —
would have surfaced here as ``twine check`` flagging an unexpected version on
a release commit, instead of being discovered after the wheel reached PyPI.

Run directly with ``python scripts/check_build.py`` if you want to verify a
release locally without going through ``git push``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    dist = Path("dist")
    if dist.exists():
        shutil.rmtree(dist)

    build_rc = subprocess.call([sys.executable, "-m", "build", "--quiet"])
    if build_rc != 0:
        return build_rc

    artifacts = sorted(dist.glob("*"))
    if not artifacts:
        print("No build artifacts produced.", file=sys.stderr)
        return 1

    return subprocess.call(["twine", "check", *(str(p) for p in artifacts)])


if __name__ == "__main__":
    sys.exit(main())
