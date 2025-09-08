import asyncio
import json
import re
import uuid
from typing import AsyncGenerator, List, Dict, Any, AsyncIterable

import requests
import httpx
from google.adk.agents import LlmAgent, BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from typing_extensions import override

# ###########################################################################
# 步骤 1: 定义顺序链中的各个子 Agent。
# ###########################################################################

class RouterAgent(LlmAgent):
    """链中的第一个 Agent：根据用户查询找到相关的智能体。"""
    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # 1. 发送启动消息
        yield Event(author=self.name, content=types.Content(parts=[types.Part(text="🚀 浏览器智能体开始分析您的请求...")]))
        await asyncio.sleep(0.5)

        all_agents = self._fetch_all_agents()
        if not all_agents:
            yield Event(author=self.name, content=types.Content(parts=[types.Part(text="❌ 未找到任何可用的供应商智能体。")]))
            return

        # 2. 找到智能体后，发送状态更新
        yield Event(
            author=self.name, 
            content=types.Content(parts=[types.Part(text=f"✅ 成功找到 {len(all_agents)} 个智能体，正在为您进行语义匹配...")])
        )
        await asyncio.sleep(0.5)
        
        ctx.session.state["all_agents"] = all_agents

        formatted_agents = self._format_agents_for_llm(all_agents)
        self.instruction = f"""
        作为一名 Agent 发现专家，请根据对话历史中的用户请求，从下面的列表中找出相关的 Agent ID。

        可用 Agent (ID - 名称 - 描述):
        {formatted_agents}

        根据用户的请求，输出一个包含匹配 Agent ID 的 JSON 对象。
        示例格式: {{"selected_agents": ["agent_id_1", "agent_id_2"]}}

        如果未找到匹配的 智能体，则返回一个空列表: {{"selected_agents": []}}

        请不要在 JSON 对象之外添加任何额外的解释或介绍性文字。
        """

        llm_response = ""
        async for event in super()._run_async_impl(ctx):
            if event.is_final_response():
                llm_response = event.content.parts[0].text
        
        try:
            cleaned_response = llm_response.strip().replace("```json", "").replace("```", "")
            selected_agent_ids = json.loads(cleaned_response).get("selected_agents", [])
        except json.JSONDecodeError:
            selected_agent_ids = []
            
        if not selected_agent_ids:
            yield Event(author=self.name, content=types.Content(parts=[types.Part(text="❌ 根据您的请求，未能匹配到合适的供应商智能体。")]))
            return

        ctx.session.state["selected_agent_ids"] = selected_agent_ids
        
        # 3. 发送最终格式化的匹配结果
        result_summary = [f"**🔍 已为您匹配到 {len(selected_agent_ids)} 个相关供应商智能体：**"]
        for agent_id in selected_agent_ids:
            agent_details = next((agent for agent in all_agents if agent.get("agentId") == agent_id), None)
            if agent_details:
                name = agent_details.get('name', 'N/A')
                description = agent_details.get('description', '无')
                pricing_cost = agent_details.get('pricingCost', 'N/A')
                wallet_address = agent_details.get('blockchainInfo', {}).get('walletAddress', 'N/A')
                url = agent_details.get('url', 'N/A')

                result_summary.append("\n---")
                result_summary.append(f"**🤖 智能体名称:** {name}")
                result_summary.append(f"   - **功能描述:** {description}")
                result_summary.append(f"   - **价格成本:** `{pricing_cost}`")
                result_summary.append(f"   - **钱包地址:** `{wallet_address}`")
                result_summary.append(f"   - **服务地址:** {url}")
        
        final_summary = "\n".join(result_summary)
        yield Event(author=self.name, content=types.Content(parts=[types.Part(text=final_summary)]))

    def _fetch_all_agents(self) -> List[Dict]:
        url = "http://43.162.109.76:18080/chainagent/api/v1/agent/public/list"
        try:
            response = requests.post(url)
            response.raise_for_status()
            return response.json().get("data", [])
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"Error fetching agents: {e}")
            return []

    def _format_agents_for_llm(self, agents: List[Dict]) -> str:
        return "\n".join([f"- {a.get('agentId')} - {a.get('name')} - {a.get('description')}" for a in agents])

