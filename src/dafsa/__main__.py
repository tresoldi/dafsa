"""Command-line entry point.

The 2.0 command-line interface is specified in ``DESIGN.md`` and is built at
milestone 10, once the structures it drives exist. Until then this reports the
package version so that the console script is at least well-formed.
"""

from __future__ import annotations

import argparse

from dafsa import __version__


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface.

    Parameters
    ----------
    argv
        Argument vector to parse. Defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        Process exit status.
    """
    parser = argparse.ArgumentParser(
        prog="dafsa",
        description="Finite-state structures for sequence data.",
    )
    parser.add_argument("--version", action="version", version=f"dafsa {__version__}")
    parser.parse_args(argv)

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
