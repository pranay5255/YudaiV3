"""Export the FastAPI OpenAPI schema without starting a server."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


def export_schema() -> dict[str, Any]:
    os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/openapi-codegen.db")

    from yudai.run_controller import fastapi_app

    return fastapi_app.openapi()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Path to write openapi.json. Defaults to stdout.",
    )
    args = parser.parse_args()

    content = json.dumps(export_schema(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

