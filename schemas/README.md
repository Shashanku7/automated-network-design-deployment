# Schemas — Shared JSON Protocol Definitions

JSON Schema (draft-07) files defining the contract between all services in the NetOrch stack.

## Files

| File | Description |
|------|-------------|
| `ws-protocol.json` | WebSocket message format between Frontend ↔ Gateway |
| `agent-task-kafka.json` | Kafka task message format Gateway → AI Service |
| `agent-event-kafka.json` | Kafka event message format AI Service → Gateway |

## WebSocket Protocol (`ws-protocol.json`)

Defines message types exchanged over the frontend-to-gateway WebSocket. The JSON schema defines a `type` enum with these values:

| Type | Direction | Description |
|------|-----------|-------------|
| `USER_INPUT` | Frontend → Gateway | User prompt / approval decision |
| `AGENT_EVENT` | Gateway → Frontend | Streaming agent progress |
| `APPROVAL_REQ` | Gateway → Frontend | Human-in-the-loop approval request |
| `APPROVAL_RES` | Frontend → Gateway | User approval/revision response |
| `PHASE_APPROVED` | Gateway → Frontend | Phase was approved, pipeline advances |
| `ERROR` | Gateway → Frontend | Error details |

Additional properties: `project_id` (required), `task_id`, `agent_name`, `event_type` (enum: `chunk`, `tool_call`, `tool_result`, `result`), `content`, `approved`, `feedback`, `payload`, `timestamp`.

## Kafka Task Protocol (`agent-task-kafka.json`)

Tasks sent from Gateway to AI Service via the `agent-tasks` topic:

- `project_id` — UUID identifying the project
- `task_id` — UUID for idempotent task processing
- `phase` — Integer phase number (1–5)
- `input_context` — Full conversation context
- `history` — Previous message history
- `agent_target` — (Optional) Specific agent name override

## Kafka Event Protocol (`agent-event-kafka.json`)

Streaming events sent from AI Service to Gateway via the `agent-events` topic:

- `TOKEN` — Streaming token from LLM
- `TOOL_CALL` — Agent invoked a tool
- `TOOL_RESULT` — Tool execution result
- `FINAL_ANSWER` — Agent completed its phase
- `DIAGRAM_READY` — Topology diagram rendered and available
- `DIAGRAM_ERROR` — Diagram rendering failed
- `APPROVAL_REQUIRED` — HITL approval needed (includes `task_id` and `phase`)
- `ERROR` — Processing error
