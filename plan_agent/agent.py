import json
import random

from collections.abc import AsyncIterable
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class PlanAgent:
    """一个负责创建生产计划的代理。"""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = 'plan_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        """获取一个表示正在处理的文本消息。"""
        return '正在制定生产计划...'

    def _build_agent(self) -> LlmAgent:
        """构建并返回核心的大语言模型代理（LlmAgent）。"""
        return LlmAgent(
            model='gemini-1.5-pro',
            name='plan_agent',
            description='一个能够根据用户输入，将高级生产目标拆解为具体任务的代理。',
            instruction="""
        你是一位专业的生产计划制定专家。你的核心任务是将用户提出的高级生产目标（例如“生产XX辆车”），拆解为一份包含具体零部件需求和时间安排的详细生产计划。

        请严格按照以下步骤执行：

        1.  **分析需求**: 从用户的输入中，精准地识别出需要生产的**车辆总数**。

        2.  **计算零部件需求**: 根据车辆总数，计算出所需的核心零部件数量：
            -   轮胎需求：车辆数量 × 4
            -   电池包需求：车辆数量 × 1
            -   车架需求：车辆数量 × 1

        3.  **制定生产计划**:
            -   基于零部件需求，给出一个合理的生产周期预估。
            -   在计划中明确指出对质量检验的要求。

        4.  **输出结构化的生产计划**:
            请以清晰、有条理的格式输出最终的生产计划。计划应明确包含以下几个部分：
            -   **总生产目标**: 清晰说明要生产的车辆总数。
            -   **零部件需求明细**: 列出每种核心零部件（轮胎、电池包、车架）的具体需求数量。
            -   **时间安排**: 给出预计的生产周期。
            -   **质量要求**: 强调所有零部件必须通过质检。

        **输出示例**:

        **输入**:
        "我们的目标是生产500辆全新的Cyber-X型号电动汽车。"

        **输出**:
        "生产计划：

        - **总生产目标**: 500辆 Cyber-X 新能源汽车。
        - **零部件需求明细**:
          - 轮胎: 2000个
          - 电池包: 500个 (型号 BATT-PACK-MODEL-X)
          - 车架: 500个
        - **时间安排**:
          - 预计总生产周期: 15天。
          - 要求所有零部件在生产开始后的第10天前全部到位。
        - **质量要求**:
          - 所有零部件在装配前必须通过100%的质量检验，确保符合国家新能源汽车安全标准。"
    """,
            tools=[],
        )

    async def stream(self, query, session_id) -> AsyncIterable[dict[str, Any]]:
        """
        运行代理链并流式传输结果。

        Args:
            query: 用户的输入查询。
            session_id: 当前会话的唯一标识符。

        Yields:
            一个包含事件更新的字典。
        """
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