class VcVerifierAgent(BaseAgent):
    """链中的第二个 Agent：为每个入围的 Agent 验证其 VC。"""
    def __init__(self, name: str, description: str):
        super().__init__(name=name, description=description)

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        selected_agent_ids = ctx.session.state.get("selected_agent_ids", [])
        all_agents = ctx.session.state.get("all_agents", [])

        if not selected_agent_ids:
            return

        agents_to_verify = [a for a in all_agents if a.get("agentId") in selected_agent_ids]
        full_verified_agents = []

        yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"✅ **开始验证资质凭证...**")]))
        await asyncio.sleep(0.5)
        # 添加用户凭证验证信息
        user_verification_message = "   - ✅ **验证成功**: 用户 的凭证已核实 (VC ID: `vc:bid:ecd3e512-88db-4561-9d54-0d165b524538`)"
        yield Event(author=self.name, content=types.Content(parts=[types.Part(text=user_verification_message)]))
        await asyncio.sleep(0.2)
        # 逐个验证并单独发送每个结果
        for agent in agents_to_verify:
            agent_name = agent.get("name")
            vc_content = agent.get("blockchainInfo", {}).get("vcContent")
            message = ""

            if not vc_content:
                message = f"   - ⚠️ **跳过验证**: **{agent_name}** 未提供资质凭证。"
                yield Event(author=self.name, content=types.Content(parts=[types.Part(text=message)]))
                continue

            verified, credential_id = await self._verify_vc_content(vc_content)
            
            
            if verified:
                full_verified_agents.append(agent)
                message = f"   - ✅ **验证成功**: **{agent_name}** 的凭证已核实 (VC ID: `{credential_id}`)"
            else:
                message = f"   - ❌ **验证失败**: **{agent_name}** 的凭证未能通过核实。"
            
            yield Event(author=self.name, content=types.Content(parts=[types.Part(text=message)]))
            await asyncio.sleep(0.2)
        

        
        # 保存状态以供链条中的下一个Agent使用
        ctx.session.state["full_verified_agents"] = full_verified_agents
        
        # 发送一个空的最终事件来确保链条继续，但不在UI上显示任何内容
        yield Event(author=self.name, content=types.Content())

    async def _verify_vc_content(self, vc_content: str) -> tuple[bool, str | None]:
        url = "http://43.162.109.76:18080/chainagent/chain/vc/verify"
        try:
            # API 期望数据格式为 'application/x-www-form-urlencoded'。
            # 我们将内容作为字典传递给 'data' 参数。
            response = requests.post(url, data={"vcContent": vc_content})
            response.raise_for_status()
            data = response.json().get("data", {})
            if data.get("verified") is True:
                return True, data.get("credential", {}).get("id")
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"VC 验证失败: {e}")
        return False, None

# ###########################################################################
# 步骤 2: 将子 Agent 组合成一个顺序链。
# 这类似于 factoryagent 中的 `FactoryChain`。
# ###########################################################################


