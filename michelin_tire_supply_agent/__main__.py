import logging
import os

import click

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent import MichelinTireSupplyAgent
from agent_executor import MichelinTireSupplyAgentExecutor
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """当 API 密钥缺失时引发的异常。"""


@click.command()
@click.option('--host', default='0.0.0.0')
@click.option('--port', default=8022)
def main(host, port):
    """主函数，用于启动 Agent 服务器。"""
    try:
        # 检查必要的环境变量是否设置
        if not os.getenv('GOOGLE_API_KEY'):
            raise MissingAPIKeyError('未设置 GOOGLE_API_KEY 环境变量。')

        # 定义 Agent 的能力
        capabilities = AgentCapabilities(streaming=True)
        
        # 定义 Agent 的技能
        skill = AgentSkill(
            id='michelin_tire_supply',
            name='米其林轮胎供应管理',
            description='根据生产需求管理高品质的米其林轮胎库存。',
            tags=['米其林', '轮胎', '供应', '高端'],
            examples=[
                '为生产500辆高端电动汽车提供米其林轮胎。',
                '我需要采购1000个米其林轮胎，请报价。'
            ],
        )
        
        # 定义 Agent 的名片
        agent_card = AgentCard(
            name='米其林轮胎供应商',
            description='一个独立的代理，负责在模拟环境中管理高端米其林轮胎的供应。',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=MichelinTireSupplyAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=MichelinTireSupplyAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        
        # 设置请求处理器
        request_handler = DefaultRequestHandler(
            agent_executor=MichelinTireSupplyAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )
        
        # 创建并配置服务器应用
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )
        
        # 动态导入 uvicorn 以避免全局范围的问题
        import uvicorn

        # 启动服务器
        uvicorn.run(server.build(), host=host, port=port)

    except MissingAPIKeyError as e:
        logger.error(f'错误: {e}')
        exit(1)
    except Exception as e:
        logger.error(f'服务器启动期间发生错误: {e}')
        exit(1)


if __name__ == '__main__':
    main()
