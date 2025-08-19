from google.adk.agents import LlmAgent,BaseAgent,SequentialAgent,ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from typing import AsyncGenerator
from typing_extensions import override
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
import requests
import asyncio

count_number = 1000000000
tire_number = 10000
battery_number = 40000
frame_number = 10000


class TradeExecutorAgent(BaseAgent):
    """一个专门执行交易并存储收据的Agent。"""

    def __init__(self, name: str, description: str):
        super().__init__(name=name, description=description)

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """执行交易，将结果存入会话状态，并产生一个事件。"""
        agent_name = self.name
        receipt_key = f"{agent_name}_receipt"

        payload = {
            "senderAddress": "did:bid:efUGVkkJ746m4iCKgSpECXcni4v1cUaQ",
            "privateKey": "priSPKrcQaSLzFtwUHuzDuxAR9pxqXS1CbT4Vpc8aSbpCLtjt1",
            "destAddress": "did:bid:ef25XsX1QLoaTB459SpucsM8i4baHPnAE",
            "amount": 0.06,
            "remarks": "",
            "gasPrice": 100,
            "feeLimit": 100000000,
            "nonceType": 0
        }
        receipt_text = ""
        try:
            response = requests.post(
                "http://192.168.110.51:9090/agent-chain/chain/transfer", json=payload
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                receipt_text = (
                    f"\n--- 交易凭证 ---\n"
                    f"Hash: {data.get('hash')}\n"
                    f"发送方: {data.get('senderAddress')}\n"
                    f"接收方: {data.get('destAddress')}"
                )
                event_text = (
                    f"交易成功!\n"
                    f"Hash: {data.get('hash')}\n"
                    f"发送方: {data.get('senderAddress')}\n"
                    f"接收方: {data.get('destAddress')}"
                )
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=event_text)]),
                )
            else:
                error_message = data.get("message", "未知错误")
                receipt_text = f"\n--- 交易失败 ---\n原因: {error_message}"
                yield Event(
                    author=self.name,
                    content=types.Content(
                        parts=[types.Part(text=f"交易失败: {error_message}")]
                    ),
                )
        except Exception as e:
            receipt_text = f"\n--- 交易API调用失败 ---\n错误: {e}"
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"API调用错误: {e}")]),
            )

        ctx.session.state[receipt_key] = receipt_text
        print(f"为 {agent_name} 执行的交易。收据: {receipt_text}")


