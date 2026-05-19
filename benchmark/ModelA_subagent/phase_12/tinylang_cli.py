"""Thin entry-point shim for the tinylang CLI.

The phase-12 brief specifies that the binary be invokable via
``python tinylang_cli.py ...`` rather than a packaged console-script. All the
actual work lives in :mod:`tinylang.cli`; this file just forwards ``sys.argv``
and bridges the exit code.
"""

from __future__ import annotations

import sys

from tinylang.cli import main


if __name__ == "__main__":
    # ``sys.argv[0]`` is the script path; the CLI takes the *user* args, so
    # we slice it off here and let ``main`` apply its own defaults.
    sys.exit(main(sys.argv[1:]))
