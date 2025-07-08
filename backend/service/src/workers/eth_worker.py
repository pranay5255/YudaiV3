from __future__ import annotations

import os
import time

from confluent_kafka import Consumer
import structlog

from ..utils.eth import EthereumClient

logger = structlog.get_logger(__name__)


class EthWorker:
    def __init__(self) -> None:
        bootstrap = os.getenv("KAFKA_BROKER", "localhost:9092")
        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": "eth-worker",
                "auto.offset.reset": "earliest",
            }
        )
        self.consumer.subscribe(["eth-queue"])
        self.client = EthereumClient()

    def run(self) -> None:
        logger.info("eth worker started")
        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error("kafka error", err=str(msg.error()))
                continue
            data = msg.value().decode()
            try:
                tx_hash = self.client.submit_patch(data, "")
                logger.info("submitted patch", tx_hash=tx_hash)
                self.consumer.commit(msg)
            except Exception as exc:  # noqa: BLE001
                logger.exception("failed to submit patch", exc=exc)
                time.sleep(1)


def main() -> None:
    worker = EthWorker()
    worker.run()


if __name__ == "__main__":
    main()
