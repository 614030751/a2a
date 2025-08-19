# Battery Supply Agent

This agent is responsible for managing the supply of batteries for the factory. It receives production plans, determines the number of batteries required, and coordinates with the (simulated) inventory to fulfill the orders.

This agent runs as a standalone FastAPI service and exposes an A2A (agent-to-agent) communication endpoint.

## Features

- **Order Processing**: Analyzes production plans to determine battery requirements.
- **Inventory Check**: Verifies if the current battery stock is sufficient to meet the demand.
- **A2A Interface**: Provides a standard endpoint for other agents to interact with it.

## Running the Agent

To run the agent, navigate to this directory and run:

```bash
python -m . 
```