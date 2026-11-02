---
name: vda5050-spec
description: Use when a question, design, code change or JSON message involves VDA 5050 / VDA5050 (AGV, AMR, mobile robot <-> fleet control over MQTT) - field names, enums, topics, QoS, order/orderUpdate/stitching, cancelOrder, actions, blockingType, actionStatus, errorType, operatingMode, connection, factsheet, visualization, zoneSet, responses, 2.x vs 3.0 differences, or validating a message against the official schema. Use even for a one-word field lookup.
---

# VDA 5050 (official sources bundled)

Everything here comes from github.com/VDA5050/VDA5050:
- 3.0.0 = `main` @ `0b2ae43`: tag `3.0.0` (2026-03-18) plus 28 commits, 17 without merges (alignment with the
  published text, schema syntax fixes, schema field-name fixes such as zoneSet
  `directedLimitation`/`bidirectedLimitation`, factsheet `mobileRobotKinematics`, boolean
  `cancelAllowed`/`pauseAllowed`). Table numbers follow `main` (Table 9 = predefined error types).
- 2.1.0 = tag `2.1.0` @ `511d01d` (2024-08-19), same content as branch `release/2.1.0`.

If GitHub and the VDA PDF disagree, the PDF on vda.de is binding (upstream README).
Checked against the PDFs on 2026-10-14 (not bundled, VDA copyright):
- 3.0.0 "Version 3.0.0, March 2026", 103 pages, sha256 `becf70e4...`:
  https://www.vda.de/dam/jcr:09f03b91-13e2-4db3-bf30-4f221710071b/VDA5050-V3.0.0-2025-03.pdf
- 2.1.0 "Version 2.1.0, January 2025", 68 pages, sha256 `e6910ac1...`:
  https://vda.de/dam/jcr:f0c9c019-1506-4dee-998a-e92723fbf025/VDA5050-V2p1p0.pdf
- Result: the bundled markdown has the same field names and enum values as the PDFs; other
  differences are layout and wording only. Where the schema differs, see the conflicts section.

## Rule: answer from the files, not from memory

Memory mixes 2.x and 3.0 names and is wrong on most 3.0 details. Before stating any field name,
enum value, error type or rule:

1. Fix the version. Message header `version`, topic prefix `.../v2/...` or `.../v3/...`, or ask.
2. Look it up in the matching file and cite the section number.
3. If the text and the schema disagree, say so and give the PDF verdict (see "Text vs schema conflicts").

Resolve `SK` to the directory containing this SKILL.md in the installed plugin; do not use the current project's working directory.

```bash
SK="<absolute path to this skill directory>"
grep -n -E '^#{2,4} [0-9]' $SK/spec/VDA5050_EN-3.0.0.md      # section map
grep -n 'minimumStateInterval' $SK/spec/VDA5050_EN-3.0.0.md $SK/schemas/3.0.0/*.json
```

| Need | 3.0.0 (`spec/VDA5050_EN-3.0.0.md`) |
|---|---|
| QoS, topic levels, topic list | 4.1, 4.2, 4.3 |
| Order concept, base/horizon, update, stitching, acceptance flow (Figure 8) | 6.1.1, 6.1.2 |
| cancelOrder, next order after cancel | 6.1.3 |
| Rejection cases | 6.1.4.x |
| Blocking types, predefined actions table, action state transitions | 6.2.2, 6.2.3 |
| Maps / zones / zone requests | 6.3, 6.4 |
| Connection, last will, retained | 6.5 |
| State triggers, traversal, ellipse deviation | 6.6.1, 6.6.2 |
| Error levels, predefined error types (Table 9) | 6.6.5 |
| Operating modes (Table 10, 11), clearing order, idle | 6.6.6 - 6.6.8 |
| Request/response | 6.9 |
| Field tables per message | 7.2 - 7.x |

Predefined actions table (6.2.3.1) scope columns, in order: instant, node, edge, zone.

2.1.0 (`spec/VDA5050_EN-2.1.0.md`) uses other numbering: QoS 6.2, topics 6.5, order 6.6,
cancel without order 6.6.3.2, order rejection 6.6.4.x, predefined actions 6.8.1 (columns
instant, node, edge; no zone), instantActions 6.9, state 6.10, action states 6.11, factsheet 6.15,
error reference 7.1.

## 3.0 facts memory gets wrong (verified)

- QoS 0 for `order`, `instantActions`, `state`, `factsheet`, `zoneSet`, `responses`, `visualization`;
  QoS 1 only for `connection`. Retained: `connection`, `factsheet`. (4.1, 6.5, 6.10)
- Factsheet timing: `protocolLimits.timing.minimumStateInterval` / `minimumOrderInterval`
  (2.1: `minStateInterval` / `minOrderInterval`).
- `safetyState.activeEmergencyStop`: `MANUAL` | `REMOTE` | `NONE`. No AUTOACK in 3.0.
- `nodePosition.allowedDeviationXY` is an object `{a, b, theta}` (ellipse). 2.1: number.
- `mobileRobotPosition`: x, y, theta, mapId, localized, localizationScore, deviationRange.
  No `mapDescription`, no `positionInitialized`.