class FactoryChain(BaseAgent):

    plan_agent: LlmAgent
    supply_chain_agent: SequentialAgent

    model_config = {"arbitrary_types_allowed": True}


    def __init__(
            self,
            name:str,
            plan_agent:LlmAgent,
            tire_supply_agent: LlmAgent,
            batter_supply_agent: LlmAgent,
            frame_supply_agent: LlmAgent,
    ):
        tire_transport_instruction = f"""
        你是一个专业的物流运输专家，负责轮胎的运输。请严格遵循以下步骤：
        1. 分析从{{tire_result}}获取的轮胎运输需求。
        2. 规划最短、最经济的运输路线。
        3. 安排合适的运输工具（标准货车），预计运输时间2天。
        4. 提供运输成本估算和时间安排。
        输出格式：
        - 运输方案：轮胎的具体运输安排
        - 运输成本：预估总费用
        - 时间安排：预计到达时间
        """
        tire_transport_agent = LlmAgent(
            name="tire_transport_agent",
            model="gemini-2.5-flash",
            description="轮胎专用物流运输Agent",
            instruction=tire_transport_instruction,
            output_key="tire_transport_result",
        )
        
        tire_trade_executor = TradeExecutorAgent(
            name="tire_trade",
            description="执行轮胎供应商付款的链上交易"
        )

        tire_trade_instruction = f"""
        你是一个财务交易专家，负责处理轮胎供应商的付款。请严格遵循以下步骤：
        1. 从{{tire_result}}获取订单金额，从{{tire_transport_result}}获取运输费用。
        2. 计算应付款项（轮胎单价：500元/个，物流费按实际计算）。
        3. 你的最终输出必须包含你计算出的付款明细，并附加上下文中的交易凭证 `{{tire_trade_receipt}}`。
        """
        tire_trade_summary_agent = LlmAgent(
            name="tire_trade_summary", 
            model="gemini-2.5-flash",
            description="轮胎交易总结Agent",
            instruction=tire_trade_instruction,
            output_key="tire_trade_result",
        )

        battery_transport_instruction = f"""
        你是一个专业的物流运输专家，负责电池包的运输。请严格遵循以下步骤：
        1. 分析从{{battery_result}}获取的电池包运输需求。
        2. 规划最短、最经济的运输路线，并考虑防震要求。
        3. 安排合适的运输工具（防震专用车），预计运输时间3天。
        4. 提供运输成本估算和时间安排。
        输出格式：
        - 运输方案：电池包的具体运输安排
        - 运输成本：预估总费用
        - 时间安排：预计到达时间
        """
        battery_transport_agent = LlmAgent(
            name="battery_transport_agent",
            model="gemini-2.5-flash", 
            description="电池包专用物流运输Agent",
            instruction=battery_transport_instruction,
            output_key="battery_transport_result",
        )
        
        battery_trade_executor = TradeExecutorAgent(
            name="battery_trade",
            description="执行电池包供应商付款的链上交易"
        )
        
        battery_trade_instruction = f"""
        你是一个财务交易专家，负责处理电池包供应商的付款。请严格遵循以下步骤：
        1. 从{{battery_result}}获取订单金额，从{{battery_transport_result}}获取运输费用。
        2. 计算应付款项（电池包单价：5000元/个，物流费按实际计算）。
        3. 你的最终输出必须包含你计算出的付款明细，并附加上下文中的交易凭证 `{{battery_trade_receipt}}`。
        """
        battery_trade_summary_agent = LlmAgent(
            name="battery_trade_summary",
            model="gemini-2.5-flash",
            description="电池包交易总结Agent", 
            instruction=battery_trade_instruction,
            output_key="battery_trade_result",
        )

        frame_transport_instruction = f"""
        你是一个专业的物流运输专家，负责车架的运输。请严格遵循以下步骤：
        1. 分析从{{frame_result}}获取的车架运输需求。
        2. 规划最短、最经济的运输路线，并考虑防锈要求。
        3. 安排合适的运输工具（大型货车），预计运输时间2天。
        4. 提供运输成本估算和时间安排。
        输出格式：
        - 运输方案：车架的具体运输安排
        - 运输成本：预估总费用
        - 时间安排：预计到达时间
        """
        frame_transport_agent = LlmAgent(
            name="frame_transport_agent",
            model="gemini-2.5-flash",
            description="车架专用物流运输Agent",
            instruction=frame_transport_instruction,
            output_key="frame_transport_result",
        )
        
        frame_trade_executor = TradeExecutorAgent(
            name="frame_trade",
            description="执行车架供应商付款的链上交易"
        )
        
        frame_trade_instruction = f"""
        你是一个财务交易专家，负责处理车架供应商的付款。请严格遵循以下步骤：
        1. 从{{frame_result}}获取订单金额，从{{frame_transport_result}}获取运输费用。
        2. 计算应付款项（车架单价：3000元/个，物流费按实际计算）。
        3. 你的最终输出必须包含你计算出的付款明细，并附加上下文中的交易凭证 `{{frame_trade_receipt}}`。
        """
        frame_trade_summary_agent = LlmAgent(
            name="frame_trade_summary",
            model="gemini-2.5-flash", 
            description="车架交易总结Agent",
            instruction=frame_trade_instruction,
            output_key="frame_trade_result",
        )

        seq_tire_agent = SequentialAgent(
            name="seq_tire_agent",
            description="轮胎供应链完整流程管理：从订单确认→物流配送→财务结算，确保轮胎按时按质交付并完成全流程闭环管理",
            sub_agents=[tire_supply_agent, tire_transport_agent, tire_trade_executor, tire_trade_summary_agent]
        )

        seq_battery_agent = SequentialAgent(
            name="seq_battery_agent",
            description="新能源电池包全链路管理：专业处理BATT-PACK-MODEL-X电池包的技术确认→安全运输→资金结算，严格执行新能源汽车电池安全标准",
            sub_agents=[batter_supply_agent, battery_transport_agent, battery_trade_executor, battery_trade_summary_agent]
        )

        seq_frame_agent = SequentialAgent(
            name="seq_frame_agent",
            description="汽车车架制造交付流程：高强度钢车架从生产质检→专业运输→付款结算的完整供应链管理，确保车架结构安全和交付质量",
            sub_agents=[frame_supply_agent, frame_transport_agent, frame_trade_executor, frame_trade_summary_agent]
        )

        supply_chain_agent = SequentialAgent(
            name="all_supply_agent", 
            description="汽车制造核心供应链协调中枢：依次协调轮胎、电池包、车架三大核心零部件的采购、生产和交付，确保整车生产的零部件同步到位",
            sub_agents=[seq_tire_agent, seq_battery_agent, seq_frame_agent]
        )

        super().__init__(
            name=name,
            sub_agents=[plan_agent, supply_chain_agent],
            plan_agent=plan_agent,
            supply_chain_agent=supply_chain_agent,
        )

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        async for event in self.plan_agent.run_async(ctx):
            yield event

        if "plan_result" not in ctx.session.state or not ctx.session.state["plan_result"]:
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text="错误：无法生成生产计划，工作流中断。")]
                ),
            )
            return
        
        async for event in self.supply_chain_agent.run_async(ctx):
            yield event


