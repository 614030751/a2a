import asyncio
from collections.abc import AsyncIterable
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class BatterySummaryAgent:
    """An agent that summarizes a battery trade transaction."""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = 'remote_battery_summary_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        return '正在生成电池交易总结...'

    def _build_agent(self) -> LlmAgent:
        """Builds the LLM agent for summarizing the trade."""
        return LlmAgent(
            name="battery_summary_agent",
            model="gemini-1.5-pro",
            description="电池交易总结Agent",
            instruction="""
                你是一个财务交易专家，负责总结电池供应商的付款流程。

                你的任务是根据用户提供的一段包含订单详情、运输信息和交易凭证的文本，生成一份清晰的财务结算报告。

                请严格遵循以下步骤：
                1.  **解析输入**: 从提供的文本中提取以下信息：
                    *   电池的数量。
                    *   运输费用。
                    *   交易凭证（通常以"--- 交易凭证 ---"或"--- 交易失败 ---"开头）。
                2.  **计算成本**:
                    *   电池成本 = 电池数量 × 800元/个。
                    *   总计应付 = 电池成本 + 运输费用。
                3.  **生成报告**:
                    *   创建一个标题为 "财务结算报告" 的总结。
                    *   在报告中清晰地列出电池成本、物流费用和总计应付金额。
                    *   将从输入中提取的完整交易凭证附在报告的末尾。

                示例输入:
                "订单已确认，将提供1500个电池。运输方案：...运输成本：预估费用为4000元。--- 交易凭证 --- Hash: a6ea2e2d... 发送方: did:bid:efUG... 接收方: did:bid:ef25..."

                示例输出:
                "财务结算报告：
                - 电池成本：1500个 * 800元/个 = 1,200,000元
                - 物流费用：4000元
                - 总计应付：1,204,000元
                --- 交易凭证 ---
                Hash: a6ea2e2d...
                发送方: did:bid:efUG...
                接收方: did:bid:ef25..."
            """,
            tools=[],
            output_key="battery_summary_result"
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
