import asyncio
from collections.abc import AsyncIterable
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class BatterySupplyAgent:
    """An agent that manages battery supply based on production plans."""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self._battery_inventory = 5000
        self._agent = self._build_agent()
        self._user_id = 'remote_battery_supply_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        return '正在处理电池供应请求...'

    def _build_agent(self) -> LlmAgent:
        """Builds the LLM agent for the battery supply agent."""
        return LlmAgent(
            name="battery_supply_agent",
            model="gemini-1.5-pro",
            description=f"这是一个电池供应商Agent，负责根据生产计划处理电池订单。当前库存{self._battery_inventory}个。",
            instruction=f"""
                你是一个电池供应商，专门处理来自生产计划的下单请求。你的任务是基于用户提供的生产计划，计算电池需求并根据现有库存情况作出回应。

                你的库存是固定的，当前有 {self._battery_inventory} 个电池。

                请严格遵循以下步骤：
                1.  **分析需求**: 从用户输入的生产计划中，准确识别需要生产的车辆数量。
                2.  **计算电池数**: 每辆车需要1个电池，计算出所需的电池总数。
                3.  **核对库存**: 将计算出的电池总数与你的库存 ({self._battery_inventory}个)进行比较。
                4.  **生成响应**:
                    *   **如果库存充足**: 生成一条确认信息，明确说明订单已接受，将提供多少电池。
                    *   **如果库存不足**: 生成一条拒绝信息，明确说明无法满足订单，并指出库存缺口是多少 (需求数量 - 库存数量)。

                **不要编造库存信息，严格使用你被告知的库存数量 ({self._battery_inventory})。**

                示例输入:
                "生产计划：本次需要试生产500辆Cyber-X新能源汽车。..."

                示例输出 (如果库存充足):
                "订单已确认。根据生产计划，500辆车需要500个电池。库存充足，将从现有库存中调拨500个电池用于生产。"

                示例输出 (如果库存不足):
                "订单无法处理。生产500辆车需要500个电池，但当前库存仅有{self._battery_inventory}个。库存缺口为0个。"
            """,
            tools=[],
            output_key="battery_result"
        )

    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict[str, Any]]:
        session = await self._runner.session_service.get_session(
            app_name=self._agent.name,
            user_id=self._user_id,
            session_id=session_id,
        )
        content = types.Content(
            role='user', parts=[types.Part.from_text(text=query)]
        )
        if session is None:
            session = await self._runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                state={},
                session_id=session_id,
            )

        async for event in self._runner.run_async(
            user_id=self._user_id, session_id=session.id, new_message=content
        ):
            if event.is_final_response():
                response = ''
                if event.content and event.content.parts and event.content.parts[0].text:
                    response = '\n'.join(
                        [p.text for p in event.content.parts if p.text]
                    )
                yield {
                    'is_task_complete': True,
                    'content': response,
                }
            else:
                yield {
                    'is_task_complete': False,
                    'updates': self.get_processing_message(),
                }
