import asyncio
import json
from collections.abc import AsyncIterable
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class HirschvogelFrameSupplyAgent:
    """一个负责管理赫尔施福格车架供应的代理。"""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        """初始化赫尔施福格车架供应代理。"""
        self._frame_inventory = 15000
        self._agent = self._build_agent()
        self._user_id = 'remote_hirschvogel_frame_supply_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        """获取一个表示正在处理的文本消息。"""
        return '正在处理赫尔施福格车架供应请求...'

    def _build_agent(self) -> LlmAgent:
        """构建并返回核心的大语言模型代理（LlmAgent）。"""
        return LlmAgent(
            name="hirschvogel_frame_supply_agent",
            model="gemini-1.5-pro",
            description=f"这是一个赫尔施福格车架供应商代理，以其经济型车架而闻名。当前库存{self._frame_inventory}个。",
            instruction=f"""
                作为赫尔施福格车架的官方供应商，你的任务是根据用户请求计算需求和报价。

                你的库存是固定的，当前有 {self._frame_inventory} 个车架。

                定价规则（赫尔施福格经济型阶梯价）:
                - 需求数量 < 100: 单价 4000 元
                - 100 <= 需求数量 <= 500: 单价 3800 元
                - 需求数量 > 500: 单价 3500 元

                请严格遵循以下逻辑，并只返回一句话的文本答复：
                1.  **识别需求**: 从用户请求中识别出需要的**车架数量**。每辆车需要1个车架。
                2.  **核对库存**: 将计算出的车架需求数量与你的库存 ({self._frame_inventory}个) 进行比较。
                3.  **生成文本响应**:
                    *   **如果库存充足**:
                        a. 根据定价规则计算总价。
                        b. 返回格式如下的确认信息: "订单已确认，[数量]个赫尔施福格车架的总价为 [总价] 元。"
                    *   **如果库存不足**:
                        a. 返回格式如下的拒绝信息: "订单无法处理，库存不足。"

                示例请求: "我需要50个车架"
                示例输出 (库存充足): "订单已确认，50个赫尔施福格车架的总价为 200000 元。"

                示例请求: "我需要20000个车架"
                示例输出 (库存不足): "订单无法处理，库存不足。"

                **请严格只输出一句话的文本答复，不要添加任何额外的文字或解释。**
            """,
            tools=[],
            output_key="hirschvogel_frame_result"
        )

    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict[str, Any]]:
        """
        运行代理链并流式传输结果。
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
                    'content': self.get_processing_message(),
                }

