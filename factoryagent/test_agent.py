import requests
import json
import uuid

def test_factory_agent():
    """根据a2a-sdk规范测试工厂代理"""

    server_base_url = "http://localhost:10002"
    well_known_url = f"{server_base_url}/.well-known/agent.json"
    
    proxies = {
        "http": None,
        "https": None,
    }
    
    print("🤖 A2A Agent Test Client")
    print("⚡️ 已禁用系统代理以确保直接连接到本地服务器。")
    print("-" * 50)

    try:
        # 步骤 1: 获取 Agent Card
        print(f"🔍 正在从 {well_known_url} 获取 Agent Card...")
        agent_card_response = requests.get(well_known_url, proxies=proxies)
        agent_card_response.raise_for_status()
        agent_card = agent_card_response.json()
        print("✅ 成功获取 Agent Card!")
        
        tasks_base_url = agent_card.get("url")
        if not tasks_base_url:
            raise ValueError("Agent Card 中缺少 'url' 字段。")

        # 客户端修正：将服务器返回的 0.0.0.0 地址替换为可连接的 localhost
        if "://0.0.0.0" in tasks_base_url:
            tasks_base_url = tasks_base_url.replace("://0.0.0.0", "://localhost")
            print(f"🔧 (客户端修正) 将服务器地址从 0.0.0.0 修正为: {tasks_base_url}")

        # 步骤 2: 构造任务请求
        # 使用 rstrip('/') 确保在拼接时不会出现双斜杠
        invoke_url = f"{tasks_base_url.rstrip('/')}/tasks/sendSubscribe"
        test_message = "请帮我生产10辆汽车，需要完整的供应链流程"
        
        payload = {
            "task_id": str(uuid.uuid4()),
            "message": {
                "role": "user",
                "parts": [{"text": test_message}]
            }
        }

        print(f"📡 准备向 {invoke_url} 发送任务...")
        print("📦 发送的载荷:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("-" * 50)

        # 步骤 3: 发送请求并处理流式响应
        response = requests.post(
            invoke_url,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            stream=True,
            proxies=proxies
        )
        response.raise_for_status()

        print("✅ 请求成功，正在接收实时事件流...")
        print("-" * 50)
        
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                print(decoded_line)
        
        print("\n🏁 流结束。")

    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        if e.response is not None:
            print(f"响应内容: {e.response.text}")
    except json.JSONDecodeError:
        print("❌ 解析 Agent Card 失败，响应不是有效的 JSON。")
    except ValueError as e:
        print(f"❌ 处理 Agent Card 数据时出错: {e}")
    except Exception as e:
        print(f"❌ 测试过程中发生未知错误: {e}")

if __name__ == "__main__":
    test_factory_agent() 