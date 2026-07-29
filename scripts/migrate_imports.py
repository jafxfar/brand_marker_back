"""One-off: replace app. imports with src. after app/ rename."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"venv", ".pytest_cache", "brandmarket_backend.egg-info", "__pycache__"}


def main() -> None:
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        new = text.replace("from src.", "from src.").replace("import src.", "import src.")
        if new != text:
            path.write_text(new, encoding="utf-8")
            print(f"updated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
