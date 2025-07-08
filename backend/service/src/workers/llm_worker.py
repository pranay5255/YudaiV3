from __future__ import annotations

import os
import time

from confluent_kafka import Consumer, Producer
import structlog

from ..utils.llm import generate_patch

logger = structlog.get_logger(__name__)


class LLMWorker:
    def __init__(self) -> None:
        bootstrap = os.getenv("KAFKA_BROKER", "localhost:9092")
        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": "llm-worker",
                "auto.offset.reset": "earliest",
            }
        )
        self.producer = Producer({"bootstrap.servers": bootstrap})
        self.consumer.subscribe(["llm-queue"])

    def run(self) -> None:
        logger.info("LLM worker started")
        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error("kafka error", err=str(msg.error()))
                continue
            code = msg.value().decode()
            try:
                patch = generate_patch(code)
                self.producer.produce("test-queue", patch.encode())
                self.producer.flush()
                self.consumer.commit(msg)
                logger.info("processed llm output")
            except Exception as exc:  # noqa: BLE001
                logger.exception("failed to process llm output", exc=exc)
                time.sleep(1)


def main() -> None:
    worker = LLMWorker()
    worker.run()


if __name__ == "__main__":
    main()
