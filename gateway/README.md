# Gateway — API Gateway & Orchestrator

Java/Quarkus service that bridges frontend WebSocket connections to the AI service via Kafka. Manages conversations, agent tasks, and event streaming.

**Port:** 8080

## Architecture

```
Frontend (WS) ←──→ Gateway :8080 ←──Kafka──→ AI Service :8000
                       │
                       └── PostgreSQL :5433
```

## Responsibilities

- **WebSocket server** — Accepts frontend connections, routes messages to Kafka
- **Kafka producer** — Sends `agent-tasks` to AI Service
- **Kafka consumer** — Receives `agent-events` from AI Service, forwards to frontend
- **REST proxy** — Proxies `/api/chat` to AI Service (`http://localhost:8000`)
- **Persistence** — Stores conversations, messages, tasks, events in PostgreSQL

## Kafka Topics

| Topic | Direction | Content |
|-------|-----------|---------|
| `agent-tasks` | Gateway → AI | Task requests (project_id, phase, input) |
| `agent-events` | AI → Gateway | Streaming events (token, tool_call, result, final) |

## PostgreSQL Entities

| Table | Purpose |
|-------|---------|
| `conversations` | Chat threads per project |
| `messages` | Individual chat messages (role, content) |
| `agent_tasks` | Orchestration task records |
| `agent_events` | Persisted Kafka events for replay/debug |
| `tool_calls` | Tool execution audit log |

Schema defined in [`../db.sql`](../db.sql). Hibernate auto-creates tables on startup.

## Setup

```bash
# Prerequisites
# - Java 25+
# - PostgreSQL on localhost:5433 (database: network_design)
# - Kafka on localhost:9092

cd gateway
./mvnw quarkus:dev
```

## Configuration

`src/main/resources/application.properties`:

| Property | Default | Description |
|----------|---------|-------------|
| `kafka.bootstrap.servers` | `localhost:9092` | Kafka broker |
| `quarkus.datasource.jdbc.url` | `jdbc:postgresql://localhost:5433/network_design` | PostgreSQL |
| `quarkus.datasource.username` | `postgres` | DB user |
| `quarkus.datasource.password` | `root` | DB password |
| `rest-client.ai-service.url` | `http://localhost:8000` | AI Service REST endpoint |

## Building

```bash
./mvnw package                          # quarkus-run.jar
./mvnw package -Dquarkus.package.jar.type=uber-jar  # fat JAR
./mvnw package -Dnative                 # native binary (needs GraalVM)
```
