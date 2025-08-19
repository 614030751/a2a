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
from agent import PlanAgent
from agent_executor import PlanAgentExecutor
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """当 API 密钥缺失时引发的异常。"""


@click.command()
@click.option('--host', default='0.0.0.0')
@click.option('--port', default=8020)
def main(host, port):
    try:
        if not os.getenv('GOOGLE_API_KEY'):
            raise MissingAPIKeyError('未设置 GOOGLE_API_KEY 环境变量。')

        capabilities = AgentCapabilities(streaming=True)
        skill = AgentSkill(
            id='plan_agent',
            name='生产计划制定',
            description='一个能够根据用户输入，制定详细生产计划的代理。',
            tags=['计划', '生产', '任务拆解'],
            examples=[
                '生产计划：本次需要试生产500辆Cyber-X新能源汽车。',
                '为1000辆车制定生产和物料计划。'
            ],
        )
        agent_card = AgentCard(
            name='生产计划代理',
            description='一个能够将高级生产目标，拆解为具体执行步骤的代理。',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=PlanAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=PlanAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        request_handler = DefaultRequestHandler(
            agent_executor=PlanAgentExecutor(),
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
