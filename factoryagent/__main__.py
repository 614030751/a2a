import logging
import os
import json
import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from agent import FactoryAgent
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Check for API Key ---
if not os.getenv("GOOGLE_API_KEY"):
    logger.error("GOOGLE_API_KEY environment variable not set.")
    exit(1)

# --- FastAPI App Setup ---
app = FastAPI()

# Add CORS middleware to allow all origins, methods, and headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Instantiate the agent
factory_agent = FactoryAgent()

def get_agent_card(host: str, port: int) -> AgentCard:
    """Creates and returns the AgentCard."""
    capabilities = AgentCapabilities(streaming=True)
    skill = AgentSkill(
        id="simulate_factory_supply_chain",
        name="Simulate Factory Supply Chain",
        description=(
            "Simulates a multi-agent factory supply chain for vehicle production, "
            "including planning, component sourcing, transportation, and payment."
        ),
        tags=[
            "factory",
            "simulation",
            "supply-chain",
            "multi-agent",
            "工厂",
            "供应链",
        ],
        examples=[
            "生产100辆汽车",
            "Simulate the production of 50 vehicles.",
        ],
    )
    return AgentCard(
        name="Factory Simulation Agent",
        description="A multi-agent system that simulates a factory supply chain.",
        url=f"http://{host}:{port}/AgentApi/getmessages/",
        version="1.0.0",
        defaultInputModes=FactoryAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=FactoryAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
    )

@app.get("/.well-known/agent.json")
async def get_well_known_json(request: Request):
    """
    Endpoint to serve the agent's AgentCard, allowing for discovery.
    """
    host = request.client.host
    # This assumes the server is running on the default port or the port is known.
    # For a more robust solution, the port might need to be configured.
    port = 10002 
    agent_card = get_agent_card(host, port)
    return JSONResponse(content=agent_card.model_dump(by_alias=True))


@app.get("/AgentApi/agents")
async def get_agents():
    """
    Returns the total number of agents and an ordered list of all sub-agents
    with their names and descriptions.
    """
    # The list is ordered according to the execution flow in FactoryChain
    agent_list = [
        {"name": "plan_agent", "description": "任务规划智能体"},
        {"name": "tire_supply_agent", "description": "轮胎供应智能体"},
        {"name": "tire_transport_agent", "description": "轮胎运输智能体"},
        {"name": "tire_trade", "description": "轮胎交易执行智能体"},
        {"name": "tire_trade_summary", "description": "轮胎交易总结智能体"},
        {"name": "battery_supply_agent", "description": "电池供应智能体"},
        {"name": "battery_transport_agent", "description": "电池运输智能体"},
        {"name": "battery_trade", "description": "电池交易执行智能体"},
        {"name": "battery_trade_summary", "description": "电池交易总结智能体"},
        {"name": "frame_supply_agent", "description": "车架供应智能体"},
        {"name": "frame_transport_agent", "description": "车架运输智能体"},
        {"name": "frame_trade", "description": "车架交易执行智能体"},
        {"name": "frame_trade_summary", "description": "车架交易总结智能体"},
    ]
    



    return JSONResponse(content={
        "total_agents": len(agent_list),
        "agents": agent_list
    })


@app.post("/AgentApi/getmessages/")
async def stream_messages(request: Request):
    """
    Handles streaming chat requests using FastAPI's StreamingResponse (SSE).
    """
    try:
        body = await request.json()
        
        # Extract message from the "params" field of the JSON-RPC like structure
        message = body.get("params", {}).get("message", {})
        if not message:
            # Fallback for the original A2A structure for compatibility
            message = body.get("message", {})
        
        # Extract query and contextId from the message
        query_part = message.get("parts", [{}])[0]
        query = query_part.get("text") or query_part.get("root", {}).get("text", "")
        session_id = message.get("contextId")

        if not query or not session_id:
            raise ValueError("Missing 'query' or 'contextId' in request.")

        logger.info(f"Received query: '{query}' for session: {session_id}")

        async def event_generator():
            """
            This generator function calls the agent's stream method and formats
            each yielded item into a Server-Sent Event (SSE) string.
            """
            try:
                async for item in factory_agent.stream(query, session_id):
                    # SSE format: "data: <json_string>\n\n"
                    yield f"data: {json.dumps(item)}\n\n"
            except Exception as e:
                logger.error(f"Error during agent execution: {e}", exc_info=True)
                error_item = {
                    'is_task_complete': True,
                    'author': 'system',
                    'content': f"An error occurred: {e}",
                    'is_partial': False
                }
                yield f"data: {json.dumps(error_item)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return {"error": "Failed to process request", "details": str(e)}, 500


if __name__ == "__main__":
    # Use the same port as before for consistency.
    uvicorn.run(app, host="0.0.0.0", port=10002) 
