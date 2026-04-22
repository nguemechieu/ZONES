from __future__ import annotations

import argparse
import os

from src.server import Server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ZONES browser dashboard.")
    parser.add_argument("--host", default=os.getenv("ZONES_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("ZONES_PORT", "8787")))
    args = parser.parse_args()

    Server().serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
