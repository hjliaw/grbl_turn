from pathlib import Path

RESOURCES = Path(__file__).resolve().parent / "resources" / "images"
ICONS = Path(__file__).resolve().parent / "resources" / "icons"


def resource(name: str) -> str:
    return str(RESOURCES / name)
