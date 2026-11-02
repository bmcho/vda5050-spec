"""List field paths (with enums) added/removed between two bundled schema versions.

usage: python3 scripts/schema_diff.py [OLD] [NEW]   (default 2.1.0 3.0.0)

$ref, allOf/anyOf/oneOf and if/then/else are resolved, so a field that only moved into
"definitions" does not show up as removed + added.
"""
import json
import sys

from validate import SCHEMAS, deref, merged


def paths(node, root, p="", out=None, depth=0):
    out = set() if out is None else out
    if depth > 15:  # guard against recursive $ref
        return out
    props, items = merged(node, root)
    for k, v in props.items():
        q = f"{p}.{k}" if p else k
        v = deref(v, root)
        enum = v.get("enum") or deref(v.get("items") or {}, root).get("enum")
        kind = v.get("type")
        out.add(q + (f" {sorted(enum)}" if enum else "") + (f" ({kind})" if isinstance(kind, str) else ""))
        paths(v, root, q, out, depth + 1)
    if isinstance(items, dict) and not props:
        paths(items, root, p + "[]", out, depth + 1)
    return out


def load_paths(file):
    if not file.exists():
        return set()
    schema = json.loads(file.read_text())
    return paths(schema, schema)


def main(old="2.1.0", new="3.0.0"):
    a_dir, b_dir = SCHEMAS / old, SCHEMAS / new
    for name in sorted({f.name for f in a_dir.glob("*.json")} | {f.name for f in b_dir.glob("*.json")}):
        a, b = load_paths(a_dir / name), load_paths(b_dir / name)
        print(f"## {name}")
        print(*(f"- {x}" for x in sorted(a - b)), sep="\n")
        print(*(f"+ {x}" for x in sorted(b - a)), sep="\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])
