"""Behavior tests for skills/vda5050-spec/scripts/validate.py.

Run from the repository root with a Python that has jsonschema installed:
    python3 -m unittest discover -s tests
Each test runs the script on a message file and checks the exit code and what it reports.
Spec references are to spec/VDA5050_EN-3.0.0.md unless noted.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "skills" / "vda5050-spec" / "scripts" / "validate.py"


def header(version="3.0.0"):
    return {"headerId": 1, "timestamp": "2026-10-15T09:00:00.000Z", "version": version,
            "manufacturer": "M", "serialNumber": "S1"}


def node(node_id, seq, released=True, **extra):
    return {"nodeId": node_id, "sequenceId": seq, "released": released, "actions": [], **extra}


def edge(edge_id, seq, released=True, **extra):
    return {"edgeId": edge_id, "sequenceId": seq, "released": released, "actions": [], **extra}


def order(nodes, edges, update_id=0, version="3.0.0"):
    return {**header(version), "orderId": "o1", "orderUpdateId": update_id, "nodes": nodes, "edges": edges}


def state30(**fields):
    msg = {**header("3.0.0"), "orderId": "o1", "orderUpdateId": 0, "lastNodeId": "n1", "lastNodeSequenceId": 0,
           "nodeStates": [], "edgeStates": [], "driving": False, "actionStates": [], "instantActionStates": [],
           "operatingMode": "AUTOMATIC", "errors": [],
           "powerSupply": {"stateOfCharge": 80.0, "charging": False},
           "safetyState": {"activeEmergencyStop": "NONE", "fieldViolation": False},
           "mobileRobotPosition": {"x": 1.0, "y": 2.0, "theta": 0.1, "mapId": "m", "localized": True}}
    msg.update(fields)
    return msg


def state21(**fields):
    msg = {**header("2.1.0"), "orderId": "o1", "orderUpdateId": 0, "lastNodeId": "n1", "lastNodeSequenceId": 0,
           "nodeStates": [], "edgeStates": [], "driving": False, "actionStates": [],
           "operatingMode": "AUTOMATIC", "errors": [],
           "batteryState": {"batteryCharge": 80.0, "charging": False},
           "safetyState": {"eStop": "NONE", "fieldViolation": False},
           "agvPosition": {"x": 1.0, "y": 2.0, "theta": 0.1, "mapId": "m", "positionInitialized": True}}
    msg.update(fields)
    return msg


def node_state(node_id, seq, released=True):
    return {"nodeId": node_id, "sequenceId": seq, "released": released}


def edge_state(edge_id, seq, released=True):
    return {"edgeId": edge_id, "sequenceId": seq, "released": released}


def run(topic, msg, *args):
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "msg.json"
        path.write_text(msg if isinstance(msg, str) else json.dumps(msg), encoding="utf-8")
        done = subprocess.run([sys.executable, str(SCRIPT), topic, str(path), *args],
                              capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


def lines(out, level):
    return [line for line in out.splitlines() if line.startswith(level + ":")]


class OrderRules(unittest.TestCase):
    def assert_clean(self, msg, *args):
        code, out, err = run("order", msg, *args)
        self.assertEqual((code, lines(out, "error"), lines(out, "warning")), (0, [], []), out + err)

    def assert_error_about(self, msg, needle):
        code, out, err = run("order", msg)
        self.assertEqual(code, 1, out + err)
        self.assertTrue(any(needle in line for line in lines(out, "error")), out + err)

    def test_valid_order_has_no_findings(self):
        # 3.0 edges carry no startNodeId/endNodeId, so nothing may be required of them
        self.assert_clean(order([node("n1", 0), node("n2", 2)], [edge("e1", 1)]))

    def test_order_without_nodes_fails(self):
        # 6.1.1: "there shall be at least one node"
        code, out, _ = run("order", order([], []))
        self.assertEqual(code, 1, out)

    def test_edge_count_must_be_nodes_minus_one(self):
        # 6.1.1: "the number of edges shall be equal to the number of nodes minus one"
        # numbering, release and continuity are all fine here; only the count is wrong
        code, out, _ = run("order", order([node("n1", 0), node("n2", 2)],
                                          [edge("e1", 1), edge("e2", 3, released=False)]))
        self.assertEqual(code, 1, out)

    def test_new_order_must_start_at_zero(self):
        # 6.1.1: "The first node has a sequenceId of 0"
        self.assert_error_about(order([node("n1", 2), node("n2", 4)], [edge("e1", 3)]), "orderUpdateId 0")

    def test_order_update_may_start_at_stitching_node(self):
        # 6.1.2: an update starts at the last base node of the previous update, keeping its sequenceId
        self.assert_clean(order([node("n1", 2), node("n2", 4)], [edge("e1", 3)], update_id=1))

    def test_gap_in_sequence_fails(self):
        # 6.1.1: "The sequenceId shall be continuous within an order"
        # 0, 1, 4: counts, parity and release order are fine; only 2 and 3 are missing
        code, out, _ = run("order", order([node("n1", 0), node("n2", 4, released=False)],
                                          [edge("e1", 1, released=False)]))
        self.assertEqual(code, 1, out)

    def test_node_with_odd_sequence_id_fails(self):
        # 6.1.1: nodes take 0, 2, 4 ...; edges take 1, 3, 5 ...
        self.assert_error_about(order([node("n1", 0), node("n2", 3)], [edge("e1", 1)]), "n2")

    def test_first_node_must_be_released(self):
        # 6.1.1: "The first node of an order ... always be released"
        self.assert_error_about(order([node("n1", 0, released=False), node("n2", 2, released=False)],
                                      [edge("e1", 1, released=False)]), "n1")

    def test_first_node_is_lowest_sequence_id_not_first_array_entry(self):
        self.assert_clean(order([node("n2", 2, released=False), node("n1", 0)], [edge("e1", 1, released=False)]))

    def test_released_edge_needs_released_end_nodes(self):
        # 6.1.1: "An edge can be released only if both the start and the end node of the edge are released"
        self.assert_error_about(order([node("n1", 0), node("n2", 2, released=False)], [edge("e1", 1)]), "e1")

    def test_nothing_released_after_unreleased_edge(self):
        # 6.1.1: "After an unreleased edge, no released nodes or edges can follow in the sequence"
        self.assert_error_about(order([node("n1", 0), node("n2", 2)], [edge("e1", 1, released=False)]), "n2")

    def test_action_ids_must_be_unique(self):
        # 7.3: actionId is a "Unique ID to identify the action"
        action = {"actionType": "pick", "actionId": "a1", "blockingType": "HARD"}
        self.assert_error_about(order([node("n1", 0, actions=[action]), node("n2", 2, actions=[dict(action)])],
                                      [edge("e1", 1)]), "a1")

    def test_missing_sequence_id_is_reported_not_crashing(self):
        bad = order([node("n1", 0), node("n2", 2)], [edge("e1", 1)])
        del bad["nodes"][1]["sequenceId"]
        code, out, err = run("order", bad)
        self.assertEqual(code, 1, out + err)
        self.assertNotIn("Traceback", err)
        self.assertTrue(lines(out, "error"), out + err)

    def test_v21_edges_must_name_their_neighbour_nodes(self):
        # 2.1 schema: startNodeId/endNodeId are "The nodeId of the start/end node" of the edge
        good = order([node("n1", 0), node("n2", 2)],
                     [edge("e1", 1, startNodeId="n1", endNodeId="n2")], version="2.1.0")
        self.assert_clean(good)
        bad = order([node("n1", 0), node("n2", 2)],
                    [edge("e1", 1, startNodeId="n1", endNodeId="nX")], version="2.1.0")
        self.assert_error_about(bad, "e1")

    def test_v21_names_in_v30_order_are_warned_but_pass(self):
        # chapter 4 allows additional parameters, so this is a warning, not an error
        msg = order([node("n1", 0), node("n2", 2)], [edge("e1", 1, maxSpeed=1.0, startNodeId="n1", endNodeId="n2")])
        code, out, err = run("order", msg)
        self.assertEqual(code, 0, out + err)
        warned = "\n".join(lines(out, "warning"))
        self.assertIn("maxSpeed", warned)
        self.assertIn("startNodeId", warned)


class StateRules(unittest.TestCase):
    def test_valid_state_has_no_findings(self):
        code, out, err = run("state", state30(nodeStates=[node_state("n2", 2)], edgeStates=[edge_state("e1", 1)]))
        self.assertEqual((code, lines(out, "error"), lines(out, "warning")), (0, [], []), out + err)

    def test_states_must_come_after_last_node(self):
        # 6.6.1: nodeStates/edgeStates "include all upcoming nodes and edges"
        code, out, _ = run("state", state30(lastNodeId="n2", lastNodeSequenceId=2, nodeStates=[node_state("n2", 2)]))
        self.assertEqual(code, 1, out)

    def test_last_sequence_id_ignored_while_last_node_id_empty(self):
        # 7.8: lastNodeSequenceId "can be arbitrary and shall be ignored" when lastNodeId is ""
        code, out, err = run("state", state30(lastNodeId="", lastNodeSequenceId=2, nodeStates=[node_state("n2", 2)]))
        self.assertEqual((code, lines(out, "error")), (0, []), out + err)

    def test_node_state_with_odd_sequence_id_fails(self):
        code, out, _ = run("state", state30(nodeStates=[node_state("n2", 3)]))
        self.assertEqual(code, 1, out)

    def test_duplicate_state_sequence_id_fails(self):
        code, out, _ = run("state", state30(nodeStates=[node_state("n2", 2), node_state("n2", 2)]))
        self.assertEqual(code, 1, out)

    def test_released_state_after_unreleased_edge_fails(self):
        code, out, _ = run("state", state30(nodeStates=[node_state("n2", 2)],
                                            edgeStates=[edge_state("e1", 1, released=False)]))
        self.assertEqual(code, 1, out)

    def test_driving_without_position_is_warning(self):
        # 6.6.1: a robot that can determine its position "shall publish it"; line-guided robots may not
        msg = state30(driving=True)
        del msg["mobileRobotPosition"]
        code, out, err = run("state", msg)
        self.assertEqual(code, 0, out + err)
        self.assertTrue(any("position" in line for line in lines(out, "warning")), out + err)

    def test_v21_position_name_in_v30_state_is_warned(self):
        msg = state30()
        msg["agvPosition"] = msg.pop("mobileRobotPosition")
        code, out, err = run("state", msg)
        self.assertEqual(code, 0, out + err)
        self.assertTrue(any("agvPosition" in line for line in lines(out, "warning")), out + err)

    def test_valid_v21_state_has_no_findings(self):
        code, out, err = run("state", state21())
        self.assertEqual((code, lines(out, "error"), lines(out, "warning")), (0, [], []), out + err)

    def test_v21_paused_rejected_by_upstream_schema(self):
        # Characterization: the 2.1.0 schema omits PAUSED although the 2.1 text and PDF define it.
        # If this starts passing after a schema refresh, update the conflicts table in SKILL.md.
        msg = state21(actionStates=[{"actionId": "a1", "actionType": "startCharging", "actionStatus": "PAUSED"}])
        code, out, _ = run("state", msg)
        self.assertEqual(code, 1, out)


class VersionsAndInput(unittest.TestCase):
    def test_version_header_selects_schema(self):
        msg = order([node("n1", 0, nodePosition={"x": 0, "y": 0, "mapId": "m", "allowedDeviationXY": 0.5}),
                     node("n2", 2)], [edge("e1", 1, startNodeId="n1", endNodeId="n2")], version="2.1.0")
        self.assertEqual(run("order", msg)[0], 0)
        # the same message checked as 3.0: allowedDeviationXY must be an ellipse object there
        self.assertEqual(run("order", msg, "--spec", "3.0.0")[0], 1)

    def test_unknown_version_asks_for_spec(self):
        msg = order([node("n1", 0)], [])
        del msg["version"]
        code, out, err = run("order", msg)
        self.assertEqual(code, 2, out + err)
        self.assertNotIn("Traceback", err)

    def test_invalid_json_fails_without_traceback(self):
        code, out, err = run("order", "{not json")
        self.assertEqual(code, 1, out + err)
        self.assertNotIn("Traceback", err)

    def test_conditional_zone_fields_are_known(self):
        # releaseLossBehavior is defined only inside an if/then block of the 3.0 zoneSet schema
        msg = {**header(), "zoneSet": {"zoneSetId": "z1", "mapId": "m", "zones": [
            {"zoneId": "a", "zoneType": "RELEASE", "releaseLossBehavior": "STOP",
             "vertices": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]}]}}
        code, out, err = run("zoneSet", msg)
        self.assertEqual((code, lines(out, "warning")), (0, []), out + err)


if __name__ == "__main__":
    unittest.main()
