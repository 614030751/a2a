import uuid

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    Message,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import new_task
from a2a.utils.errors import ServerError

from agent import TireTransportAgent


class TireTransportAgentExecutor(AgentExecutor):
    """Tire Transport AgentExecutor."""

    def __init__(self):
        self.agent = TireTransportAgent()

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
            if item.get('is_task_complete'):
                await updater.add_artifact(
                    [Part(root=TextPart(text=item['content']))],
                    name='tire_transport_result',
                )
                await updater.complete()
                break

            custom_message = Message(
                messageId=f"msg-{uuid.uuid4()}",
                contextId=task.context_id,
                role="agent",
                parts=[Part(root=TextPart(text=item['content']))],
                metadata={
                    "author": item.get('author', 'system'),
                    "is_partial": item.get('is_partial', False),
                },
            )

            await updater.update_status(
                TaskState.working,
                message=custom_message,
            )

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())
