#!/usr/bin/env python3
"""Check a VDA 5050 message file against the bundled official JSON schema and against the rules of
the spec text that a JSON schema cannot express.

usage: validate.py <topic> <message.json> [--spec 2.1.0|3.0.0]

The spec version comes from --spec or from the major number of the message "version" field.
Output: one line per finding, "error: ..." or "warning: ...", then an OK or FAIL summary line.
Fields the schema does not define are warnings: the schemas allow extra fields, so a name from
another spec version would otherwise pass unnoticed.
Exit code: 0 no errors (warnings allowed), 1 errors, 2 the message could not be checked.
Rule references point to sections of spec/VDA5050_EN-3.0.0.md.
"""
import argparse
import json
import pathlib
import sys

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"
SPEC_FOR_MAJOR = {"2": "2.1.0", "3": "3.0.0"}


def deref(node, root):
    """Follow local "$ref" pointers until a real schema node is reached."""
    while isinstance(node, dict) and "$ref" in node:
        target = root
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        node = target
    return node


def merged(node, root):
    """(properties, items) of a schema node, including allOf/anyOf/oneOf and if-then/else branches."""
    node = deref(node, root)
    props, items = dict(node.get("properties") or {}), node.get("items")
    branches = node.get("allOf", []) + node.get("anyOf", []) + node.get("oneOf", [])
    branches += [node[key] for key in ("then", "else") if key in node]
    for branch in branches:
        branch_props, branch_items = merged(branch, root)
        props.update(branch_props)
        items = items or branch_items
    return props, items


def unknown_fields(value, node, root, path=""):
    """Paths of object keys in value that the schema node does not define."""
    props, items = merged(node, root)
    found = []
    if isinstance(value, dict) and props:
        for key, child in value.items():
            if key in props:
                found += unknown_fields(child, props[key], root, f"{path}{key}/")
            else:
                found.append(path + key)
    elif isinstance(value, list) and isinstance(items, dict):
        for index, child in enumerate(value):
            found += unknown_fields(child, items, root, f"{path}{index}/")
    return found


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def name_of(item):
    return item.get("nodeId") or item.get("edgeId") or "?"


def chain(node_list, edge_list):
    """Nodes and edges that carry an integer sequenceId, as (sequenceId, kind, item), in sequence order.
    Entries without one are left to the schema check."""
    entries = [(item["sequenceId"], kind, item)
               for kind, group in (("node", node_list), ("edge", edge_list))
               for item in group if isinstance(item, dict) and is_int(item.get("sequenceId"))]
    return sorted(entries, key=lambda entry: entry[0])


def numbering_errors(entries):
    """6.1.1: one shared, gap-free sequenceId run; nodes even (0, 2, ...), edges odd (1, 3, ...)."""
    errors = []
    numbers = [number for number, _, _ in entries]
    repeated = sorted({number for number in numbers if numbers.count(number) > 1})
    if repeated:
        errors.append(f"6.1.1: sequenceId used more than once: {repeated}")
    for number, kind, item in entries:
        if (number % 2 == 0) != (kind == "node"):
            errors.append(f"6.1.1: {kind} {name_of(item)} has sequenceId {number}; "
                          "nodes take even and edges odd numbers")
    if numbers:
        gaps = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
        if gaps:
            errors.append(f"6.1.1: sequenceId is not continuous, missing {gaps}")
    return errors


def release_order_errors(entries):
    """6.1.1: "After an unreleased edge, no released nodes or edges can follow in the sequence"."""
    blocking_edge = None
    for _, kind, item in entries:
        if blocking_edge is not None and item.get("released") is True:
            return [f"6.1.1: {kind} {name_of(item)} is released but follows unreleased edge {name_of(blocking_edge)}"]
        if kind == "edge" and item.get("released") is not True and blocking_edge is None:
            blocking_edge = item
    return []


