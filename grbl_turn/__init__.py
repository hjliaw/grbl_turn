from pathlib import Path

RESOURCES = Path(__file__).resolve().parent / "resources" / "images"


def resource(name: str) -> str:
    return str(RESOURCES / name)
