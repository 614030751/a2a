import logging
import os
import json
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# We will be importing the top-level SearchAgent class
from agent import SearchAgent
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

# Load environment variables from .env file
load_dotenv()

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- API Key Check ---
# Ensure that the necessary API keys are set in the environment.
if not os.getenv("GOOGLE_API_KEY"):
    logger.error("GOOGLE_API_KEY environment variable not set.")
    exit(1)

# --- FastAPI App Setup ---
app = FastAPI()

# Configure CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
    expose_headers=["*"],
)

# Instantiate our search agent
search_agent_instance = SearchAgent()


# --- AgentCard and API Endpoints ---

def get_agent_card(host: str, port: int) -> AgentCard:
    """Creates and returns the AgentCard for our search agent."""
    capabilities = AgentCapabilities(streaming=True)
    skill = AgentSkill(
        id="search_and_verify_agents",
        name="Search and Verify Agents",
        description="Searches for supplier agents and verifies their credentials based on natural language.",
        tags=["search", "discovery", "verification", "supplier"],
        examples=[
            "I need to source tire suppliers",
            "Help me find battery manufacturers",
            "Look for agents that can handle logistics",
        ],
    )
    return AgentCard(
        name="Supplier Search & Verification Agent",
        description="A multi-step agent for finding and verifying supplier agents on the platform.",
        url=f"http://{host}:{port}/AgentApi/getmessages/",
        version="1.0.0",
        defaultInputModes=SearchAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=SearchAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
    )

@app.get("/.well-known/agent.json")
async def get_well_known_json(request: Request):
    """Endpoint to serve the agent's AgentCard for discovery."""
    host = request.client.host
    port = 8032 # The port this service runs on
    agent_card = get_agent_card(host, port)
    return JSONResponse(content=agent_card.model_dump(by_alias=True))


@app.get("/AgentApi/agents")
async def get_agents():
    """Returns the sub-agents involved in the search and verification process."""
    agent_list = [
        {"name": "router", "description": "浏览器智能体"},
        {"name": "horse", "description": "马牌轮胎智能体"},
        {"name": "michelin", "description": "米其林轮胎智能体"},
        {"name": "bridgestone", "description": "普利司通轮胎智能体"},
      
    ]
    return JSONResponse(content={
        "total_agents": len(agent_list),
        "agents": agent_list
    })


@app.post("/AgentApi/getmessages/")
async def stream_messages(request: Request):
    """
    Handles streaming chat requests using FastAPI's StreamingResponse (SSE),
    matching the structure of factoryagent.
    """
    try:
        body = await request.json()
        
        # Pass the full request body 'body' to the agent's stream method
        logger.info(f"Forwarding full request to agent for session: {body.get('params', {}).get('message', {}).get('contextId')}")

        async def event_generator():
            """
            Generator that calls the agent's stream method and formats
            each item into a Server-Sent Event (SSE) string.
            """
            try:
                # The core call to our agent's stream method, passing the full body
                async for item in search_agent_instance.stream(body):
                    yield f"data: {json.dumps(item)}\n\n"
            except Exception as e:
                logger.error(f"Error during agent execution: {e}", exc_info=True)
                error_item = {
                    'is_task_complete': True,
                    'author': 'system',
                    'content': f"An error occurred: {e}",
                }
                yield f"data: {json.dumps(error_item)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return JSONResponse(content={"error": "Failed to process request", "details": str(e)}, status_code=500)

@app.post("/pay")
async def pay():
    """模拟支付接口"""
    logger.info("接收到 /pay 接口的请求。")
    return JSONResponse(content=True)

@app.post("/contract")
async def contract():
    """模拟合同接口"""
    logger.info("接收到 /contract 接口的请求。")
    return JSONResponse(content=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8032)
