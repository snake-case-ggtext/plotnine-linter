"""Command line.

    plotnine-linter rules [--markdown]      # list the rule catalog
    plotnine-linter check project.ipynb      # run a notebook, lint every plot it draws
    plotnine-linter check script.py [...]   # run scripts, lint every plot they make
    plotnine-linter audit project.ipynb      # Chartability audit of every plot, as markdown checklists
    plotnine-linter audit project.ipynb --check-answers   # report checklist items left unanswered
"""

from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path


def _rules(markdown: bool) -> int:
    from .registry import all_rules

    rules = all_rules()
    if markdown:
        tiers = {1: "Tier 1 — Errors (on by default)", 2: "Tier 2 — Clarity (on by default)", 3: "Tier 3 — Style (opt-in)"}
        for tier, heading in tiers.items():
            print(f"## {heading}\n")
            print("| ID | Rule | Why | Fix |\n| --- | --- | --- | --- |")
            for r in rules:
                if r.tier == tier:
                    note = " *(heuristic, reported as info)*" if r.heuristic else ""
                    print(f"| {r.id} | {r.title}{note} | {r.why} | {r.fix} |")
            print()
    else:
        for r in rules:
            print(f"{r.id}  tier {r.tier}  {r.title}")
    return 0


def _check(paths: list[str], fmt: str, fail_on: str, timeout: int = 900, save_images: str | None = None) -> int:
    notebooks = [p for p in paths if p.endswith(".ipynb")]
    scripts = [p for p in paths if not p.endswith(".ipynb")]
    worst = 0
    if notebooks:
        from .notebook import check_notebook

        results = []
        for p in notebooks:
            img_dir = str(Path(save_images) / Path(p).stem) if save_images else None
            results.append(check_notebook(p, timeout=timeout, save_images_to=img_dir))
        if fmt == "json":
            print(json.dumps([r.to_dict() for r in results], indent=2))
        else:
            print("\n\n".join(str(r) for r in results))
        worst = int(any(r.at_least(fail_on) for r in results))
    if scripts:
        worst = max(worst, _check_scripts(scripts, fmt, fail_on))
    return worst


def _check_scripts(paths: list[str], fmt: str, fail_on: str) -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .api import lint
    from .describe.spec import is_ggplot

    worst = 0
    reports = []
    plt.show = lambda *a, **k: None  # scripts call plt.show(); keep figures open
    from .describe.render import tag_histograms

    tag_histograms()
    for path in paths:
        source = Path(path).read_text()
        plt.close("all")
        namespace = runpy.run_path(path, run_name="__main__")
        targets = [(f"figure {n}", plt.figure(n)) for n in plt.get_fignums()]
        targets += [(name, obj) for name, obj in namespace.items() if is_ggplot(obj)]
        for name, obj in targets:
            report = lint(obj, source=source)
            reports.append((path, name, report))
            if report.at_least(fail_on):
                worst = 1
    if fmt == "json":
        print(json.dumps([{"file": p, "plot": n, **r.to_dict()} for p, n, r in reports], indent=2))
    else:
        for p, n, r in reports:
            print(f"{p} [{n}]")
            print("  " + str(r).replace("\n", "\n  "))
    return worst


def _audit(paths: list[str], fmt: str, timeout: int) -> int:
    from .notebook import check_notebook

    out_json = []
    for path in paths:
        if not path.endswith(".ipynb"):
            print(f"{path}: audit works on notebooks (.ipynb)", file=sys.stderr)
            return 2
        result = check_notebook(path, timeout=timeout, audit=True)
        if fmt == "json":
            out_json.append(
                {
                    "path": path,
                    "error": result.error,
                    "plots": [
                        {"cell": pr.cell, "audit": pr.audit.to_dict() if pr.audit else None} for pr in result.plots
                    ],
                }
            )
            continue
        print(f"# {path}: {len(result.plots)} plot(s)\n")
        if result.error:
            print(f"could not finish running: {result.error}\n")
        for pr in result.plots:
            if pr.audit is None:
                continue
            if fmt == "markdown":
                print(f"<!-- cell {pr.cell} -->")
                print(pr.audit.to_markdown())
            else:
                print(f"cell {pr.cell}: " + str(pr.audit).replace("\n", "\n  "))
                print()
    if fmt == "json":
        print(json.dumps(out_json, indent=2))
    return 0


def _check_answers(paths: list[str]) -> int:
    import nbformat

    from .audit import read_checklists

    incomplete = 0
    for path in paths:
        nb = nbformat.read(path, as_version=4)
        found = []
        for i, cell in enumerate(nb.cells, start=1):
            if cell.cell_type == "markdown":
                found += [(i, c) for c in read_checklists(cell.source)]
        if not found:
            print(f"{path}: no accessibility checklists found")
            incomplete += 1
            continue
        done = sum(c.complete for _, c in found)
        print(f"{path}: {done} of {len(found)} checklist(s) complete")
        for i, c in found:
            if not c.complete:
                incomplete += 1
                print(f"  cell {i}, " + str(c).replace("\n", "\n  "))
    return 1 if incomplete else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="plotnine-linter")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rules", help="list the rule catalog")
    r.add_argument("--markdown", action="store_true")
    c = sub.add_parser("check", help="run notebooks (.ipynb) or Python scripts and lint every plot they make")
    c.add_argument("paths", nargs="+")
    c.add_argument("--format", choices=["text", "json"], default="text")
    c.add_argument("--fail-on", default="error", choices=["info", "warning", "error"])
    c.add_argument("--timeout", type=int, default=900, help="seconds allowed per notebook")
    c.add_argument("--save-images", metavar="DIR", help="save a PNG of each linted notebook plot under DIR")
    a = sub.add_parser("audit", help="Chartability audit of every plot in notebooks (.ipynb)")
    a.add_argument("paths", nargs="+")
    a.add_argument("--format", choices=["markdown", "text", "json"], default="markdown")
    a.add_argument("--timeout", type=int, default=900, help="seconds allowed per notebook")
    a.add_argument(
        "--check-answers",
        action="store_true",
        help="don't run anything: read the checklists pasted into the notebooks and list what's unanswered",
    )
    args = parser.parse_args(argv)
    if args.cmd == "rules":
        return _rules(args.markdown)
    if args.cmd == "audit":
        if args.check_answers:
            return _check_answers(args.paths)
        return _audit(args.paths, args.format, args.timeout)
    return _check(args.paths, args.format, args.fail_on, args.timeout, args.save_images)


if __name__ == "__main__":
    sys.exit(main())
