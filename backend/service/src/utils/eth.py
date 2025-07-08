from __future__ import annotations

import os
from typing import Any, Dict

from web3 import Web3
import structlog

logger = structlog.get_logger(__name__)


class EthereumClient:
    def __init__(self) -> None:
        provider = Web3.HTTPProvider(os.getenv("WEB3_PROVIDER_URI", "http://localhost:8545"))
        self.web3 = Web3(provider)
        self.address = Web3.to_checksum_address(os.getenv("CONTRACT_ADDRESS", "0x0"))
        abi_env = os.getenv("CONTRACT_ABI", "[]")
        abi: list[dict[str, Any]] = []
        if abi_env:
            try:
                import json

                abi = json.loads(abi_env)
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed to load ABI", exc=exc)
        self.contract = self.web3.eth.contract(address=self.address, abi=abi)

    def submit_patch(self, patch: str, test_result: str) -> str:
        logger.info("submitting patch to ethereum")
        try:
            tx = self.contract.functions.submitPatch(patch, test_result).transact()
            receipt = self.web3.eth.wait_for_transaction_receipt(tx)
            logger.debug("transaction mined", tx_hash=receipt.transactionHash.hex())
            return receipt.transactionHash.hex()
        except Exception as exc:  # noqa: BLE001
            logger.exception("failed to submit patch", exc=exc)
            return ""

    def get_patch(self, patch_id: int) -> Dict[str, Any]:
        logger.info("getting patch", patch_id=patch_id)
        try:
            return self.contract.functions.getPatch(patch_id).call()
        except Exception as exc:  # noqa: BLE001
            logger.exception("get patch failed", exc=exc)
            return {}
