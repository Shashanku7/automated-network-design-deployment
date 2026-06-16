import json
import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from config import KAFKA_BOOTSTRAP_SERVERS, TOPIC_AGENT_TASKS, TOPIC_AGENT_EVENTS

class KafkaProvider:
    def __init__(self):
        self.consumer = None
        self.producer = None
        self._stop_event = asyncio.Event()

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            TOPIC_AGENT_TASKS,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="ai-service-group",
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        try:
            await self.consumer.start()
            await self.producer.start()
            print("Kafka successfully connected.")
        except Exception as e:
            print(f"Warning: Failed to connect to Kafka at {KAFKA_BOOTSTRAP_SERVERS}. Ensure Kafka is running if you need event streaming. ({e})")
            self.consumer = None
            self.producer = None

    async def stop(self):
        self._stop_event.set()
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

    async def send_event(self, event_data: dict):
        if self.producer:
            await self.producer.send_and_wait(TOPIC_AGENT_EVENTS, event_data)

    async def listen_tasks(self, callback):
        if not self.consumer:
            return
        try:
            async for msg in self.consumer:
                if self._stop_event.is_set():
                    break
                await callback(msg.value)
        finally:
            await self.stop()

kafka_provider = KafkaProvider()
