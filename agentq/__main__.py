import asyncio

from agentq.core.agent.browser_nav_agent import BrowserNavAgent
from agentq.core.agent.planner_agent import PlannerAgent
from agentq.core.agent.agentq import AgentQ
from agentq.core.models.models import State
from agentq.core.orchestrator.orchestrator import Orchestrator


async def main():
    # Define state machine
    state_to_agent_map = {
        State.PLAN: PlannerAgent(),
        State.BROWSE: BrowserNavAgent(),
        State.CONTINUE: AgentQ(),
    }

    orchestrator = Orchestrator(state_to_agent_map=state_to_agent_map)
    await orchestrator.start()


if __name__ == "__main__":
    asyncio.run(main())