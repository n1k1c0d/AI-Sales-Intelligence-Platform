"""Check tracked paths, portable exports and relative Markdown links without reading local environments."""
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = """
README.md .gitignore .editorconfig .env.example docker-compose.yml
.github/workflows/ci.yml apps/api/pyproject.toml apps/api/uv.lock apps/web/package.json
apps/web/package-lock.json automations/n8n/workflows/system-health-check.json
docs/PROJECT_CONTEXT.md docs/ARCHITECTURE.md docs/ROADMAP.md docs/TEST_STRATEGY.md
""".split()
RUNTIME = {".venv", "node_modules", ".next", ".n8n", "__pycache__", ".pytest_cache",
           ".mypy_cache", ".ruff_cache", ".turbo", "dist", "build", "reports", "coverage", "htmlcov",
           "n8n_data", "postgres_data", ".cache", ".tox", "out", "venv", "tmp", "temp"}
MARKER = re.compile(r"^(?:<{7} |={7}$|>{7} )", re.M)
LINK = re.compile(r"\[[^\]\n]*\]\((?:<([^>\n]+)>|([^()\s]+))(?:\s+\"[^\"]+\")?\)")


def git_paths(*args):
    output = subprocess.check_output(["git", "ls-files", "-z", *args], cwd=ROOT).decode("utf-8")
    return {Path(p) for p in output.split("\0") if p}


def forbidden(path):
    name = path.name.lower()
    return (bool(RUNTIME.intersection(path.parts)) or
            ((name == ".env" or name.startswith(".env.")) and not name.endswith(".example")) or
            name.endswith((".sqlite", ".sqlite3", ".sqlite-wal", ".sqlite-shm", ".pyc",
                           ".db", ".db-journal", ".tsbuildinfo", ".whl", ".dump", ".log")) or
            name == ".coverage" or ("credential" in name and name.endswith(".json")))


def main():
    files = git_paths("--cached", "--others", "--exclude-standard")
    errors = [f"Missing required file: {p}" for p in REQUIRED if Path(p) not in files or not (ROOT / p).is_file()]
    for path in sorted(files):
        if forbidden(path):
            errors.append(f"Unexpected runtime or private file: {path}")
            continue
        source = ROOT / path
        if not source.is_file():
            errors.append(f"Missing from checkout: {path}")
            continue
        if source.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}:
            continue
        try:
            content = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if MARKER.search(content):
            errors.append(f"Merge marker: {path}")
        if path.parent.as_posix() == "automations/n8n/workflows" and path.suffix == ".json":
            try:
                json.loads(content)
            except ValueError:
                errors.append(f"Invalid JSON: {path}")
        if path.suffix.lower() == ".md":
            prose = re.sub(r"^ *\x60{3,}.*?^ *\x60{3,}[ \t]*$", "", content, flags=re.M | re.S)
            for bracketed, plain in LINK.findall(prose):
                url = urlsplit(bracketed or plain)
                if url.scheme or url.netloc or not url.path:
                    continue
                target = source.parent / unquote(url.path)
                if not target.exists():
                    errors.append(f"Broken link in {path}: {url.path}")
    if errors:
        sys.exit("\n".join(errors))
    print(f"PASS: {len(files)} repository paths, required files, export JSON and local links")


if __name__ == "__main__":
    main()
