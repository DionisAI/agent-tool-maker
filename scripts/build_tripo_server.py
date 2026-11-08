"""Deterministic package snapshot of the existing reviewed DOM adapters; no installation/login."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("studio_builder", ROOT / "scripts/build_tripo_studio.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def definitions():
    result = {op: builder.manifest(op) for op in ("account", "assets", "quote", "generate")}
    for operations, factory in [(builder.EXTENDED_OPERATIONS, builder.extended_manifest),
            (builder.WORKSPACE_OPERATIONS, builder.workspace_manifest),
            (builder.QUERY_OPERATIONS, builder.query_manifest),
            (builder.UI_OPTIONS_OPERATIONS, builder.ui_options_manifest),
            (builder.VIEWER_OPERATIONS, builder.viewer_manifest),
            (builder.IMAGE_FORM_OPERATIONS, builder.image_form_manifest)]:
        result.update({op: factory(op) for op in operations})
    return result


def main():
    destination = ROOT / "src/agent_tool_maker/data/tripo_server"
    destination.mkdir(parents=True, exist_ok=True)
    for source in sorted((ROOT / "examples/opencli/tripo-studio").iterdir()):
        if source.suffix in {".mjs", ".js"}:
            (destination / source.name).write_bytes(source.read_bytes())
    (destination / "index.json").write_text(json.dumps(definitions(), ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"tools": len(definitions()), "source": "reviewed_repository_adapters", "installation": False}))


if __name__ == "__main__":
    main()