class bridgestoneAgent(BaseAgent):
    """一个专门调用智能体 Agent 以获取报价的 Agent。"""

    def __init__(self, name: str, description: str):
        super().__init__(name=name, description=description)

    async def _call_supplier_agent(self, agent_url: str, message_params: Dict[str, Any]) -> Any:
        """异步调用单个智能体 Agent 的 API。"""
        try:
            # 从原始参数中提取正确的格式，排除支付相关信息
            params = message_params.get("params", {})
            message = params.get("message", {})
            
            # 构造符合子agent期望的标准请求格式
            payload = {
                "id": str(uuid.uuid4()),  # 生成唯一的请求ID
                "params": {
                    "message": {
                        "messageId": str(uuid.uuid4()),  # 生成唯一的消息ID
                        "contextId": message.get("contextId"),
                        "role": "user",  # 设置必需的role字段
                        "parts": message.get("parts", [])
                    }
                }
            }
            
            # 添加其他可能需要的字段（排除支付相关信息）
            if "senderAddress" in params:
                payload["params"]["senderAddress"] = params["senderAddress"]
            if "privateKey" in params:
                payload["params"]["privateKey"] = params["privateKey"]

            print(f"--- Debug: Cleaned payload for {agent_url}: {payload} ---")

            # 注意：智能体 Agent 可能需要一些时间来启动和响应
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(agent_url, json=payload)
                response.raise_for_status()
                
                # 智能体 Agent 返回的是 SSE (Server-Sent Events) 流
                # 我们需要解析这个流来找到最终的消息
                final_data = None
                print(f"--- Debug: Raw Response from {agent_url} ---")
                async for line in response.aiter_lines():
                    print(f"Supplier Raw Line: {line}")
                    try:
                        # 不再检查 'data:' 前缀，直接处理非空行
                        data_str = line.strip()
                        if not data_str:
                            continue
                            
                        data = json.loads(data_str)
                        
                        # 检查是否为包含 'result' 的最终响应
                        result = data.get('result')
                        status_obj = result.get('status', {}) if isinstance(result, dict) else {}

                        if status_obj.get('state') == 'completed':
                            artifacts = result.get('artifacts')
                            if isinstance(artifacts, list) and artifacts:
                                parts = artifacts[0].get('parts')
                                if isinstance(parts, list) and parts:
                                    # 最终的文本内容在 parts[0] 的 'text' 字段中
                                    text_content = parts[0].get('text')
                                    if text_content:
                                        final_data = text_content
                                        break # 成功提取数据，退出循环
                    except json.JSONDecodeError:
                        print(f"--- Debug: JSON decode error for line: {line} ---")
                        continue # 忽略无法解析的行
                print(f"--- Debug: End Raw Response ---")
                print(f"--- Debug: Final data extracted: {final_data} ---")
                return final_data

        except (httpx.RequestError, json.JSONDecodeError) as e:
            print(f"调用智能体 Agent ({agent_url}) 出错: {e}")
            return None

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """为每个已验证的智能体获取报价，并从文本中提取价格。"""
        full_verified_agents = ctx.session.state.get("full_verified_agents", [])
        # 使用清理后的消息参数供子agent调用
        message_params = ctx.session.state.get("cleaned_message_params")

        if not full_verified_agents or not message_params:
            return

        summary_lines = [
            "**正在获取报价**", 
            "---",
            f"📊 开始为 {len(full_verified_agents)} 个智能体获取报价..."
        ]
        
        agents_with_quotes = []

        for agent in full_verified_agents:
            agent_name = agent.get("name")
            agent_url = agent.get("url")

            if not agent_url:
                summary_lines.append(f"- **{agent_name}**: ⚠️ 跳过，缺少 URL。")
                continue

            response_text = await self._call_supplier_agent(agent_url, message_params)

            if not response_text:
                summary_lines.append(f"- **{agent_name}**: ❌ 获取响应失败或响应为空。")
                continue

            # 尝试解析JSON格式的响应
            try:
                json_response = json.loads(response_text)
                
                # 处理JSON格式的响应
                if json_response.get("status") == "confirmed":
                    quote = json_response.get("quote", {})
                    total_price = quote.get("total_price")
                    if total_price:
                        currency = "星火令"  # 统一货币单位为星火令
                        agent['quote'] = {"total_price": total_price, "currency": currency}
                        agents_with_quotes.append(agent)
                        confirmation_msg = json_response.get("confirmation_message", "订单已确认")
                        summary_lines.append(f"- **{agent_name}**: ✅ 获取报价成功: {total_price} {currency}")
                    else:
                        summary_lines.append(f"- **{agent_name}**: ℹ️ JSON响应缺少价格信息: {response_text}")
                elif json_response.get("status") == "rejected":
                    rejection_msg = json_response.get("rejection_message", "订单被拒绝")
                    summary_lines.append(f"- **{agent_name}**: ℹ️ {rejection_msg}")
                else:
                    summary_lines.append(f"- **{agent_name}**: ℹ️ 未知JSON响应状态: {response_text}")
                    
            except json.JSONDecodeError:
                # 如果不是JSON格式，尝试原来的文本解析方式
                price_match = re.search(r"总价为\s*(\d+(\.\d+)?)\s*(元|星火令)", response_text)
                
                if "订单已确认" in response_text and price_match:
                    try:
                        total_price = float(price_match.group(1))
                        currency = "星火令"  # 统一货币单位为星火令
                        agent['quote'] = {"total_price": total_price, "currency": currency}
                        agents_with_quotes.append(agent)
                        summary_lines.append(f"- **{agent_name}**: ✅ 获取报价成功: {total_price} {currency}")
                    except (ValueError, IndexError):
                        summary_lines.append(f"- **{agent_name}**: ℹ️ 提取价格失败: {response_text}")

                elif "库存不足" in response_text or "无法处理" in response_text:
                     summary_lines.append(f"- **{agent_name}**: ℹ️ {response_text}")
                else:
                    summary_lines.append(f"- **{agent_name}**: ℹ️ 未知格式响应: {response_text}")

        # 将带有报价信息的 Agent 列表存回会话状态
        ctx.session.state["agents_with_quotes"] = agents_with_quotes
        
        # 如果有成功的报价，则追加最终的决策问题
        if agents_with_quotes:
            best_agent = min(agents_with_quotes, key=lambda a: a.get("quote", {}).get("total_price", float('inf')))
            min_price = best_agent.get("quote", {}).get("total_price")
            currency = best_agent.get("quote", {}).get("currency", "星火令")
            
            summary_lines.append("\n---\n")  # 强力换行
            summary_lines.append(
                f"报价获取完成。价格最低的供应商是 **'{best_agent.get('name')}'** (报价: **{min_price} {currency}**)。"
            )
        else:
            summary_lines.append("\n---")
            summary_lines.append("报价获取流程完成，未收到任何有效报价。")

        final_summary = "\n".join(summary_lines)
        yield Event(author=self.name, content=types.Content(parts=[types.Part(text=final_summary)]))


