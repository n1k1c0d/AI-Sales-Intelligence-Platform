"""Verify that both Python distributions carry the backend package and type marker."""
import sys
import tarfile
import zipfile
from pathlib import Path

dist = Path(sys.argv[1])
wheel, = dist.glob("*.whl")
sdist, = dist.glob("*.tar.gz")
with zipfile.ZipFile(wheel) as archive, tarfile.open(sdist) as source:
    packaged = set(archive.namelist())
    sources = {p.split("/", 1)[-1] for p in source.getnames()}
    modules = Path(__file__).resolve().parents[1] / "apps/api/src"
    expected = {p.relative_to(modules).as_posix() for p in modules.rglob("*.py")}
    expected.add("dealmind/py.typed")
    if not expected <= packaged or not {"src/" + name for name in expected} <= sources:
        sys.exit("Missing backend module or py.typed in wheel or sdist")
    print(f"PASS: wheel and sdist include {len(expected)} package files")
