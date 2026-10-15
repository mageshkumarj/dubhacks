import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted([*ROOT.glob("api/**/*.py"), *ROOT.glob("datagen/**/*.py"), *ROOT.glob("scripts/*.py")])


def test_sources_parse_as_python_311():
    failures = []
    for path in SOURCES:
        try:
            ast.parse(path.read_text(), feature_version=(3, 11))
        except SyntaxError as exc:
            failures.append(f"{path.relative_to(ROOT)}:{exc.lineno}")
    assert not failures, f"Python 3.12+ syntax in: {failures}"