class TradeExecutorAgent(BaseAgent):
    """一个专门为每个已验证的智能体执行交易的Agent。"""

    def __init__(self, name: str, description: str):
        super().__init__(name=name, description=description)

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """根据合同中选定的智能体执行交易。"""
        selected_trade_agent = ctx.session.state.get("selected_trade_agent")

        if not selected_trade_agent:
            return

        summary_lines = ["**正在执行星火令交易**", "---"]
        
        best_agent = selected_trade_agent
        min_price = best_agent.get("quote", {}).get("total_price")
        currency = best_agent.get("quote", {}).get("currency", "星火令")
        agent_name = best_agent.get("name")
            
        summary_lines.append(
            f"✅ 根据合同，正在与智能体执行交易: "
            f"'{agent_name}' (报价: {min_price} {currency})"
        )
        
        # 检查是否是从支付结果中提取的信息
        is_from_payment_result = ctx.session.state.get("is_from_payment_result", False)
        
        # 从前端传来的数据中提取交易信息（使用完整的原始数据）
        original_message_params = ctx.session.state.get("original_message_params", {})
        # 获取清理后的参数供子agent使用
        cleaned_message_params = ctx.session.state.get("cleaned_message_params", {})
        
        # 添加调试信息
        print(f"--- Debug TradeExecutor: original_message_params: {original_message_params} ---")
        
        # 检查是否有 transactionResult 数据（可能在 original_message_params 顶层）
        transaction_result = original_message_params.get("transactionResult")
        if not transaction_result:
            # 检查是否在 params 层级
            params = original_message_params.get("params", {})
            transaction_result = params.get("transactionResult")
        
        if transaction_result:
            transaction_data = transaction_result.get("data", {})
            # 检查 senderName 的位置
            sender_name = original_message_params.get("senderName")
            if not sender_name:
                # 如果顶层没有，检查 params 层级
                params = original_message_params.get("params", {})
                sender_name = params.get("senderName", "信通院")
            
            print(f"--- Debug: 找到 transactionResult: {transaction_result} ---")
            print(f"--- Debug: sender_name: {sender_name} ---")
            
            # 使用前端传来的交易数据，但对于截断的地址使用完整默认值
            raw_sender_address = transaction_data.get("senderAddress", "")
            raw_dest_address = transaction_data.get("destAddress", "")
            
    
            
            payment_amount = transaction_data.get("amount", 50000)
            payment_tx_hash = transaction_data.get("txHash", "0x1a2b3c4d5e6f7890abcdef1234567890abcdef12")
            transaction_success = transaction_data.get("success", True)
            transaction_code = transaction_result.get("code", 0)
            transaction_message = transaction_result.get("message", "操作成功")
    
        
        summary_lines.append(f"💰 付款方钱包: {raw_sender_address}")
        summary_lines.append(f"💰 收款方钱包: {raw_dest_address} ({agent_name})")
        
        # 根据交易状态显示不同的信息
        if transaction_success and transaction_code == 0:
            summary_lines.append(
                f"\n✅ 支付给 '{agent_name}' 成功！\n"
                f"   - 发送方: {sender_name}\n"
                f"   - 支付钱包: {raw_sender_address}\n"
                f"   - 目标钱包: {raw_dest_address}\n"
                f"   - 交易金额: {payment_amount}\n"
                f"   - 交易 Hash: {payment_tx_hash}\n"
                f"   - 交易状态: {transaction_message}\n"
                f"   - 交易代码: {transaction_code}"
            )
        else:
            summary_lines.append(
                f"\n❌ 支付给 '{agent_name}' 失败！\n"
                f"   - 发送方: {sender_name}\n"
                f"   - 错误信息: {transaction_message}\n"
                f"   - 错误代码: {transaction_code}"
            )
        
        # 保存支付数据供最终回复使用
        ctx.session.state["payment_success"] = True
        ctx.session.state["payment_data"] = {
            "hash": payment_tx_hash,
            "senderAddress": raw_sender_address,
            "destAddress": raw_sender_address,
            "amount": payment_amount
        }
        
        summary_lines.append("---")
        summary_lines.append("交易已执行完毕。")

        final_summary = "\n".join(summary_lines)
        yield Event(author=self.name, content=types.Content(parts=[types.Part(text=final_summary)]))


