import asyncio
import json
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from config import KAFKA_BOOTSTRAP_SERVERS, TOPIC_AGENT_TASKS, TOPIC_AGENT_EVENTS


class KafkaHistoryItem(BaseModel):
    role: str
    content: str
    timestamp: str | None = None


class KafkaTaskPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    project_id: str
    task_id: str
    phase: int = Field(ge=1)
    input_context: str
    history: list[KafkaHistoryItem] = Field(default_factory=list)
    agent_target: str | None = None


def _validate_task_payload(task_data: Any) -> KafkaTaskPayload:
    if hasattr(KafkaTaskPayload, "model_validate"):
        return KafkaTaskPayload.model_validate(task_data)
    return KafkaTaskPayload.parse_obj(task_data)

class KafkaManager:
    def __init__(self):
        self.consumer = None
        self.producer = None
        self.max_task_retries = 3
        self.failed_attempts: dict[tuple[str, str, int], int] = {}
        self.completed_tasks: set[tuple[str, str, int]] = set()

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            TOPIC_AGENT_TASKS,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="ai-service-group",
            enable_auto_commit=False,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )
        await self.consumer.start()
        await self.producer.start()

    async def stop(self):
        await self.consumer.stop()
        await self.producer.stop()

    async def send_event(self, event_data: dict):
        print(f"KAFKA_SEND event_type={event_data.get('event_type')} task_id={event_data.get('task_id')} project_id={event_data.get('project_id')} data_preview={str(event_data.get('data', ''))[:100]}", flush=True)
        await self.producer.send_and_wait(TOPIC_AGENT_EVENTS, event_data)

    async def consume_tasks(self, process_fn):
        while True:
            try:
                async for msg in self.consumer:
                    raw_task = msg.value
                    print(
                        f"KAFKA_RECV topic={msg.topic} partition={msg.partition} offset={msg.offset}",
                        flush=True,
                    )
                    try:
                        task = _validate_task_payload(raw_task)
                        task_data = task.model_dump() if hasattr(task, "model_dump") else task.dict()
                    except ValidationError as validation_error:
                        project_id = raw_task.get("project_id") if isinstance(raw_task, dict) else None
                        task_id = raw_task.get("task_id") if isinstance(raw_task, dict) else None
                        print(
                            f"KAFKA_RECV invalid_payload partition={msg.partition} offset={msg.offset} "
                            f"project_id={project_id} task_id={task_id} error={validation_error}",
                            flush=True,
                        )
                        if project_id and task_id:
                            try:
                                await self.send_event(
                                    {
                                        "project_id": project_id,
                                        "task_id": task_id,
                                        "agent_name": "system",
                                        "event_type": "ERROR",
                                        "data": "Invalid Kafka task payload",
                                        "payload": {"validation_error": str(validation_error)},
                                        "is_final": True,
                                    }
                                )
                            except Exception as send_error:
                                print(
                                    f"KAFKA_SEND failed_invalid_payload_event partition={msg.partition} "
                                    f"offset={msg.offset} error={send_error}",
                                    flush=True,
                                )
                        await self.consumer.commit()
                        continue

                    print(
                        f"KAFKA_RECV task_id={task_data['task_id']} project_id={task_data['project_id']} "
                        f"phase={task_data['phase']} history_len={len(task_data['history'])}",
                        flush=True,
                    )
                    print(
                        "KAFKA_RECV input_context="
                        + (
                            "null"
                            if task_data["input_context"] is None
                            else "notNull len=" + str(len(str(task_data["input_context"])))
                        ),
                        flush=True,
                    )
                    task_key = (
                        str(task_data["project_id"]),
                        str(task_data["task_id"]),
                        int(task_data["phase"]),
                    )
                    if task_key in self.completed_tasks:
                        print(
                            f"KAFKA_SKIP duplicate_completed task_id={task_data['task_id']} phase={task_data['phase']}",
                            flush=True,
                        )
                        await self.consumer.commit()
                        continue
                    try:
                        await process_fn(task_data)
                        self.completed_tasks.add(task_key)
                        self.failed_attempts.pop(task_key, None)
                        await self.consumer.commit()
                        print(
                            f"KAFKA_COMMIT success partition={msg.partition} offset={msg.offset} "
                            f"task_id={task_data['task_id']}",
                            flush=True,
                        )
                    except Exception as process_error:
                        attempts = self.failed_attempts.get(task_key, 0) + 1
                        self.failed_attempts[task_key] = attempts
                        print(
                            f"KAFKA_PROCESS fail partition={msg.partition} offset={msg.offset} "
                            f"task_id={task_data['task_id']} attempt={attempts} error={process_error}",
                            flush=True,
                        )
                        if attempts >= self.max_task_retries:
                            try:
                                await self.send_event(
                                    {
                                        "project_id": task_data["project_id"],
                                        "task_id": task_data["task_id"],
                                        "agent_name": "system",
                                        "event_type": "ERROR",
                                        "data": "Task retries exhausted in ai-service consumer",
                                        "payload": {
                                            "phase": task_data["phase"],
                                            "attempts": attempts,
                                            "reason": str(process_error),
                                        },
                                        "is_final": True,
                                    }
                                )
                            except Exception as send_error:
                                print(
                                    f"KAFKA_SEND retries_exhausted_event_failed task_id={task_data['task_id']} "
                                    f"error={send_error}",
                                    flush=True,
                                )
                            await self.consumer.commit()
                            self.failed_attempts.pop(task_key, None)
                            print(
                                f"KAFKA_COMMIT retries_exhausted partition={msg.partition} offset={msg.offset} "
                                f"task_id={task_data['task_id']}",
                                flush=True,
                            )
                            continue
                        # Keep offset uncommitted so the message can be retried.
                        continue
            except asyncio.CancelledError:
                raise
            except Exception as loop_error:
                print(f"KAFKA_LOOP error={loop_error}; restarting consume loop in 1s", flush=True)
                await asyncio.sleep(1)
