import argparse
from dataclasses import dataclass
from pathlib import Path
import re

EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv"}
TEXT_EXTENSIONS = {".py", ".md", ".yml", ".yaml", ".txt"}


@dataclass(frozen=True)
class Finding:
    category: str
    path: Path
    line_number: int
    message: str


def should_scan(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    return not any(part in EXCLUDED_DIRS for part in path.parts)


def has_todo_comment(line: str, comment_prefix: str) -> bool:
    comment_index = line.find(comment_prefix)
    if comment_index == -1:
        return False
    comment_text = line[comment_index + len(comment_prefix) :]
    return "TODO" in comment_text or "FIXME" in comment_text


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    todo_comment_prefix = "#" if path.suffix.lower() in {".py", ".yml", ".yaml"} else ""
    for line_number, line in enumerate(content, start=1):
        if todo_comment_prefix and has_todo_comment(line, todo_comment_prefix):
            findings.append(
                Finding(
                    category="Improvement",
                    path=path,
                    line_number=line_number,
                    message="TODO/FIXME comment",
                )
            )
        if re.match(r"^\s*except\s*:\s*(#.*)?$", line):
            findings.append(
                Finding(
                    category="Bug",
                    path=path,
                    line_number=line_number,
                    message="Bare except detected",
                )
            )
        if re.search(r"subprocess\.\w+\([^#]*\bshell\s*=\s*True", line):
            findings.append(
                Finding(
                    category="Bug",
                    path=path,
                    line_number=line_number,
                    message="subprocess call with shell=True",
                )
            )
    return findings


def run_audit(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in root.rglob("*"):
        if path.is_file() and should_scan(path):
            findings.extend(scan_file(path))
    return findings


def print_report(findings: list[Finding], root: Path) -> None:
    print("=== Repository Audit ===")
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.category, []).append(finding)

    for category in ("Bug", "Improvement"):
        items = grouped.get(category, [])
        print(f"\n{category}s ({len(items)}):")
        if not items:
            print("- None found.")
            continue
        for finding in items:
            rel_path = finding.path.relative_to(root)
            print(f"- {rel_path}:{finding.line_number} → {finding.message}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan the repository for common bug/improvement patterns."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Repository root directory to scan.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    findings = run_audit(root)
    print_report(findings, root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