plan_agent = LlmAgent(
    name="plan_agent",
    model="gemini-2.5-flash",
    description="将生产计划进行拆分，让不同的agent进行任务的执行",
    instruction="""
        你是一个生产计划制定专家，负责将用户的生产需求拆解为详细的采购和生产任务。请严格遵循以下步骤：
        
        1. 分析用户输入的生产需求（如：生产多少辆车）
        2. 计算各个零部件的需求量：
           - 轮胎需求：车辆数量 × 4个/辆
           - 电池包需求：车辆数量 × 1个/辆  
           - 车架需求：车辆数量 × 1个/辆
           
        3. 制定生产时间安排：
           - 分析生产周期和交付时间要求
           - 考虑各供应商的生产能力
           - 制定合理的采购和生产计划
           
        4. 输出详细的生产计划，包括：
           - 总生产目标：需要生产XX辆车
           - 零部件需求明细：轮胎XX个，电池包XX个，车架XX个
           - 时间安排：预计总生产周期XX天
           - 质量要求：所有零部件必须通过质检
           
        示例输出格式：
        "生产计划：本次需要生产100辆新能源汽车。
        零部件需求：轮胎400个，电池包100个（型号BATT-PACK-MODEL-X），车架100个。
        预计生产周期：15天，要求所有零部件在第10天前到位。
        质量标准：符合国家新能源汽车标准。"
    """,
    output_key="plan_result",
)

tire_supply_agent = LlmAgent(
    name="tire_supply_agent",
    model="gemini-2.5-flash",
    description=f"这是一个轮胎供应商Agent，Agent维护了一个轮胎数量{tire_number},每次plan_agent下发订单的时候就{tire_number}减去相对应的数量。",
    instruction=f"""
        你是一个轮胎供应商，专门处理来自plan_agent的下单请求,实现下单。请严格遵循以下步骤：
        
        1. 分析{{plan_result}},查看下了多少量订单的车，根据每辆车的数量 * 4获得要下单的轮胎数量，然后用当前库存 {tire_number}
        2. 计算所需轮胎总数 = 车辆数量 × 4
        3. 检查库存是否充足：当前库存{tire_number}个轮胎
        4. 如果库存够用，确认订单并更新库存
        5. 如果库存不足，提示需要补货多少个轮胎
    """,
    output_key="tire_result",
)

batter_supply_agent = LlmAgent(
    name="battery_supply_agent",
    model="gemini-2.5-flash",
    description="电池包供应商Agent，负责电池包的采购、库存管理和出库配送",
    instruction=f"""
        你是一个电池包供应商，专门处理电池包的订单请求。请严格遵循以下步骤：
        
        1. 分析{{plan_result}}中的生产计划，确定需要的电池包数量
        2. 每辆车需要1个电池包，计算总需求量
        3. 检查当前库存状态（假设库存充足）
        4. 确认电池包规格：BATT-PACK-MODEL-X
        5. 安排电池包的质检、包装和出库
        6. 预估交付时间并确认订单
        
        输出格式：
        - 订单确认：已接受XX个电池包的订单
        - 库存状态：当前库存充足/需要补货
        - 预计交付时间：X天内完成出库
        - 质量保证：所有电池包均通过质检
    """,
    output_key="battery_result",
)