- INTERVENED: orders and order updates allowed (executed after return), instant actions only `cancelOrder`.
- Same `orderId` + same `orderUpdateId`: identical content ignored; different content ->
  `SAME_ORDER_UPDATE_ID` (WARNING). Lower `orderUpdateId` -> `OUTDATED_ORDER_UPDATE`.
- Order received in MANUAL/SERVICE/TEACH_IN/STARTUP -> `MOBILE_ROBOT_NOT_AVAILABLE` (WARNING),
  reported until the operating mode allows orders again.
- `errorType` is an extensible enum (7.8): vendor values are allowed, only Table 9 values are
  predefined. The schema has no enum for it.
- Edges have no `startNodeId` / `endNodeId`. The edge with `sequenceId` n connects the nodes
  n-1 and n+1 (6.1.1).
- Instant actions: `blockingType` must be `NONE` (6.2.1).
- Order actions add only `retriable` (instant actions add nothing). `cancelAllowed` /
  `pauseAllowed` are factsheet fields (`protocolFeatures.mobileRobotActions[]`), not action fields.
- Corridor `releaseLossBehavior`: `STOP` | `RETURN`. Zone `releaseLossBehavior`: `STOP` | `CONTINUE` | `EVACUATE`.

## 2.1 -> 3.0 differences

Full field-level list: `schema-diff-2.1.0-to-3.0.0.txt` (`-` only in 2.1, `+` only in 3.0, enums
inline, `$ref`/`allOf`/`if-then` resolved). Main patterns:

| 2.1 | 3.0 |
|---|---|
| `agvPosition` (`positionInitialized`, `mapDescription`), `batteryState` (`batteryCharge`, `reach`) | `mobileRobotPosition` (`localized`, no `mapDescription`), `powerSupply` (`stateOfCharge`, `range`, new `batteryCurrent`) |
| `actionDescription`, `nodeDescription`, `edgeDescription`, `maps[].mapDescription`, `infoDescription` | `actionDescriptor`, `nodeDescriptor`, `edgeDescriptor`, `mapDescriptor`, `infoDescriptor`. Unchanged: `errorDescription`, factsheet `mobileRobotActions[].actionDescription`. New: `orderDescription` |
| `resultDescription` (state, factsheet) | `actionResult` |
| edge `maxSpeed`, `maxHeight`, `minHeight`, `maxRotationSpeed`, `rotationAllowed` | `maximumSpeed`, `maximumMobileRobotHeight`, `minimumLoadHandlingDeviceHeight`, `maximumRotationSpeed` (PDF and text; the 3.0 schema still says `maxRotationSpeed`, so schema-diff misses it); `rotationAllowed` removed; new `reachOrientationBeforeEntering` |
| `nodePosition.allowedDeviationXY` number, `nodePosition.mapDescription` | ellipse object `{a, b, theta}`; `mapDescription` removed |
| factsheet `agvGeometry` (`envelopes2d[].set`, `polygonPoints`), `vehicleConfig`, `agvActions`, `agvClass`, `agvKinematic` | `mobileRobotGeometry` (`envelope2dId`, `vertices`), `mobileRobotConfiguration`, `mobileRobotActions`, `mobileRobotClass`, `mobileRobotKinematics` |
| factsheet limits `speedMax`, `heightMin`, `maxLoadMass`, `agvSpeedLimit`, `maxArrayLens`, `maxStringLens` | `maximumSpeed`, `minimumHeight`, `maximumLoadMass`, `maximumSpeed`, `maximumArrayLengths`, `maximumStringLengths`; `enumLen` dropped |
| factsheet values `DIFF` / `OMNI` / `THREEWHEEL`, navigationTypes `AUTONOMOUS`, valueDataType `FLOAT` | `DIFFERENTIAL` / `OMNIDIRECTIONAL` / `THREE_WHEEL`, `FREELY_NAVIGATING`, `FLOAT` removed |
| corridor `corridorRefPoint`: `KINEMATICCENTER` | `corridorReferencePoint`: `KINEMATIC_CENTER`; new `releaseRequired`, `releaseLossBehavior` |
| action `initPosition` | `initializePosition` (instant, node for elevators, in both versions) |
| `CONNECTIONBROKEN` | `CONNECTION_BROKEN`, plus `HIBERNATING` |
| `operatingMode` `TEACHIN` | `TEACH_IN`, plus `INTERVENED`, `STARTUP` |
| `errorLevel` `WARNING` / `FATAL` | `WARNING` / `URGENT` / `CRITICAL` / `FATAL` |
| actionStatus without `RETRIABLE`; blockingType without `SINGLE` | `RETRIABLE`, `SINGLE` added |
| order/state `zoneSetId` | removed; zone sets come via `zoneSet` topic or `downloadZoneSet`, then `enableZoneSet` (6.4.2) |

Behavior differences:
- Error types: 2.1 `errorType` is free text; the text names `validationError`, `orderError`,
  `orderUpdateError` (6.6.4.x), `noOrderToCancel` (6.6.3.2). 3.0 uses the UPPER_SNAKE list in Table 9.
  Do not send 3.0 names to a 2.1 integration.
