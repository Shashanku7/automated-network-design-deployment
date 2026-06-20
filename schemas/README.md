# Schemas — Shared JSON Protocol Definitions

JSON Schema (draft-07) files defining the contract between all services in the NetOrch stack.

## Files

| File | Description |
|------|-------------|
| `ws-protocol.json` | WebSocket message format between Frontend ↔ Gateway |
| `agent-task-kafka.json` | Kafka task message format Gateway → AI Service |
| `agent-event-kafka.json` | Kafka event message format AI Service → Gateway |

## WebSocket Protocol (`ws-protocol.json`)

Defines message types exchanged over the frontend-to-gateway WebSocket:

| Message Type | Direction | Description |
|-------------|-----------|-------------|
| `USER_INPUT` | Frontend → Gateway | User prompt / approval decision |
| `AGENT_EVENT` | Gateway → Frontend | Streaming agent progress |
| `TOKEN` | Gateway → Frontend | Streaming LLM token |
| `TOOL_CALL` | Gateway → Frontend | Tool invocation notification |
| `TOOL_RESULT` | Gateway → Frontend | Tool execution result |
| `FINAL_ANSWER` | Gateway → Frontend | Agent completed its phase with final output |
| `APPROVAL_REQ` | Gateway → Frontend | Human-in-the-loop approval request |
| `PHASE_APPROVED` | Gateway → Frontend | Phase was approved, pipeline advances |
| `PHASE_REVISION` | Gateway → Frontend | Phase rejected, agent re-runs with feedback |
| `DIAGRAM_READY` | Gateway → Frontend | Topology diagram rendered and available |
| `DIAGRAM_ERROR` | Gateway → Frontend | Diagram rendering failed |
| `WORKFLOW_COMPLETE` | Gateway → Frontend | Final result and diagram URL |
| `ERROR` | Gateway → Frontend | Error details |

## Kafka Task Protocol (`agent-task-kafka.json`)

Tasks sent from Gateway to AI Service via the `agent-tasks` topic:

- `project_id` — UUID identifying the project
- `phase` — Integer phase number
- `input_context` — Full conversation context
- `history` — Previous message history

## Kafka Event Protocol (`agent-event-kafka.json`)

Streaming events sent from AI Service to Gateway via the `agent-events` topic:

- `TOKEN` — Streaming token from LLM
- `TOOL_CALL` — Agent invoked a tool
- `TOOL_RESULT` — Tool execution result
- `FINAL_ANSWER` — Agent completed its phase
- `PHASE_APPROVED` — User approved a phase
- `ERROR` — Processing error
