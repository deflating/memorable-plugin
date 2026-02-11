#!/usr/bin/env python3
"""Memorable server entrypoint.

Thin CLI wrapper around HTTP server wiring.
"""

import argparse

from server_http import run
from server_storage import DEFAULT_PORT


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Memorable server")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args()
    run(port=args.port)
