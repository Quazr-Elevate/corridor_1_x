"""List every Cor1x API route with its effective path, the auth it requires and
its route-level rate limit.

Reads the source with ``ast``: nothing is imported, so it runs without the
backend's virtualenv or settings. Exits 1 if an /admin route other than
login/logout has no permission dependency.

Limits enforced inside a service (the contact-reveal window in
catalog/service.py) are not visible here; the output says so.

Usage, from the repository root:
    python .claude/skills/cor1x-backend/scripts/route_inventory.py
    python .claude/skills/cor1x-backend/scripts/route_inventory.py --public
    python .claude/skills/cor1x-backend/scripts/route_inventory.py --root path/to/repo --markdown
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

METHODS = {"get", "post", "put", "patch", "delete"}
ADMIN_OPEN_BY_DESIGN = {"/admin/login", "/admin/logout"}


@dataclass
class Route:
    method: str
    path: str
    auth: str
    limit: str
    source: str


def _router_prefixes(tree: ast.Module) -> dict[str, str]:
    """``name = APIRouter(prefix="/x")`` → {name: "/x"} (no prefix → "")."""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name) and func.id == "APIRouter":
                prefix = next((k.value.value for k in node.value.keywords
                               if k.arg == "prefix" and isinstance(k.value, ast.Constant)), "")
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        out[target.id] = prefix
    return out


def _mounts(router_file: Path) -> dict[tuple[str, str], str]:
    """In a package's router.py: ``router.include_router(mod.var)`` mounts mod.var under router's prefix."""
    tree = ast.parse(router_file.read_text(encoding="utf-8"))
    prefixes = _router_prefixes(tree)
    out: dict[tuple[str, str], str] = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "include_router" and isinstance(node.func.value, ast.Name)
                and node.args and isinstance(node.args[0], ast.Attribute)
                and isinstance(node.args[0].value, ast.Name)):
            parent = prefixes.get(node.func.value.id, "")
            out[(node.args[0].value.id, node.args[0].attr)] = parent
    return out


def _permission_aliases(deps_file: Path) -> dict[str, str]:
    """``CanX = Annotated[AdminPrincipal, Depends(require(Perm.y))]`` → {"CanX": "y"}."""
    if not deps_file.exists():
        return {}
    src = deps_file.read_text(encoding="utf-8")
    return dict(re.findall(r"^(Can\w+)\s*=\s*Annotated\[.*?require\(Perm\.(\w+)\)", src, re.M))


def _version_prefix(main_file: Path) -> str:
    """A prefix applied to every router in create_app(), if one exists (e.g. /v1)."""
    if not main_file.exists():
        return ""
    m = re.search(r"include_router\([^)]*prefix\s*=\s*[\"'](/[^\"']*)[\"']", main_file.read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def _auth(fn: ast.AsyncFunctionDef | ast.FunctionDef, perms: dict[str, str]) -> str:
    args = fn.args.args + fn.args.kwonlyargs
    text = " ".join(ast.unparse(a.annotation) for a in args if a.annotation is not None)
    if alias := re.search(r"\b(Can\w+)\b", text):
        return "admin:" + perms.get(alias.group(1), alias.group(1))
    if "require(Perm." in text:
        return "admin:" + re.search(r"require\(Perm\.(\w+)\)", text).group(1)
    if "SignedInAdmin" in text:
        return "admin:any"
    if re.search(r"\b(CurrentUser|CurrentSessionId)\b", text):
        return "trader"
    if "LookupPrincipal" in text:
        return "trader or admin"
    if "OptionalUser" in text:
        return "optional"
    return "PUBLIC"


def _limit(fn: ast.AsyncFunctionDef | ast.FunctionDef, decorator: ast.Call) -> str:
    rules: list[str] = []
    for kw in decorator.keywords:
        if kw.arg == "dependencies":
            rules += [f"ip:{r}" for r in re.findall(r"ip_rate_limit\((\w+)\)", ast.unparse(kw.value))]
    body = "\n".join(ast.unparse(stmt) for stmt in fn.body)
    rules += re.findall(r"get_limiter\(\)\.check\((\w+)", body)
    return ", ".join(dict.fromkeys(rules)) or "-"


def collect(root: Path) -> list[Route]:
    app_dir = root / "backend" / "app"
    modules = app_dir / "modules"
    if not modules.is_dir():
        sys.exit(f"No backend/app/modules under {root}. Pass --root <repository root>.")
    perms = _permission_aliases(modules / "admin" / "deps.py")
    version = _version_prefix(app_dir / "main.py")

    mounts: dict[Path, dict[tuple[str, str], str]] = {}
    for router_file in modules.glob("*/router.py"):
        mounts[router_file.parent] = _mounts(router_file)

    routes: list[Route] = []
    for py in sorted(modules.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        prefixes = _router_prefixes(tree)
        package_mounts = mounts.get(py.parent, {})
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for dec in fn.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr in METHODS and isinstance(dec.func.value, ast.Name)
                        and dec.args and isinstance(dec.args[0], ast.Constant)):
                    continue
                var = dec.func.value.id
                parent = package_mounts.get((py.stem, var), "") if py.name != "router.py" else ""
                # create_app() mounts the health router outside the version prefix.
                mount = "" if py.parent.name == "health" else version
                path = mount + parent + prefixes.get(var, "") + dec.args[0].value
                routes.append(Route(dec.func.attr.upper(), path or "/", _auth(fn, perms),
                                    _limit(fn, dec), f"{py.parent.name}/{py.name}:{fn.lineno}"))
    return sorted(routes, key=lambda r: (r.path, r.method))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path.cwd(), help="repository root (default: current directory)")
    ap.add_argument("--public", action="store_true", help="only routes with no auth dependency")
    ap.add_argument("--markdown", action="store_true", help="print a Markdown table (for design reviews and releases)")
    opts = ap.parse_args()

    routes = collect(opts.root.resolve())
    shown = [r for r in routes if r.auth == "PUBLIC"] if opts.public else routes

    if opts.markdown:
        print("| Method | Path | Auth | Route-level limit | Source |\n|---|---|---|---|---|")
        for r in shown:
            print(f"| {r.method} | `{r.path}` | {r.auth} | {r.limit} | `{r.source}` |")
    else:
        width = max((len(r.path) for r in shown), default=10)
        for r in shown:
            print(f"{r.method:6} {r.path:{width}}  {r.auth:28} {r.limit:30} {r.source}")

    public = sum(r.auth == "PUBLIC" for r in routes)
    print(f"\n{len(routes)} routes · {public} public · "
          f"{sum(r.limit != '-' for r in routes)} with a route-level rate limit")
    print("Limits enforced inside services (e.g. the contact-reveal window) are not detected; check the service.")

    unguarded = [r for r in routes if r.path.split("/v1", 1)[-1].startswith("/admin")
                 and not r.auth.startswith("admin:")
                 and r.path.split("/v1", 1)[-1] not in ADMIN_OPEN_BY_DESIGN]
    for r in unguarded:
        print(f"ERROR: admin route without a permission: {r.method} {r.path} ({r.source})", file=sys.stderr)
    return 1 if unguarded else 0


if __name__ == "__main__":
    sys.exit(main())
