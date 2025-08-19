import asyncio
import uuid
from collections.abc import AsyncIterable
from typing import Any

import httpx


class BatteryTradeAgent:
    """An agent that executes a trade for batteries."""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        """Initializes the BatteryTradeAgent."""
        pass

    def get_processing_message(self) -> str:
        return '正在处理电池交易...'

    async def _execute_trade(self) -> str:
        """Executes a simulated blockchain transaction."""
        transaction_id = str(uuid.uuid4())
        payload = {
            "senderAddress": "did:bid:efUGVkkJ746m4iCKgSpECXcni4v1cUaQ",
            "privateKey": "priSPKrcQaSLzFtwUHuzDuxAR9pxqXS1CbT4Vpc8aSbpCLtjt1",
            "destAddress": "did:bid:ef25XsX1QLoaTB459SpucsM8i4baHPnAE",
            "amount": 0.08, 
            "remarks": "",
            "gasPrice": 100,
            "feeLimit": 100000000,
            "nonceType": 0
        }
        receipt_text = ""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://43.162.109.76:18080/chainagent/chain/transfer", json=payload
                )
                response.raise_for_status()
                data = response.json()

            if data.get("code") == 0:
                trade_data = data.get("data", {})
                receipt_text = (
                    f"--- 交易凭证 ---\n"
                    f"Hash: {trade_data.get('hash')}\n"
                    f"发送方: {trade_data.get('senderAddress')}\n"
                    f"接收方: {trade_data.get('destAddress')}"
                )
            else:
                error_message = data.get("message", "未知错误")
                receipt_text = f"--- 交易失败 ---\n原因: {error_message}"
        except httpx.RequestError as e:
            receipt_text = f"--- 交易API调用失败 ---\n错误: {e}"
        except Exception as e:
            receipt_text = f"--- 交易处理时发生未知错误 ---\n错误: {e}"

        return receipt_text

    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict[str, Any]]:
        yield {
            'is_task_complete': False,
            'updates': self.get_processing_message(),
        }
        
        receipt = await self._execute_trade()
        
        yield {
            'is_task_complete': True,
            'content': f"{receipt}\n\n是否确认采购？",
        }