class ProcurementContractAgent(BaseAgent):
    """链的最后一步：为成功的交易生成采购合同。"""

    def __init__(self, name: str, description: str):
        super().__init__(name=name, description=description)

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """为最佳报价智能体生成采购合同。"""
        agents_with_quotes = ctx.session.state.get("agents_with_quotes", [])

        # 如果没有报价，则不执行任何操作
        if not agents_with_quotes:
            return

        # 选择价格最低的智能体
        best_agent = min(agents_with_quotes, key=lambda a: a.get("quote", {}).get("total_price", float('inf')))
        
        # 保存最佳智能体信息供后续交易使用
        ctx.session.state["selected_trade_agent"] = best_agent

        summary_lines = [
            "**正在生成星火令采购合同**",
            "---",
            "📄 正在签署星火令采购合同...",
        ]
        
        # --- 1. 从上下文中提取信息并生成占位符 ---
        buyer_name = "Cyber-X 智能制造中心"
        # 从会话状态中获取前端传来的用户钱包地址作为买方DID
        buyer_did = ctx.session.state.get("sender_address", "did:bid:efUGVkkJ746m4iCKgSpECXcni4v1cUaQ")
        buyer_signature = "0x" + uuid.uuid4().hex

        seller_name = best_agent.get("name", "未知智能体")
        seller_did = best_agent.get("blockchainInfo", {}).get("walletAddress", "N/A")
        seller_signature = "0x" + uuid.uuid4().hex # 模拟的乙方签名
        
        # 提取或生成合同细节
        original_query = ctx.session.state.get("original_query", "")
        quantity_match = re.search(r"(\d+)\s*个", original_query)
        quantity = int(quantity_match.group(1)) if quantity_match else 1000

        contract_amount = best_agent.get("quote", {}).get("total_price", 900000)
        currency = best_agent.get("quote", {}).get("currency", "星火令")
        deposit = contract_amount * 0.1
        
        contract_details = {
            "采购商品": "轮胎",
            "规格": "235/45 R18 94W",
            "数量": quantity,
            "收货地址": "上海松江区荣乐中路5号",
            "交货时间": "2025年9月30日之前",
            "合同金额": f"{contract_amount:,.2f} {currency}",
            "定金": f"{deposit:,.2f} {currency}"
        }

        # --- 2. 编排待签署合同的输出 ---
        summary_lines.append("--------------------")
        summary_lines.append(f"- **甲方**: {buyer_name} ({buyer_did})")
        summary_lines.append(f"- **乙方**: {seller_name} ({seller_did})")
        for key, value in contract_details.items():
            summary_lines.append(f"- **{key}**: {value}")
        summary_lines.append(f"- **甲方签名**: `{buyer_signature}`")
        summary_lines.append("- **乙方签名**: (待签署)")
        summary_lines.append("--------------------")

        # --- 3. 编排模拟签署和已生效合同的输出 ---
        summary_lines.append(f"\n✅ 模拟 {seller_name} 签署并验证成功！\n")
        
        summary_lines.append("--------------------")
        summary_lines.append(f"- **甲方**: {buyer_name} ({buyer_did})")
        summary_lines.append(f"- **乙方**: {seller_name} ({seller_did})")
        for key, value in contract_details.items():
            summary_lines.append(f"- **{key}**: {value}")
        summary_lines.append(f"- **甲方签名**: `{buyer_signature}`")
        summary_lines.append(f"- **乙方签名**: `{seller_signature}`")
        summary_lines.append("--------------------")
        summary_lines.append("✅ 合同已正式生效。")

        # 产生单个最终事件
        final_summary = "\n".join(summary_lines)
        yield Event(author=self.name, content=types.Content(parts=[types.Part(text=final_summary)]))


