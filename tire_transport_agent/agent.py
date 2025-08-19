import asyncio
from collections.abc import AsyncIterable
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class TireTransportAgent:
    """An agent that arranges transport for tires."""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = 'remote_tire_transport_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        return '正在规划轮胎运输方案...'

    def _build_agent(self) -> LlmAgent:
        """Builds the LLM agent for the tire transport agent."""
        return LlmAgent(
            name="tire_transport_agent",
            model="gemini-1.5-pro",
            description="轮胎专用物流运输Agent",
            instruction="""
                你是一个专业的物流运输专家，负责轮胎的运输。你的任务是根据用户提供的轮胎运输需求，制定详细的运输方案。

                请严格遵循以下步骤：
                1.  **分析需求**: 从用户输入中解析出需要运输的轮胎数量和目的地信息。
                2.  **规划路线**: 基于目的地，规划出一条最短、最经济的运输路线。
                3.  **安排工具**: 为轮胎运输安排合适的运输工具（例如：标准货车）。
                4.  **估算时间与成本**: 预估运输时间为2天，并给出一个合理的运输成本估算。
                5.  **生成方案**: 输出一个结构化的运输方案，必须包含以下部分：
                    -   **运输方案**: 对轮胎运输的具体安排描述。
                    -   **运输成本**: 预估的总费用。
                    -   **时间安排**: 预计的到达时间。

                示例输入:
                "订单已确认。根据生产计划，500辆车需要2000个轮胎。库存充足，将从现有库存中调拨2000个轮胎用于生产。"

                示例输出:
                "运输方案：已为2000个轮胎安排标准货车运输，路线已规划为最优经济路线。
                运输成本：预估费用为3000元。
                时间安排：预计2天内送达目的地工厂。"
            """,
            tools=[],
            output_key="tire_transport_result"
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

        final_response_parts = []
        async for event in self._runner.run_async(
            user_id=self._user_id, session_id=session.id, new_message=content
        ):
            author = event.author or "system"
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if not part.text:
                        continue
                    
                    final_response_parts.append(part.text)

                    yield {
                        'is_task_complete': False,
                        'author': author,
                        'content': part.text,
                        'is_partial': True
                    }
                    await asyncio.sleep(0.05)
        
        yield {
            'is_task_complete': True,
            'content': "".join(final_response_parts),
            'author': self._agent.name,
            'is_partial': False,
        }