frame_supply_agent = LlmAgent(
    name="frame_supply_agent",
    model="gemini-2.5-flash", 
    description="车架供应商Agent，负责车架的生产、质检和出库配送",
    instruction=f"""
        你是一个车架供应商，专门处理车架的订单请求。请严格遵循以下步骤：
        
        1. 分析{{plan_result}}中的生产计划，确定需要的车架数量
        2. 每辆车需要1个车架，计算总需求量
        
        3. 检查车架生产能力和库存状态
        4. 确认车架规格和材质要求
        5. 安排车架的焊接、质检和表面处理
        6. 准备车架的包装和出库
        
        输出格式：
        - 订单确认：已接受XX个车架的订单
        - 生产状态：正在生产/库存现货
        - 质检结果：所有车架通过强度测试
        - 预计交付：X天内完成生产和出库
    """,
    output_key="frame_result",
)

transport_agent = LlmAgent(
    name="transport_agent",
    model="gemini-2.5-flash",
    description="物流运输Agent，负责规划最优运输路线、车辆调度和货物跟踪",
    instruction=f"""
        你是一个专业的物流运输专家，负责协调各供应商的货物运输。请严格遵循以下步骤：
        
        1. 分析需要运输的货物类型和数量：
           - 从{{tire_result}}获取轮胎运输需求
           - 从{{battery_result}}获取电池包运输需求  
           - 从{{frame_result}}获取车架运输需求
        
        2. 制定综合运输方案：
           - 规划最短、最经济的运输路线
           - 考虑货物的特殊要求（电池包需要防震、车架需要防锈）
           - 安排合适的运输工具（卡车/专用运输车）
           
        3. 运输执行计划：
           - 轮胎运输：标准货车，预计运输时间2天
           - 电池包运输：防震专用车，预计运输时间3天
           - 车架运输：大型货车，预计运输时间2天
           
        4. 提供运输成本估算和时间安排
        
        输出格式：
        - 运输方案：各类货物的具体运输安排
        - 运输成本：预估总费用
        - 时间安排：各货物的预计到达时间
        - 跟踪服务：提供货物在途跟踪
    """,
    output_key="transport_result",
)

trade_agent = LlmAgent(
    name="trade_agent",
    model="gemini-2.5-flash",
    description="财务交易Agent，负责处理供应商付款、结算和财务记录",
    instruction=f"""
        你是一个财务交易专家，负责处理供应商的付款和结算。请严格遵循以下步骤：
        
        1. 收集各供应商的交易信息：
           - 轮胎供应商：从{{tire_result}}获取订单金额
           - 电池包供应商：从{{battery_result}}获取订单金额
           - 车架供应商：从{{frame_result}}获取订单金额
           - 物流服务商：从{{transport_result}}获取运输费用
           
        2. 计算各供应商的应付款项：
           - 轮胎单价：500元/个，按实际数量计算
           - 电池包单价：5000元/个，按实际数量计算
           - 车架单价：3000元/个，按实际数量计算
           - 物流费用：按运输方案计算
           
        3. 执行付款流程：
           - 核实订单和货物接收情况
           - 检查发票和质量验收单
           - 安排银行转账或票据支付
           - 更新财务系统记录
           
        4. 生成财务报告和付款凭证
        
        输出格式：
        - 付款明细：各供应商的具体付款金额
        - 付款状态：已付款/待付款/分期付款
        - 财务记录：交易流水号和凭证号
        - 成本分析：总采购成本和成本构成
    """,
    output_key="trade_result",
)

from collections.abc import AsyncIterable
from typing import Any

from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

class FactoryAgent:
    """An agent that simulates a factory supply chain."""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = 'a2a_user'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        return '工厂正在运转...'

    def _build_agent(self) -> FactoryChain:
        """Builds the FactoryChain agent."""
        return FactoryChain(
            name="FactoryFlow_Agent",
            plan_agent=plan_agent,
            tire_supply_agent=tire_supply_agent,
            batter_supply_agent=batter_supply_agent,
            frame_supply_agent=frame_supply_agent,
        )

    async def stream(self, query, session_id) -> AsyncIterable[dict[str, Any]]:
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
            author = event.author or "system"
            
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if not part.text:
                        continue
                    
                    is_partial = hasattr(part, 'partial') and part.partial
                    
                    yield {
                        'is_task_complete': False,
                        'author': author,
                        'content': part.text,
                        'is_partial': is_partial
                    }
                    if is_partial:
                        await asyncio.sleep(0.05) # 控制流式输出速度
            else:
                yield {
                    'is_task_complete': False,
                    'author': author,
                    'content': self.get_processing_message(),
                    'is_partial': True
                }

        yield {
            'is_task_complete': True,
            'content': '工厂模拟完成。',
            'author': 'system',
            'is_partial': False, 
        }

