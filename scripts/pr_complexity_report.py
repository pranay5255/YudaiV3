#!/usr/bin/env python3
"""Report simple cyclomatic complexity estimates for Python changes."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class FunctionComplexity:
    path: Path
    name: str
    line: int
    complexity: int


class ComplexityVisitor(ast.NodeVisitor):
    """Estimate cyclomatic complexity for one function body."""

    def __init__(self) -> None:
        self.complexity = 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.complexity += len(node.cases)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.complexity += 1 + len(node.ifs)
        self.generic_visit(node)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print a markdown complexity report for changed Python files."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional Python files or directories. Defaults to changed files.",
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base ref for changed-file detection. Default: origin/main.",
    )
    parser.add_argument(
        "--warn-threshold",
        type=int,
        default=8,
        help="Warn when a function complexity is at least this value. Default: 8.",
    )
    parser.add_argument(
        "--fail-threshold",
        type=int,
        default=10,
        help="Mark high risk when complexity is greater than this value. Default: 10.",
    )
    return parser.parse_args(argv)


def run_git_changed_files(base: str) -> list[Path]:
    command = [
        "git",
        "diff",
        "--name-only",
        "--diff-filter=ACMRT",
        f"{base}...HEAD",
    ]
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "git diff failed"
        raise RuntimeError(detail)
    return [Path(line) for line in completed.stdout.splitlines() if line.strip()]


def iter_python_paths(paths: Iterable[Path]) -> list[Path]:
    discovered: set[Path] = set()
    for path in paths:
        if path.is_dir():
            for child in path.rglob("*.py"):
                if "__pycache__" not in child.parts:
                    discovered.add(child)
        elif path.is_file() and path.suffix == ".py":
            discovered.add(path)
    return sorted(discovered)


def function_name(prefix: tuple[str, ...], name: str) -> str:
    return ".".join((*prefix, name)) if prefix else name


def iter_function_complexities(
    tree: ast.AST,
    path: Path,
    prefix: tuple[str, ...] = (),
) -> Iterable[FunctionComplexity]:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            yield from iter_function_complexities(node, path, (*prefix, node.name))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visitor = ComplexityVisitor()
            for statement in node.body:
                visitor.visit(statement)
            yield FunctionComplexity(
                path=path,
                name=function_name(prefix, node.name),
                line=node.lineno,
                complexity=visitor.complexity,
            )
            yield from iter_function_complexities(node, path, (*prefix, node.name))


def collect_complexities(
    paths: Iterable[Path],
) -> tuple[list[FunctionComplexity], list[str]]:
    results: list[FunctionComplexity] = []
    errors: list[str] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"- `{path}`: {exc}")
            continue
        results.extend(iter_function_complexities(tree, path))
    return sorted(results, key=lambda item: (str(item.path), item.line)), errors


def risk_label(complexity: int, warn_threshold: int, fail_threshold: int) -> str:
    if complexity > fail_threshold:
        return "high risk"
    if complexity >= warn_threshold:
        return "warn"
    return "ok"


def print_report(
    paths: Sequence[Path],
    results: Sequence[FunctionComplexity],
    errors: Sequence[str],
    warn_threshold: int,
    fail_threshold: int,
) -> None:
    print("# PR Complexity Report")
    print()
    print(f"- Python files scanned: {len(paths)}")
    print(f"- Warning threshold: >= {warn_threshold}")
    print(f"- High-risk threshold: > {fail_threshold}")
    print()

    noteworthy = [
        item
        for item in results
        if item.complexity >= warn_threshold or item.complexity > fail_threshold
    ]
    if noteworthy:
        print("## Findings")
        print()
        print("| Risk | Complexity | Function | Location |")
        print("| --- | ---: | --- | --- |")
        for item in sorted(
            noteworthy,
            key=lambda value: value.complexity,
            reverse=True,
        ):
            risk = risk_label(item.complexity, warn_threshold, fail_threshold)
            print(
                f"| {risk} | {item.complexity} | `{item.name}` | "
                f"`{item.path}:{item.line}` |"
            )
        print()
    else:
        print("No functions met the warning threshold.")
        print()

    if errors:
        print("## Skipped")
        print()
        print("\n".join(errors))
        print()

    if paths and results:
        highest = max(results, key=lambda item: item.complexity)
        print(
            "Highest observed complexity: "
            f"`{highest.name}` at `{highest.path}:{highest.line}` "
            f"with score {highest.complexity}."
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.paths:
        paths = iter_python_paths(Path(path) for path in args.paths)
    else:
        try:
            paths = iter_python_paths(run_git_changed_files(args.base))
        except RuntimeError as exc:
            print("# PR Complexity Report")
            print()
            print("Unable to detect changed Python files from git.")
            print()
            print(f"- Base ref: `{args.base}`")
            print(f"- Error: {exc}")
            print()
            print("Pass explicit paths or repair the local git object database and retry.")
            return 2

    results, errors = collect_complexities(paths)
    print_report(
        paths=paths,
        results=results,
        errors=errors,
        warn_threshold=args.warn_threshold,
        fail_threshold=args.fail_threshold,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
