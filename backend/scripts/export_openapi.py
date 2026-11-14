"""Write the API's OpenAPI schema to a file.

Production does not serve /openapi.json (DEBUG=false), so each release's
schema is exported instead; CI keeps it as a build artifact. Run::

    backend/.venv/bin/python backend/scripts/export_openapi.py openapi.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    schema = app.openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{out}: {len(schema['paths'])} paths")


if __name__ == "__main__":
    main()