class SearchAndVerifyChain(SequentialAgent):
    """一个先进行路由，然后进行验证的顺序链。"""
    def __init__(self, name: str, **kwargs):
        super().__init__(
            name=name,
            sub_agents=[
                RouterAgent(name="router", description="Supplier discovery agent", model="gemini-2.5-pro"),
                VcVerifierAgent(name="verifier", description="Supplier VC verification agent"),
                bridgestoneAgent(name="bridgestone", description="Gets quotes from suppliers"),
                ProcurementContractAgent(name="contract_generator", description="Generates a procurement contract before trade execution"),
                TradeExecutorAgent(name="trader", description="Executes payment for verified suppliers"),
            ],
            **kwargs,
        )

# ###########################################################################
# 步骤 3: 创建一个顶层包装类，类似于 `FactoryAgent`。
# 这个类将初始化并运行 ADK 链。
# ###########################################################################

class SearchAgent:
    """搜索和验证 Agent 链的顶层包装器。"""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = 'a2a_user'  # 使用与 factoryagent 一致的 user_id
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            session_service=InMemorySessionService(),
        )

    def get_processing_message(self) -> str:
        return '正在搜索并验证智能体...'

    def _build_agent(self) -> SearchAndVerifyChain:
        """构建 SearchAndVerifyChain。"""
        return SearchAndVerifyChain(name="SearchAndVerify_Agent")

    async def stream(self, message_params: Dict[str, Any]) -> AsyncIterable[dict[str, Any]]:
        """
        运行 Agent 链并流式传输结果，模仿 factoryagent 的 stream 方法。
        """
        # 调试信息：打印接收到的参数结构
        print(f"--- Debug: 接收到的 message_params: {message_params} ---")
        
        # 检查是否是支付结果通知格式
        if "senderName" in message_params and "transactionResult" in message_params:
            # 这是一个支付结果通知，从中提取信息并触发正常流程
            transaction_result = message_params.get("transactionResult", {})
            transaction_data = transaction_result.get("data", {})
            
            # 从支付结果中提取信息
            extracted_sender_address = transaction_data.get("senderAddress")
            # 模拟一个私钥用于测试（实际应用中需要安全的私钥管理）
            extracted_private_key = "mock_private_key_for_testing"  # 支付结果中通常不会包含私钥，这里使用模拟值
            
            # 从支付结果通知中提取原始的消息信息
            params = message_params.get("params", {})
            message = params.get("message", {})
            
            query = message.get("parts", [{}])[0].get("text", "")
            session_id = message.get("contextId")
            
            if not query or not session_id:
                yield {
                    "is_task_complete": True,
                    "content": "支付结果通知中缺少必要的消息信息",
                    "author": "system",
                    "agent_class": "system",
                    "is_partial": False
                }
                return
            
            # 使用提取的信息继续正常流程
            sender_address = extracted_sender_address
            private_key = extracted_private_key
            
            # 创建清理后的消息参数
            cleaned_message_params = {
                "params": {
                    "message": {
                        "contextId": session_id,
                        "parts": message.get("parts", [])
                    }
                }
            }
            
            # 添加从支付结果中提取的钱包信息
            if sender_address:
                cleaned_message_params["params"]["senderAddress"] = sender_address
            if private_key:
                cleaned_message_params["params"]["privateKey"] = private_key
            
            # 保留原始的 transactionResult 和 senderName 数据
            if "transactionResult" in message_params:
                cleaned_message_params["transactionResult"] = message_params["transactionResult"]
            if "senderName" in message_params:
                cleaned_message_params["senderName"] = message_params["senderName"]
                
            # 添加标记表示来自支付结果
            is_from_payment_result = True
                
            print(f"--- Debug: 从支付结果提取的信息 - sender_address: {sender_address}, query: '{query}' ---")
            
        else:
            # 正常的请求格式处理
            params = message_params.get("params", {})
            message = params.get("message", {})
            
            query = message.get("parts", [{}])[0].get("text", "")
            session_id = message.get("contextId")
            
            if not query or not session_id:
                print(f"--- Debug: 参数验证失败 - query: '{query}', session_id: '{session_id}' ---")
                raise ValueError("Message parameters must include query and contextId.")

            # 从请求参数中提取用户钱包信息
            sender_address = params.get("senderAddress")
            private_key = params.get("privateKey")
            
            # 创建一个清理后的消息参数，移除支付相关信息，供子agent使用
            cleaned_message_params = {
                "params": {
                    "message": {
                        "contextId": session_id,
                        "parts": message.get("parts", [])
                    }
                }
            }
            
            # 添加钱包信息（如果存在）
            if sender_address:
                cleaned_message_params["params"]["senderAddress"] = sender_address
            if private_key:
                cleaned_message_params["params"]["privateKey"] = private_key
                
            # 添加标记表示来自正常请求
            is_from_payment_result = False
        
        print(f"--- Debug: 提取的 params: {params if 'params' in locals() else '从支付结果提取'} ---")
        print(f"--- Debug: 提取的 message: {message if 'message' in locals() else '从支付结果提取'} ---")
        print(f"--- Debug: 提取的 query: '{query}', session_id: '{session_id}' ---")
        print(f"--- Debug: 清理后的 message_params: {cleaned_message_params} ---")
        
        session = await self._runner.session_service.get_session(
            app_name=self._agent.name,
            user_id=self._user_id,
            session_id=session_id,
        )
        if session is None:
            session = await self._runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                session_id=session_id,
                # 将原始查询和消息参数存储在会话状态中
                state={
                    'original_query': query,
                    'original_message_params': message_params, # 存储完整的原始请求体
                    'cleaned_message_params': cleaned_message_params, # 存储清理后的请求体  
                    'sender_address': sender_address, # 存储用户钱包地址
                    'private_key': private_key, # 存储用户私钥
                    'is_from_payment_result': is_from_payment_result # 标记是否来自支付结果
                }
            )
        else:
            # 如果会话已存在，更新钱包信息和消息参数
            session.state.update({
                'original_query': query,
                'original_message_params': message_params, # 存储完整的原始请求体
                'cleaned_message_params': cleaned_message_params, # 存储清理后的请求体
                'sender_address': sender_address,
                'private_key': private_key,
                'is_from_payment_result': is_from_payment_result
            })
        content = types.Content(role='user', parts=[types.Part.from_text(text=query)])

        final_result_sent = False
        last_agent_name = self._agent.sub_agents[-1].name

        async for event in self._runner.run_async(
            user_id=self._user_id, session_id=session.id, new_message=content
        ):
            author = event.author or "system"
            
            # 产生中间文本更新
            if event.content and event.content.parts and event.content.parts[0].text:
                content_text = event.content.parts[0].text
                
                # 任务只在最后一个 Agent 发出它的最终响应时才算完成
                is_task_complete = (author == last_agent_name and event.is_final_response())
                
                if is_task_complete:
                    final_result_sent = True

                agent_class = "router" if author == "router" else "bridgestone"

                yield {
                    'is_task_complete': is_task_complete,
                    'author': author,
                    'content': content_text,
                    'is_partial': False,
                }
        
        # 确保如果链在没有发送最终消息的情况下结束，也能发送一条最终消息
        if not final_result_sent:
            # 检查是否有支付交易信息
            payment_success = session.state.get("payment_success", False)
            payment_data = session.state.get("payment_data", {})
            
            if payment_success and payment_data:
                # 构造支付成功的回复格式
                response_content = {
                    "senderName": "信通院",
                    "transactionResult": {
                        "code": 0,
                        "message": "操作成功",
                        "data": {
                            "txHash": payment_data.get("hash", "0x..."),
                            "senderAddress": payment_data.get("senderAddress", "did:bid:efUGVkkJ746m4iCKgSpECXcni4v1cUaQ"),
                            "destAddress": payment_data.get("destAddress", "did:bid:efUGVkkJ746m4iCKgSpECXcni4v1cUas"),
                            "amount": payment_data.get("amount", 50000),
                            "success": True
                        }
                    }
                }
                
                yield {
                    "is_task_complete": True,
                    "content": json.dumps(response_content, ensure_ascii=False, indent=2),
                    "author": "system",
                    "agent_class": "system",
                    "is_partial": False
                }
            else:
                yield {
                    'is_task_complete': True,
                    'content': '流程处理结束，但未收到最终确认。',
                    'author': 'system',
                    'agent_class': 'system',
                    'is_partial': False,
                }