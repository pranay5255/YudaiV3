from __future__ import annotations

import os
import time

from confluent_kafka import Consumer, Producer
import structlog
from ..utils.swe_agent import apply_patch_with_agent

from ..utils.testing import run_tests

logger = structlog.get_logger(__name__)


class TestWorker:
    def __init__(self) -> None:
        bootstrap = os.getenv("KAFKA_BROKER", "localhost:9092")
        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": "test-worker",
                "auto.offset.reset": "earliest",
            }
        )
        self.producer = Producer({"bootstrap.servers": bootstrap})
        self.consumer.subscribe(["test-queue"])

    def run(self) -> None:
        logger.info("test worker started")
        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error("kafka error", err=str(msg.error()))
                continue
            patch = msg.value().decode()
            patched = apply_patch_with_agent(patch)
            try:
                result = run_tests(patched)
                self.producer.produce("eth-queue", result.encode())
                self.producer.flush()
                self.consumer.commit(msg)
                logger.info("processed tests")
            except Exception as exc:  # noqa: BLE001
                logger.exception("failed to run tests", exc=exc)
                time.sleep(1)


def main() -> None:
    worker = TestWorker()
    worker.run()


if __name__ == "__main__":
    main()
