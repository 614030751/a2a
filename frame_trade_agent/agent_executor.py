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
from agent import FrameTradeAgent


class FrameTradeAgentExecutor(AgentExecutor):
    """Frame Trade AgentExecutor."""

    def __init__(self):
        self.agent = FrameTradeAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
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
                        item['updates'], task.context_id, task.id
                    ),
                )
                continue
            
            await updater.add_artifact(
                [Part(root=TextPart(text=item['content']))], name='frame_trade_result'
            )
            await updater.complete()
            break

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())
