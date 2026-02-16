import argparse
from dataclasses import dataclass
from pathlib import Path
import re

EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv"}
TEXT_EXTENSIONS = {".py", ".md", ".yml", ".yaml"}


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


def has_hash_comment_todo(line: str) -> bool:
    comment_index = line.find("#")
    if comment_index == -1:
        return False
    comment_text = line[comment_index + 1 :]
    return "TODO" in comment_text or "FIXME" in comment_text


def has_markdown_comment_todo(line: str) -> bool:
    start = line.find("<!--")
    if start == -1:
        return False
    end = line.find("-->", start + 4)
    if end == -1:
        return False
    comment_text = line[start + 4 : end]
    return "TODO" in comment_text or "FIXME" in comment_text


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    suffix = path.suffix.lower()
    is_python = suffix == ".py"
    is_yaml = suffix in {".yml", ".yaml"}
    is_markdown = suffix == ".md"
    for line_number, line in enumerate(content, start=1):
        if (is_python or is_yaml) and has_hash_comment_todo(line):
            findings.append(
                Finding(
                    category="Improvement",
                    path=path,
                    line_number=line_number,
                    message="TODO/FIXME comment",
                )
            )
        if is_markdown and has_markdown_comment_todo(line):
            findings.append(
                Finding(
                    category="Improvement",
                    path=path,
                    line_number=line_number,
                    message="TODO/FIXME comment",
                )
            )
        if is_python:
            if re.match(r"^\s*except\s*:\s*(#.*)?$", line):
                findings.append(
                    Finding(
                        category="Bug",
                        path=path,
                        line_number=line_number,
                        message="Bare except detected",
                    )
                )
            comment_index = line.find("#")
            code_segment = line if comment_index == -1 else line[:comment_index]
            if re.search(r"subprocess\.\w+\([^)]*\bshell\s*=\s*True", code_segment):
                findings.append(
                    Finding(
                        category="Security",
                        path=path,
                        line_number=line_number,
                        message="Security risk: subprocess call with shell=True",
                    )
                )
    return findings


def run_audit(root: Path) -> dict[Path, list[Finding]]:
    findings_by_file: dict[Path, list[Finding]] = {}
    for path in root.rglob("*"):
        if path.is_file() and should_scan(path):
            findings_by_file[path] = scan_file(path)
    return findings_by_file


def print_report(findings_by_file: dict[Path, list[Finding]], root: Path) -> None:
    print("=== Repository Audit ===")
    findings = [finding for items in findings_by_file.values() for finding in items]
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.category, []).append(finding)

    categories = [
        ("Security", "Security Issues"),
        ("Bug", "Bugs"),
        ("Improvement", "Improvements"),
    ]
    for category, label in categories:
        items = grouped.get(category, [])
        print(f"\n{label} ({len(items)}):")
        if not items:
            print("- None found.")
            continue
        for finding in items:
            rel_path = finding.path.relative_to(root)
            print(f"- {rel_path}:{finding.line_number} → {finding.message}")

    print("\nFindings by file:")
    for path in sorted(findings_by_file, key=lambda item: str(item)):
        rel_path = path.relative_to(root)
        items = findings_by_file[path]
        print(f"\n{rel_path} ({len(items)}):")
        if not items:
            print("- None found.")
            continue
        for finding in items:
            print(
                f"- Line {finding.line_number} [{finding.category}] {finding.message}"
            )


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
    findings_by_file = run_audit(root)
    print_report(findings_by_file, root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
