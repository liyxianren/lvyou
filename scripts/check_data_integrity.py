import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "trip.json"


def walk(value, path="root"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    suspicious = [(path, value) for path, value in walk(data) if "??" in value or "?" * 3 in value]
    if suspicious:
        print("Suspicious replacement characters found:")
        for path, value in suspicious:
            print(f"- {path}: {value}")
        raise SystemExit(1)
    print("trip.json encoding/content check passed")


if __name__ == "__main__":
    main()