def order_errors(msg):
    node_list = [item for item in msg.get("nodes") or [] if isinstance(item, dict)]
    edge_list = [item for item in msg.get("edges") or [] if isinstance(item, dict)]
    if not node_list:
        return ["6.1.1: an order needs at least one node"]
    errors = []
    if len(edge_list) != len(node_list) - 1:
        errors.append(f"6.1.1: {len(edge_list)} edges for {len(node_list)} nodes; "
                      f"an order needs exactly {len(node_list) - 1}")
    entries = chain(node_list, edge_list)
    errors += numbering_errors(entries)
    if entries:
        start, kind, first = entries[0]
        if msg.get("orderUpdateId") == 0 and start != 0:
            errors.append(f"6.1.1: a new order (orderUpdateId 0) starts at sequenceId 0, not {start}")
        if kind == "node" and first.get("released") is not True:
            errors.append(f"6.1.1: first node {name_of(first)} must be released")
    at = {number: item for number, _, item in entries}
    for number, kind, item in entries:
        if kind != "edge":
            continue
        ends = (at.get(number - 1), at.get(number + 1))
        if item.get("released") is True and not all(end and end.get("released") is True for end in ends):
            errors.append(f"6.1.1: edge {name_of(item)} is released but its start or end node is not")
        # 2.x edges name their nodes (2.1 schema: "The nodeId of the start node" / "of the end node")
        for field, end in zip(("startNodeId", "endNodeId"), ends):
            if field in item and end is not None and item[field] != end.get("nodeId"):
                errors.append(f"2.1 order: edge {name_of(item)} {field} is {item[field]!r}, "
                              f"but the neighbouring node is {end.get('nodeId')!r}")
    errors += release_order_errors(entries)
    action_ids = [action.get("actionId") for item in node_list + edge_list
                  for action in item.get("actions") or [] if isinstance(action, dict)]
    repeated = sorted({action_id for action_id in action_ids
                       if action_id is not None and action_ids.count(action_id) > 1})
    if repeated:
        errors.append(f"7.3: actionId must be unique, repeated: {repeated}")
    return errors


def state_findings(msg):
    entries = chain([item for item in msg.get("nodeStates") or [] if isinstance(item, dict)],
                    [item for item in msg.get("edgeStates") or [] if isinstance(item, dict)])
    errors = numbering_errors(entries)
    # 7.8: lastNodeSequenceId "can be arbitrary and shall be ignored" while lastNodeId is ""
    last = msg.get("lastNodeSequenceId")
    if msg.get("lastNodeId") and is_int(last):
        behind = [number for number, _, _ in entries if number <= last]
        if behind:
            errors.append(f"6.6.1: nodeStates/edgeStates hold only upcoming nodes and edges; "
                          f"sequenceId {behind} is not after lastNodeSequenceId {last}")
    errors += release_order_errors(entries)
    warnings = []
    if msg.get("driving") is True and "mobileRobotPosition" not in msg and "agvPosition" not in msg:
        warnings.append("6.6.1: driving but no position in the state; "
                        "a robot that can determine its position shall publish it")
    return errors, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check a VDA 5050 message against the official schema and spec rules.")
    parser.add_argument("topic", help="order, instantActions, state, connection, factsheet, visualization, zoneSet, responses")
    parser.add_argument("message", help="path of the message JSON file")
    parser.add_argument("--spec", choices=sorted(path.name for path in SCHEMAS.iterdir() if path.is_dir()))
    args = parser.parse_args(argv)
    try:
        import jsonschema
    except ImportError:
        print("error: jsonschema is not installed (pip install jsonschema)", file=sys.stderr)
        return 2
    try:
        text = pathlib.Path(args.message).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {args.message}: {exc}", file=sys.stderr)
        return 2
    try:
        msg = json.loads(text)
    except ValueError as exc:
        print(f"error: not valid JSON: {exc}")
        print(f"FAIL: {args.topic} {args.message}")
        return 1
    if not isinstance(msg, dict):
        print("error: a VDA 5050 message is a JSON object")
        print(f"FAIL: {args.topic} {args.message}")
        return 1
    spec = args.spec or SPEC_FOR_MAJOR.get(str(msg.get("version", "")).split(".")[0])
    if spec is None:
        print(f"error: cannot tell the spec version from version={msg.get('version')!r}; pass --spec",
              file=sys.stderr)
        return 2
    schema_file = SCHEMAS / spec / f"{args.topic}.schema.json"
    if not schema_file.exists():
        topics = sorted(path.name.split(".")[0] for path in (SCHEMAS / spec).glob("*.schema.json"))
        print(f"error: no {spec} schema for topic {args.topic!r}; topics: {topics}", file=sys.stderr)
        return 2
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    checker = jsonschema.validators.validator_for(schema)(schema)
    errors = [f"schema: {'/'.join(map(str, problem.absolute_path)) or '<root>'}: {problem.message}"
              for problem in checker.iter_errors(msg)]
    warnings = [f"field not in the {spec} schema: {path} (another version's name? see schema-diff)"
                for path in unknown_fields(msg, schema, schema)]
    if args.topic == "order":
        errors += order_errors(msg)
    elif args.topic == "state":
        state_errors, state_warnings = state_findings(msg)
        errors += state_errors
        warnings += state_warnings
    for line in errors:
        print(f"error: {line}")
    for line in warnings:
        print(f"warning: {line}")
    print(f"{'FAIL' if errors else 'OK'}: {args.topic} {spec} {args.message} "
          f"({len(errors)} errors, {len(warnings)} warnings)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
