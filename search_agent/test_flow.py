import asyncio
import json
import httpx
import uuid
from typing import Dict, Any

# --- 配置 ---
BASE_URL = "http://43.162.109.76:8032"
# 初始采购请求
INITIAL_PROMPT = "我需要采购200个225/60R16规格的轮胎，要求品牌为米其林或普利司通。"
# 你的用户ID（可以任意设置）
USER_ID = "test_user_12345"
# 为这次测试流程生成一个独一无二的会话ID
SESSION_ID = f"session_{uuid.uuid4()}"


async def run_test_flow():
    """
    完整模拟并测试三阶段采购流程的客户端。
    """
    print("=================================================")
    print("🚀 [阶段 1/3] 开始：发起采购，获取报价方案...")
    print(f"   请求内容: {INITIAL_PROMPT}")
    print("=================================================\n")

    best_agent_proposal = None
    
    try:
        # --- 步骤 1: 调用 /AgentApi/getmessages/ 获取报价 ---
        url = f"{BASE_URL}/AgentApi/getmessages/"
        payload = {
            "params": {
                "message": {
                    "contextId": SESSION_ID,
                    "parts": [{"text": INITIAL_PROMPT}]
                }
            }
        }
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    print(f"❌ 错误: 初始请求失败，状态码 {response.status_code}")
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        try:
                            data_str = line[len("data:"):].strip()
                            if not data_str:
                                continue
                            
                            data = json.loads(data_str)
                            author = data.get("author", "system")
                            content = data.get("content", "")
                            
                            print(f"🤖 [ {author.upper()} ]:")
                            print(content)
                            print("-" * 20)

                            # --- 关键：从最终输出中提取交易提案 ---
                            if data.get('is_task_complete') and author == 'quotation':
                                proposal_match = re.search(r"```json\n(\{.*?\})\n```", content, re.DOTALL)
                                if proposal_match:
                                    best_agent_proposal = json.loads(proposal_match.group(1))
                                    print("\n✅ 成功从报价Agent的输出中提取到交易提案！")
                        except json.JSONDecodeError:
                            print(f"⚠️ 无法解析的行: {line}")
                            continue
    except httpx.RequestError as e:
        print(f"❌ 错误: 连接到Agent服务失败 - {e}")
        return

    if not best_agent_proposal:
        print("\n❌ 错误: 未能获取到有效的交易提案，测试终止。")
        return

    print("\n\n=================================================")
    print("💰 [阶段 2/3] 开始：执行独立支付...")
    print("=================================================\n")

    trade_receipt = None
    
    try:
        # --- 步骤 2: 调用 /pay 接口执行支付 ---
        payment_url = f"{BASE_URL}/pay"
        payment_payload = {
            "destAddress": best_agent_proposal.get("blockchainInfo", {}).get("walletAddress"),
            "amount": best_agent_proposal.get("quote", {}).get("total_price")
        }

        if not payment_payload["destAddress"] or payment_payload["amount"] is None:
            print("❌ 错误: 交易提案中缺少钱包地址或金额。")
            return
            
        print(f"   准备支付 -> 目标: {payment_payload['destAddress']}, 金额: {payment_payload['amount']}\n")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(payment_url, json=payment_payload)

            if response.status_code == 200:
                trade_receipt = response.json()
                print("✅ 支付成功！")
                print("   交易收据:")
                print(json.dumps(trade_receipt, indent=2, ensure_ascii=False))
            else:
                print(f"❌ 支付失败，状态码: {response.status_code}")
                print("   错误详情:")
                try:
                    print(response.json())
                except json.JSONDecodeError:
                    print(response.text)
                # 即使支付失败，我们也构造一个失败的收据来继续流程
                trade_receipt = {"status": "failed", "error": response.json().get("detail", "支付失败")}

    except httpx.RequestError as e:
        print(f"❌ 错误: 连接到支付接口失败 - {e}")
        return

    if not trade_receipt:
        print("\n❌ 错误: 未能获取到交易收据，测试终止。")
        return

    print("\n\n=================================================")
    print("📝 [阶段 3/3] 开始：注入交易结果，继续流程...")
    print("=================================================\n")

    try:
        # --- 步骤 3: 调用 /continue 接口继续流程 ---
        continue_url = f"{BASE_URL}/continue"
        continue_payload = {
            "contextId": SESSION_ID,
            "trade_receipt": trade_receipt
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", continue_url, json=continue_payload) as response:
                if response.status_code != 200:
                    print(f"❌ 错误: 继续流程请求失败，状态码 {response.status_code}")
                    return
                
                print("   已成功注入交易结果，正在监听后续Agent的输出...\n")
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        try:
                            data_str = line[len("data:"):].strip()
                            if not data_str:
                                continue
                            
                            data = json.loads(data_str)
                            author = data.get("author", "system")
                            content = data.get("content", "")
                            
                            print(f"🤖 [ {author.upper()} ]:")
                            print(content)
                            print("-" * 20)
                            
                            if data.get('is_task_complete'):
                                print("\n✅ 整个采购流程已成功完成！")

                        except json.JSONDecodeError:
                            print(f"⚠️ 无法解析的行: {line}")
                            continue

    except httpx.RequestError as e:
        print(f"❌ 错误: 连接到继续接口失败 - {e}")

if __name__ == "__main__":
    asyncio.run(run_test_flow())
