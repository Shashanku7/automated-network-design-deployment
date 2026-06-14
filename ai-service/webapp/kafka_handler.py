import json
import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from config import KAFKA_BOOTSTRAP_SERVERS, TOPIC_AGENT_TASKS, TOPIC_AGENT_EVENTS

class KafkaManager:
    def __init__(self):
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

    async def start(self):
        await self.consumer.start()
        await self.producer.start()

    async def stop(self):
        await self.consumer.stop()
        await self.producer.stop()

    async def send_event(self, event_data: dict):
        await self.producer.send_and_wait(TOPIC_AGENT_EVENTS, event_data)

    async def consume_tasks(self, process_fn):
        try:
            async for msg in self.consumer:
                task_data = msg.value
                print(f"Received task: {task_data.get('task_id')}")
                # Schedule task processing
                asyncio.create_task(process_fn(task_data))
        except Exception as e:
            print(f"Error in Kafka consume loop: {e}")
