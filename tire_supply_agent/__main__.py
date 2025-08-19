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
from agent_executor import TireSupplyAgentExecutor
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """当 API 密钥缺失时引发的异常。"""


@click.command()
@click.option('--host', default='0.0.0.0')
@click.option('--port', default=8021) # 默认端口
def main(host, port):
    try:
        if not os.getenv('GOOGLE_API_KEY'):
            raise MissingAPIKeyError('未设置 GOOGLE_API_KEY 环境变量。')

        # 在使用前直接导入 Agent 类
        from agent import TireSupplyAgent

        capabilities = AgentCapabilities(streaming=True)
        skill = AgentSkill(
            id='tire_supply',
            name='通用轮胎供应管理',
            description='根据生产需求管理轮胎库存。',
            tags=['轮胎', '供应', '库存', '工厂'],
            examples=[
                '为生产500辆电动汽车提供轮胎。',
                '我需要采购100个轮胎，请报价。'
            ],
        )
        agent_card = AgentCard(
            name='通用轮胎供应商',
            description='一个独立的代理，负责在模拟环境中管理轮胎的供应。',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=TireSupplyAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=TireSupplyAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        request_handler = DefaultRequestHandler(
            agent_executor=TireSupplyAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )
        import uvicorn

        uvicorn.run(server.build(), host=host, port=port)
    except MissingAPIKeyError as e:
        logger.error(f'Error: {e}')
        exit(1)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        exit(1)


if __name__ == '__main__':
    main()
