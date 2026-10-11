"""Old command line, kept for scripts that still use it. The builder is builder/build.py.

    python3 builder.py [--api FILE] [--slot S] [--practice A|B] brief.md [later_brief.md ...]
is the same as
    python3 builder/build.py <last brief> <api file> --base <earlier briefs> [--slot S] [--practice A|B]
"""
import argparse, pathlib, runpy, sys

KIT = pathlib.Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("briefs", nargs="+"); ap.add_argument("--api", default=str(KIT / "tools" / "openapi.json"))
ap.add_argument("--slot"); ap.add_argument("--practice", choices=["A", "B"])
a = ap.parse_args()
argv = [str(KIT / "builder" / "build.py"), a.briefs[-1], a.api]
if a.briefs[:-1]: argv += ["--base", *a.briefs[:-1]]
if a.slot: argv += ["--slot", a.slot]
if a.practice: argv += ["--practice", a.practice]
sys.argv = argv
runpy.run_path(argv[0], run_name="__main__")
