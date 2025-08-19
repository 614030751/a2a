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


class TireSupplyAgent:
    """一个负责管理轮胎供应的代理。"""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self._tire_inventory = 10000  # 默认库存
        self._agent = self._build_agent()
        self._user_id = 'remote_tire_supply_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        """获取一个表示正在处理的文本消息。"""
        return '正在处理轮胎供应请求...'

    def _build_agent(self) -> LlmAgent:
        """构建并返回核心的大语言模型代理（LlmAgent）。"""
        return LlmAgent(
            name="tire_supply_agent",
            model="gemini-1.5-pro",
            description=f"这是一个通用的轮胎供应商代理。当前库存{self._tire_inventory}个。",
            instruction=f"""
                你是一家通用轮胎供应商。

                你的库存是固定的，当前有 {self._tire_inventory} 个轮胎。

                定价规则（标准阶梯价）:
                - 需求数量 < 1000: 单价 500 元
                - 1000 <= 需求数量 <= 5000: 单价 480 元
                - 需求数量 > 5000: 单价 450 元

                请严格遵循以下逻辑：
                1.  **识别需求**:
                    *   如果用户的请求直接说明了需要的**轮胎数量**，请直接使用该数量。
                    *   如果用户的请求是关于**车辆生产**的（例如“生产XX辆车”），则将车辆数乘以4，计算出轮胎总数。
                2.  **核对库存**: 将最终计算出的轮胎需求数量与你的库存 ({self._tire_inventory}个) 进行比较。
                3.  **生成 JSON 响应**:
                    *   **如果库存充足**:
                        a. 根据定价规则，计算单价和总价。
                        b. 生成一个 JSON 对象，包含确认信息和报价。格式如下:
                           {{"status": "confirmed", "confirmation_message": "订单已确认。将提供 [数量] 个轮胎。", "quote": {{"unit_price": [单价], "total_price": [总价]}}}}
                    *   **如果库存不足**:
                        a. 计算库存缺口 (需求数量 - 库存数量)。
                        b. 生成一个 JSON 对象，说明订单无法处理。格式如下:
                           {{"status": "rejected", "rejection_message": "订单无法处理。需求 [数量] 个轮胎，库存不足。", "inventory_shortfall": [缺口数量]}}

                **不要在 JSON 响应之外添加任何多余的文字或解释。**
            """,
            tools=[],
        )

    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict[str, Any]]:
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
                final_content = ""
                if event.content and event.content.parts and event.content.parts[0].text:
                    final_content = event.content.parts[0].text
                
                try:
                    # 清理可能的 markdown 代码块
                    cleaned_response = final_content.strip().replace("```json", "").replace("```", "")
                    # 首先，将LLM的响应解析为Python字典
                    json_response_dict = json.loads(cleaned_response)
                    # 然后，将该字典重新编码为JSON字符串，以确保输出格式统一
                    yield {
                        'is_task_complete': True,
                        'content': json.dumps(json_response_dict, ensure_ascii=False), 
                    }
                except json.JSONDecodeError:
                    # 如果解析失败，返回一个结构化的错误 JSON 字符串
                    error_response = {
                        "status": "rejected",
                        "rejection_message": "供应商代理未能生成有效的 JSON 格式报价。",
                        "details": final_content
                    }
                    yield {
                        'is_task_complete': True,
                        'content': json.dumps(error_response, ensure_ascii=False),
                    }
            else:
                yield {
                    'is_task_complete': False,
                    'updates': self.get_processing_message(),
                }
