# Backend Startup Guide

Step-by-step guide to start all backend services for NetOrch.

## Startup Order

1. **PostgreSQL** — Database
2. **Kafka** — Message broker
3. **AI Service** — Multi-agent orchestrator (port 8000)
4. **Image Gen** — Diagram renderer (port 8001)
5. **Topology Gatekeeper** — JSON validator (port 8002)
6. **Gateway** — API gateway (port 8080)

---

## 1. PostgreSQL

```bash
# Start PostgreSQL (adjust for your OS)
sudo systemctl start postgresql   # Linux
# or via Docker:
docker run -d --name pg-netorch \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=root \
  -e POSTGRES_DB=network_design \
  -p 5433:5432 postgres:15

# Create database and schema
createdb -p 5433 network_design
psql -p 5433 -d network_design -f db.sql
```

## 2. Kafka

```bash
docker compose up -d
# Verifies on port 9092
```

## 3. AI Service

```bash
cd ai-service
cp .env.example .env      # fill in QDRANT_URL, OLLAMA_BASE_URL, etc.
uv venv
uv pip install -r requirements.txt   # or use pyproject.toml
uv run uvicorn webapp.app:app --host 0.0.0.0 --port 8000 --reload
```

## 4. Image Generation Service

```bash
cd Image_generation_service
pip install -r requirements.txt
python app.py
# or: uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

## 5. Topology Gatekeeper

```bash
cd topology_generation
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8002 --reload
```

## 6. Gateway

```bash
cd gateway
./mvnw quarkus:dev -Dquarkus.http.port=8080
```

## 7. Frontend (optional)

```bash
cd frontend/code
npm install
npm run dev
```

## Unified Launcher

```bash
./start.sh                  # start all 5 services
./start.sh --no-frontend   # skip frontend
./start.sh --stop          # stop all running services
```

## Logs

| Service | Log File |
|---------|----------|
| Gatekeeper | `tail -f /tmp/gatekeeper.log` |
| AI Service | `tail -f /tmp/ai-service.log` |
| Image Gen | `tail -f /tmp/image-gen.log` |
| Gateway | `tail -f /tmp/gateway.log` |
| Frontend | `tail -f /tmp/frontend.log` |

## Troubleshooting

- **Port conflicts**: Kill existing processes with `lsof -ti :PORT | xargs kill`
- **AI Service won't start**: Verify `.env` is configured and Qdrant/Ollama are reachable
- **Gateway fails**: Ensure PostgreSQL is running on port 5433 and Kafka on 9092
- **Kafka issues**: Run `docker compose down && docker compose up -d` to restart
