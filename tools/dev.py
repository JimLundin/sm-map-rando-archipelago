"""The development tasks that take more than one command. Run with `uv run tools/dev.py <task> --help`.

The one-command loops (README) run directly: `uv run pytest tests/core`, `uv run pytest tests/rom`, ... `uv run`
rebuilds the engine module first when its Rust changed.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UV = shutil.which("uv") or "uv"


def run(*command: str | Path, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(str(part) for part in command), flush=True)
    subprocess.run([str(part) for part in command], cwd=cwd, env={**os.environ, **(env or {})}, check=True)


def python(script: str, *args: str | Path) -> None:
    run(sys.executable, ROOT / "tools" / script, *args)


def archipelago(path: str | None) -> Path:
    if not path:
        sys.exit("needs an Archipelago checkout: --ap PATH (or SMMR_AP)")
    return Path(path).expanduser().resolve()


def typecheck(args: argparse.Namespace) -> None:
    """pyright (pyproject.toml): strict for the core, its tests and the tools; the World against Archipelago."""
    link = ROOT / "build" / "archipelago"
    link.parent.mkdir(exist_ok=True)
    link.unlink(missing_ok=True)
    link.symlink_to(archipelago(args.ap), target_is_directory=True)
    run("pyright")


def asar(args: argparse.Namespace) -> None:
    """The assembler, from Map Rando's asar submodule (into build/asar)."""
    run("cmake", "-S", "MapRandomizer/asar/src", "-B", "build/asar", "-DCMAKE_BUILD_TYPE=Release", "-DASAR_GEN_LIB=OFF")
    run("cmake", "--build", "build/asar", "-j8")


def mw(args: argparse.Namespace) -> None:
    """Assemble the multiworld patch into world/smmr/data/mw.ips (ASAR: another assembler build)."""
    python("build_mw.py")


def data(args: argparse.Namespace) -> None:
    """The world data generated from Map Rando (commit the result)."""
    python("stage.py", "info", "-o", "world/smmr/data/info.json")
    python("gen_presets.py")


def fixtures(args: argparse.Namespace) -> None:
    """Re-record the seed fixture the core tests replay."""
    python("stage.py", "upgrade", "fixtures/settings/default-vanilla.json",
           "-o", "fixtures/settings/default-vanilla.upgraded.json")
    python("stage.py", "randomize", "fixtures/settings/default-vanilla.upgraded.json", "--seed", "1",
           "-o", "fixtures/seeds/default-vanilla-1.json")


def test_ap(args: argparse.Namespace) -> None:
    """The World's tests in an Archipelago checkout (worlds/smmr symlinked), with its requirements."""
    ap = archipelago(args.ap)
    link = ap / "worlds" / "smmr"
    if link.is_symlink() or not link.exists():
        link.unlink(missing_ok=True)
        link.symlink_to(ROOT / "world" / "smmr", target_is_directory=True)
    run(UV, "run", "--project", ROOT, "--with-requirements", ap / "requirements.txt", "pytest", "-q",
        "worlds/smmr/test", cwd=ap, env={"SKIP_REQUIREMENTS_UPDATE": "1", "SMMR_TEST_ROM": args.rom or ""})


def apworld(args: argparse.Namespace) -> None:
    """dist/smmr.apworld with this platform's engine, built --release, and Map Rando's data."""
    wheels = ROOT / "dist" / "wheels"
    shutil.rmtree(wheels, ignore_errors=True)
    run(UV, "run", "maturin", "build", "--release", "--out", wheels)
    sys.path.insert(0, str(ROOT / "world" / "smmr"))
    from core.engine import platform_tag
    [wheel] = wheels.glob("*.whl")
    python("build_apworld.py", "--engine", f"{platform_tag()}={wheel}")


def e2e(args: argparse.Namespace) -> None:
    """The packaged world: build it, generate, patch and boot (an Archipelago checkout without worlds/smmr)."""
    apworld(args)
    if not args.rom:
        sys.exit("needs the vanilla ROM: --rom PATH (or SMMR_TEST_ROM)")
    ap = archipelago(args.ap)
    run(UV, "run", "--with-requirements", ap / "requirements.txt", "python", ROOT / "tools" / "e2e.py",
        "--ap", ap, "--rom", args.rom)


TASKS: dict[str, Callable[[argparse.Namespace], None]] = {
    "typecheck": typecheck, "asar": asar, "mw": mw, "data": data, "fixtures": fixtures, "test-ap": test_ap,
    "apworld": apworld, "e2e": e2e,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    tasks = parser.add_subparsers(dest="task", required=True)
    for name, task in TASKS.items():
        sub = tasks.add_parser(name, help=(task.__doc__ or "").split("\n")[0])
        sub.add_argument("--ap", default=os.environ.get("SMMR_AP"), help="an Archipelago checkout (SMMR_AP)")
        sub.add_argument("--rom", default=os.environ.get("SMMR_TEST_ROM"), help="the vanilla ROM (SMMR_TEST_ROM)")
    args = parser.parse_args()
    TASKS[args.task](args)


if __name__ == "__main__":
    main()
