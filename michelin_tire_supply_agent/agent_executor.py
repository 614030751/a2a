import json

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError
from agent import MichelinTireSupplyAgent


class MichelinTireSupplyAgentExecutor(AgentExecutor):
    """米其林轮胎供应代理的执行器。"""

    def __init__(self):
        self.agent = MichelinTireSupplyAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        执行代理的核心逻辑。

        Args:
            context: 请求的上下文，包含用户信息和任务详情。
            event_queue: 用于向客户端发送事件的队列。
        """
        query = context.get_user_input()
        task = context.current_task

        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        async for item in self.agent.stream(query, task.context_id):
            if not item['is_task_complete']:
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        item['content'], task.context_id, task.id
                    ),
                )
                continue
            
            await updater.add_artifact(
                [Part(root=TextPart(text=item['content']))], name='michelin_supply_result'
            )
            await updater.complete()
            break

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        """取消一个正在执行的任务。"""
        raise ServerError(error=UnsupportedOperationError())
