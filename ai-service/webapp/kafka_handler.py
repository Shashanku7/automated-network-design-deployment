import json
import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from config import KAFKA_BOOTSTRAP_SERVERS, TOPIC_AGENT_TASKS, TOPIC_AGENT_EVENTS

class KafkaManager:
    def __init__(self):
        self.consumer = None
        self.producer = None

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            TOPIC_AGENT_TASKS,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="ai-service-group",
            value_deserializer=lambda v: json.loads(v.decode("utf-8"))
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
        try:
            async for msg in self.consumer:
                task_data = msg.value
                print(f"KAFKA_RECV task_id={task_data.get('task_id')} project_id={task_data.get('project_id')} phase={task_data.get('phase')}", flush=True)
                print(f"KAFKA_RECV input_context={'null' if task_data.get('input_context') is None else ('notNull len=' + str(len(str(task_data.get('input_context', '')))))}", flush=True)
                history = task_data.get('history', [])
                print(f"KAFKA_RECV history_len={len(history)}", flush=True)
                print(f"KAFKA_RECV task_data_keys={list(task_data.keys())}", flush=True)
                # Schedule task processing
                asyncio.create_task(process_fn(task_data))
        except Exception as e:
            print(f"Error in Kafka consume loop: {e}")
