import asyncio

from playwright.async_api import Page

from agentq.core.agent.agentq import AgentQ
from agentq.core.agent.agentq_actor import AgentQActor
from agentq.core.agent.agentq_critic import AgentQCritic
from agentq.core.agent.browser_nav_agent import BrowserNavAgent
from agentq.core.agent.planner_agent import PlannerAgent
from agentq.core.models.models import State
from agentq.core.orchestrator.orchestrator import Orchestrator

state_to_agent_map = {
    State.PLAN: PlannerAgent(),
    State.BROWSE: BrowserNavAgent(),
    State.AGENTQ_BASE: AgentQ(),
    State.AGENTQ_ACTOR: AgentQActor(),
    State.AGENTQ_CRITIC: AgentQCritic(),
}


async def run_agent(command):
    orchestrator = Orchestrator(state_to_agent_map=state_to_agent_map, eval_mode=True)
    await orchestrator.start()
    page: Page = await orchestrator.playwright_manager.get_current_page()
    await page.set_extra_http_headers({"User-Agent": "AgentQ-Bot"})
    await page.goto(
        "http://localhost:3000/abc", wait_until="networkidle", timeout=30000
    )
    result = await orchestrator.execute_command(command)
    return result


def run_agent_sync(command):
    if asyncio.get_event_loop().is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    return loop.run_until_complete(run_agent(command))


async def main():
    orchestrator = Orchestrator(state_to_agent_map=state_to_agent_map)
    await orchestrator.start()


if __name__ == "__main__":
    asyncio.run(main())