- 2.1 duplicate order (same id + update id) is ignored; `SAME_ORDER_UPDATE_ID` does not exist.
- 2.1 has no `instantActionStates` (instant action states live in `actionStates`).
- Already in 2.1, not new in 3.0: `errorHint`, `maps` in state, `enableMap` / `downloadMap` /
  `deleteMap`, edge `corridor`, factsheet.
- New 3.0 actions: `trigger`, `retry`, `skipRetry`, `clearInstantActions`, `clearZoneActions`,
  `startHibernation`, `stopHibernation`, `shutdown`, `updateCertificate`, `downloadZoneSet`,
  `enableZoneSet`, `deleteZoneSet`. 3.0 adds `errorDescriptionTranslations` / `errorHintTranslations`.

## Text vs schema conflicts and other upstream issues

Name the conflict in the answer, give the PDF verdict, and mention the interoperability risk
(code generated from the schema uses the schema name).

| Conflict | PDF verdict |
|---|---|
| 3.0 edge rotation speed: schema `maxRotationSpeed`, text 7.3 `maximumRotationSpeed` | PDF p.73: `maximumRotationSpeed`. The schema is wrong. Ask which name the robot reads. `validate.py` warns on `maximumRotationSpeed` (not in schema) |
| 3.0 7.8 `errorType` enum lists `INVALID_ORDER`; Table 9 defines `INVALID_ORDER_ACTION` | The PDF has both (p.89 vs Table 9 p.56 and 6.1.4.3 p.21). Use `INVALID_ORDER_ACTION` |
| 3.0 7.8 `actionStates` row says `resultDescription` | Same leftover in PDF p.80. The field is `actionResult` (p.88, schema) |
| 2.1 schema `actionStatus` enum lacks `PAUSED` | PDF p.50 defines `PAUSED`. The schema is wrong; `validate.py` reports a valid 2.1 `PAUSED` as a schema error |
| 2.1 factsheet `angularSpeedMin` / `angularSpeedMax` missing in schema | PDF p.59 defines both. The schema is incomplete |
| 2.1 edge `startNodeId` / `endNodeId` described as first / last node "within the order" | Same wording in PDF p.26. The same table defines an edge as "Directional connection between two nodes", so use the schema meaning (the edge's start / end node) |

Unreleased branch `dev/3.0.1` (@ `4437fb3`, 2026-09-28) already fixes the three 3.0 rows the
PDF way. It also has changes that are not in the 3.0.0 PDF (e.g. new error type
`ORIENTATION_UNREACHABLE`, `RELEASE_LOST` split into `ZONE_RELEASE_LOST` / `CORRIDOR_RELEASE_LOST`). Do not answer
3.0.0 questions from that branch.

Other upstream issues:
- Tag `3.0.0` schemas for order, factsheet, visualization have trailing commas (invalid JSON).
- 3.0 messages captured from real robots (navifra examples) still carry 2.x names
  (edge `startNodeId` / `endNodeId`, `maps[].mapDescription`).
- Third-party skill `navifra-sally/vda5050-skill` 0.3.1: 3.0 core rules and schemas are right.
  Wrong: 2.x error names, `minimumStateInterval` as a 2.1 field, `mapDescription` in 3.0,
  `errorHint` / map actions / corridor / node-scope position reset as new in 3.0,
  `cancelAllowed` / `pauseAllowed` on order actions, `KINEMATICCENTER` in 3.0. Missing:
  `TEACHIN`, `*Descriptor`, `initPosition` renames. Its validator fails valid 3.0 orders without
  `startNodeId` / `endNodeId`. The `validate.py` here is an independent implementation.

## Tools

```bash
pip install jsonschema
python3 $SK/scripts/validate.py order msg.json             # version from "version" header
python3 $SK/scripts/validate.py state msg.json --spec 2.1.0
python3 $SK/scripts/schema_diff.py 2.1.0 3.0.0             # regenerate field diff
```

`validate.py` prints one `error:` or `warning:` line per finding, then `OK` or `FAIL`.
Exit code 0 means no errors, 1 means errors, 2 means the message could not be checked (unknown
version, missing schema for the topic, unreadable file). Errors are schema violations and the
spec rules a schema cannot express, each tagged with its section: order 6.1.1 (at least one
node, edges = nodes - 1, continuous numbering with even nodes and odd edges, new order starts at
0, first node released, released edge needs released nodes, nothing released after an
unreleased edge), 7.3 (unique `actionId`), 2.x edge `startNodeId` / `endNodeId`; state 6.6.1
(only upcoming nodes and edges, same numbering and release rules). Warnings do not fail the run.
They include every field the schema does not define. The schemas allow extra fields (chapter 4:
"future extensions ... with additional parameters"), so read these warnings: a 2.x name in a
3.0 message shows up only there.

## Refresh when upstream changes

Clone github.com/VDA5050/VDA5050, copy `VDA5050_EN.md` and `json_schemas/*.schema` into `spec/` and
`schemas/<version>/`, check every schema parses, rerun `schema_diff.py` into
`schema-diff-2.1.0-to-3.0.0.txt`, recheck the conflicts list, update commit ids above.
