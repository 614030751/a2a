# Battery Transport Agent

This agent is responsible for planning the transport of batteries.

## Features

-   **Transport Planning**: Based on the demand, it plans the optimal route and arranges for the appropriate vehicles.
-   **Cost and Time Estimation**: Provides an estimate of the transportation cost and time.
-   **A2A Interface**: Exposes an a2a interface for other agents to interact with it.

## To Run

To run the agent, install the dependencies and run the main module:

```bash
poetry install
poetry run python -m battery_transport_agent
```