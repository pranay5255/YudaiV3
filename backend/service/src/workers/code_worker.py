from __future__ import annotations

import os
import time

from confluent_kafka import Consumer, Producer
import structlog
from ..utils.swe_agent import run_agent_command

from ..utils.code_exec import run_code

logger = structlog.get_logger(__name__)


class CodeWorker:
    def __init__(self) -> None:
        bootstrap = os.getenv("KAFKA_BROKER", "localhost:9092")
        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": "code-worker",
                "auto.offset.reset": "earliest",
            }
        )
        self.producer = Producer({"bootstrap.servers": bootstrap})
        self.consumer.subscribe(["code-queue"])

    def run(self) -> None:
        logger.info("code worker started")
        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error("kafka error", err=str(msg.error()))
                continue
            code = msg.value().decode()
            try:
                output = run_code(code)
                run_agent_command(["run"])
                self.producer.produce("llm-queue", output.encode())
                self.producer.flush()
                self.consumer.commit(msg)
                logger.info("processed code")
            except Exception as exc:  # noqa: BLE001
                logger.exception("failed to process code", exc=exc)
                time.sleep(1)


def main() -> None:
    worker = CodeWorker()
    worker.run()


if __name__ == "__main__":
    main()
