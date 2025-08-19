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
from .agent import BatterySupplyAgent
from .agent_executor import BatterySupplyAgentExecutor
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


@click.command()
@click.option('--host', default='0.0.0.0')
@click.option('--port', default=8029)
def main(host, port):
    try:
        if not os.getenv('GOOGLE_API_KEY'):
            raise MissingAPIKeyError('GOOGLE_API_KEY environment variable not set.')

        capabilities = AgentCapabilities(streaming=True)
        skill = AgentSkill(
            id='battery_supply',
            name='Battery Supply Management',
            description='Manage battery inventory based on production needs.',
            tags=['battery', 'supply', 'inventory', 'factory'],
            examples=[
                '为生产500辆电动汽车提供电池。',
            ],
        )
        agent_card = AgentCard(
            name='Battery Supply Agent',
            description='A standalone agent for managing battery supply in a factory simulation.',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=BatterySupplyAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=BatterySupplyAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        request_handler = DefaultRequestHandler(
            agent_executor=BatterySupplyAgentExecutor(),
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
