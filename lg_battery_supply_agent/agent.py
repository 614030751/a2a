import asyncio
from collections.abc import AsyncIterable
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class LgBatterySupplyAgent:
    """一个负责管理LG电池供应的代理。"""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self._battery_inventory = 12000  # LG 库存
        self._agent = self._build_agent()
        self._user_id = 'remote_lg_battery_supply_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        return '正在处理LG电池供应请求...'

    def _build_agent(self) -> LlmAgent:
        """构建并返回核心的大语言模型代理（LlmAgent）。"""
        return LlmAgent(
            name="lg_battery_supply_agent",
            model="gemini-1.5-pro",
            description=f"这是一个LG电池供应商代理，知名的消费电子及动力电池提供商。当前库存{self._battery_inventory}个。",
            instruction=f"""
                作为LG电池的官方供应商，你的任务是根据用户请求计算需求和报价。

                你的库存是固定的，当前有 {self._battery_inventory} 个电池。

                定价规则（LG经济型阶梯价）:
                - 需求数量 < 500: 单价 75000 元
                - 500 <= 需求数量 <= 2000: 单价 72000 元
                - 需求数量 > 2000: 单价 70000 元

                请严格遵循以下逻辑，并只返回一句话的文本答复：
                1.  **识别需求**: 从用户请求中识别出需要的**电池数量**。每辆车需要1个电池。
                2.  **核对库存**: 将计算出的电池需求数量与你的库存 ({self._battery_inventory}个) 进行比较。
                3.  **生成文本响应**:
                    *   **如果库存充足**:
                        a. 根据定价规则计算总价。
                        b. 返回格式如下的确认信息: "订单已确认，[数量]个LG电池的总价为 [总价] 元。"
                    *   **如果库存不足**:
                        a. 返回格式如下的拒绝信息: "订单无法处理，库存不足。"

                示例请求: "我需要100个电池"
                示例输出 (库存充足): "订单已确认，100个LG电池的总价为 7500000 元。"

                示例请求: "我需要20000个电池"
                示例输出 (库存不足): "订单无法处理，库存不足。"

                **请严格只输出一句话的文本答复，不要添加任何额外的文字或解释。**
            """,
            tools=[],
            output_key="lg_battery_result"
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
                    'content': self.get_processing_message(),
                }
