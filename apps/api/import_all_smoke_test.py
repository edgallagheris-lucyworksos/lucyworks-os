"""Import smoke test for LucyWorksOS API route modules."""
import importlib
import pkgutil

import app


def main() -> None:
    failures: list[str] = []
    loaded: list[str] = []
    for _, modname, _ in pkgutil.iter_modules(app.__path__):
        if modname.endswith("_routes") or modname in {"main", "main_fixed", "models", "database"}:
            target = f"app.{modname}"
            try:
                importlib.import_module(target)
                loaded.append(target)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{target}: {exc}")
    print(f"Imported {len(loaded)} modules")
    if failures:
        print("Failures:")
        for f in failures:
            print(f" - {f}")
        raise SystemExit(1)
    print("Import smoke passed")


if __name__ == "__main__":
    main()
