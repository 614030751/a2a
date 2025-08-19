import asyncio
from collections.abc import AsyncIterable
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class FrameSupplyAgent:
    """An agent that manages frame supply based on production plans."""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self._frame_inventory = 10000 
        self._agent = self._build_agent()
        self._user_id = 'remote_frame_supply_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        return '正在处理车架供应请求...'

    def _build_agent(self) -> LlmAgent:
        """Builds the LLM agent for the frame supply agent."""
        return LlmAgent(
            name="frame_supply_agent",
            model="gemini-1.5-pro",
            description=f"车架供应商Agent，负责车架的生产、质检和出库配送。当前库存: {self._frame_inventory}个。",
            instruction=f"""
                你是一个车架供应商，专门处理车架的订单请求。你的库存是固定的，当前有 {self._frame_inventory} 个车架。

                请严格遵循以下步骤：
                1.  **分析需求**: 从用户输入的生产计划中，准确识别需要生产的车辆数量。
                2.  **计算车架需求**: 每辆车需要1个车架，计算出所需的车架总数。
                3.  **核对库存**: 将计算出的需求总数与你的库存 ({self._frame_inventory}个)进行比较。
                4.  **生成响应**:
                    *   **如果库存充足**: 生成确认信息，说明将提供多少个车架，并描述后续的生产、质检和包装流程。
                    *   **如果库存不足**: 生成拒绝信息，明确指出无法满足订单，并说明库存缺口。

                输出格式必须包含以下几点：
                - 订单确认状态
                - 生产状态（例如：正在生产/库存现货）
                - 质检结果（例如：所有车架通过强度测试）
                - 预计交付时间

                示例输入:
                "生产计划：本次需要生产500辆Cyber-X新能源汽车。..."

                示例输出 (如果库存充足):
                "订单确认：已接受500个车架的订单。
                生产状态：库存现货。
                质检结果：所有车架均通过强度测试和表面处理。
                预计交付：将在3天内完成包装和出库。"
            """,
            tools=[],
            output_key="frame_result"
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
