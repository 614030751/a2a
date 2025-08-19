import asyncio
from collections.abc import AsyncIterable
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class FrameTransportAgent:
    """An agent that arranges transport for car frames."""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = 'remote_frame_transport_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        return '正在规划车架运输方案...'

    def _build_agent(self) -> LlmAgent:
        """Builds the LLM agent for the frame transport agent."""
        return LlmAgent(
            name="frame_transport_agent",
            model="gemini-1.5-pro",
            description="车架专用物流运输Agent",
            instruction="""
                你是一个专业的物流运输专家，负责车架的运输。你的任务是根据用户提供的车架运输需求，制定详细的运输方案。

                请严格遵循以下步骤：
                1.  **分析需求**: 从用户输入中解析出需要运输的车架数量和目的地信息。
                2.  **规划路线**: 基于目的地，规划出一条最短、最经济的运输路线。
                3.  **安排工具**: 为车架运输安排合适的运输工具（例如：大型货车）。
                4.  **估算时间与成本**: 预估运输时间为2天，并给出一个合理的运输成本估算。
                5.  **生成方案**: 输出一个结构化的运输方案，必须包含以下部分：
                    -   **运输方案**: 对车架运输的具体安排描述。
                    -   **运输成本**: 预估的总费用。
                    -   **时间安排**: 预计的到达时间。

                示例输入:
                "订单确认：已接受500个车架的订单..."

                示例输出:
                "运输方案：已为500个车架安排大型货车运输，路线已规划为最优经济路线。
                运输成本：预估费用为8000元。
                时间安排：预计2天内送达目的地工厂。"
            """,
            tools=[],
            output_key="frame_transport_result"
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
