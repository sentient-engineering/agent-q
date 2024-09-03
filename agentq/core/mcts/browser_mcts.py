import asyncio
from typing import List, NamedTuple, Tuple

import numpy as np

from agentq.core.agent.agentq_actor import AgentQActor
from agentq.core.agent.agentq_critic import AgentQCritic
from agentq.core.agent.vision_agent import VisionAgent
from agentq.core.skills.get_screenshot import get_screenshot
from agentq.core.agent.base import BaseAgent
from agentq.core.mcts.base import Reasoner, SearchConfig, WorldModel
from agentq.core.mcts.mcts import MCTS, MCTSResult
from agentq.core.models.models import Action as BrowserAction
from agentq.core.models.models import (
    ActionType,
    AgentQActorOutput,
    AgentQCriticInput,
    AgentQCriticOutput,
    AgentQInput,
    TaskWithActions,
    VisionInput, 
    VisionOutput
)
from agentq.core.skills.click_using_selector import click
from agentq.core.skills.enter_text_using_selector import EnterTextEntry, entertext
from agentq.core.skills.get_dom_with_content_type import get_dom_with_content_type
from agentq.core.skills.get_url import geturl
from agentq.core.skills.open_url import openurl
from agentq.core.web_driver.playwright import PlaywrightManager


class BrowserState(NamedTuple):
    dom: str
    url: str
    objective: str
    completed_task: List[str]


class BrowserWorldModel(WorldModel[BrowserState, BrowserAction, str]):
    def __init__(self, objective: str, vision: BaseAgent) -> None:
        super().__init__()
        self.objective = objective
        self.vision = vision
        print(f"[DEBUG] BrowserWorldModel initialized with objective: {self.objective}")

    async def init_state(self) -> BrowserState:
        initial_dom = await self.get_current_dom()
        initial_url = await self.get_current_url()
        print(f"[DEBUG] Initial state created - URL: {initial_url}")
        return BrowserState(dom=initial_dom, url=initial_url, objective=self.objective)

    async def step(
        self, state: BrowserState, action: BrowserAction
    ) -> Tuple[BrowserState, dict]:
        print(f"[DEBUG] Executing step with action: {action}")
        new_dom, new_url = await self.execute_browser_action(action)
        new_completed_tasks = state.completed_task + [str(action)]
        new_state = BrowserState(dom=new_dom, url=new_url, objective=state.objective, completed_task=new_completed_tasks)
        print(f"[DEBUG] New state after step - URL: {new_url}")
        return new_state, {}

    async def is_terminal(self, state: BrowserState) -> bool:
        terminal = await is_terminal(state, self.vision)
        print(f"[DEBUG] Checking if state is terminal: {terminal}")
        return terminal

    async def execute_browser_action(self, action: BrowserAction) -> Tuple[str, str]:
        print(f"[DEBUG] Executing browser action: {action.type}")
        if action.type == ActionType.GOTO_URL:
            await openurl(url=action.website, timeout=action.timeout or 0)
        elif action.type == ActionType.TYPE:
            entry = EnterTextEntry(
                query_selector=f"[mmid='{action.mmid}']", text=action.content
            )
            await entertext(entry)
        elif action.type == ActionType.CLICK:
            await click(
                selector=f"[mmid='{action.mmid}']",
                wait_before_execution=action.wait_before_execution or 0,
            )
        new_dom = await self.get_current_dom()
        new_url = await self.get_current_url()
        print(f"[DEBUG] After action execution - New URL: {new_url}")
        return new_dom, new_url

    async def get_current_dom(self) -> str:
        dom = await get_dom_with_content_type(content_type="all_fields")
        print(f"[DEBUG] Got current DOM (length: {len(dom)})")
        return str(dom)

    async def get_current_url(self) -> str:
        url = await geturl()
        print(f"[DEBUG] Got current URL: {url}")
        return url


class BrowserMCTSSearchConfig(SearchConfig[BrowserState, BrowserAction, str]):
    def __init__(self, actor: BaseAgent, critic: BaseAgent, vision: BaseAgent) -> None:
        super().__init__()
        self.actor = actor
        self.critic = critic
        self.vision = vision
        print("[DEBUG] BrowserMCTSSearchConfig initialized")

    async def get_actions(self, state: BrowserState) -> List[BrowserAction]:
        print("[DEBUG] Getting actions for current state")
        actor_input: AgentQInput = AgentQInput(
            objective=state.objective,
            completed_tasks=state.completed_task,
            current_page_dom=state.dom,
            current_page_url=state.url,
        )
        actor_output: AgentQActorOutput = await self.actor.run(actor_input)

        proposed_tasks: List[TaskWithActions] = actor_output.proposed_tasks
        print(f"[DEBUG] Number of proposed tasks: {len(proposed_tasks)}")

        sorted_actions = await self._sorted_actions(state, proposed_tasks)
        print(f"[DEBUG] Number of sorted actions: {len(sorted_actions)}")

        return sorted_actions

    async def reward(
        self, state: BrowserState, action: BrowserAction, **kwargs
    ) -> Tuple[float, dict]:
        
        if await is_terminal(state=state, vision=self.vision):
            print("[DEBUG] Terminal state reached, reward: 1.0")
            return 1.0, {}
        else:
            print("[DEBUG] Non-terminal state, reward: -0.01")
            return -0.01, {}  # small penalty for each step to encourage shorter path

    async def _sorted_actions(
        self, state: BrowserState, tasks: List[TaskWithActions]
    ) -> List[BrowserAction]:
        actions = [
            task.actions_to_be_performed[0]
            for task in tasks
            if task.actions_to_be_performed
        ]
        print(f"[DEBUG] Actions extracted from tasks: {actions}")
        return actions


async def is_terminal(state: BrowserState, vision: BaseAgent) -> bool:
    # Todo: Implement terminal state using vision
    print("[DEBUG] Checking if state is terminal")
    screenshot = await get_screenshot()
    vision_input: VisionInput = VisionInput(objective=state.objective)
    vision_output: VisionOutput = await vision.run(vision_input, screenshot)
    print(f"[DEBUG] Output of vision LLM {vision_output.is_terminal}")
    return vision_output.is_terminal


class BrowserMCTSWrapper(Reasoner[BrowserState, BrowserAction, str]):
    def __init__(
        self,
        objective: str,
        actor: BaseAgent,
        critic: BaseAgent,
        vision: BaseAgent,
        n_iterations: int = 1,
        exploration_weight: float = 1.0,
    ):
        world_model = BrowserWorldModel(objective, vision)
        search_config = BrowserMCTSSearchConfig(actor, critic, vision)
        search_algo = MCTS(
            n_iters=n_iterations,
            w_exp=exploration_weight,
            cum_reward=sum,
            calc_q=np.mean,
            simulate_strategy="random",
            output_strategy="max_reward",
            depth_limit=20,
        )
        super().__init__(world_model, search_config, search_algo)
        print(f"[DEBUG] BrowserMCTSWrapper initialized with objective: {objective}")

    async def __call__(self) -> MCTSResult:
        print("[DEBUG] Starting MCTS search")
        return await super().__call__("")

    @staticmethod
    def print_result(result: MCTSResult):
        if result.trace is None:
            print("[DEBUG] No valid path found")
            return

        states, actions = result.trace
        print("[DEBUG] Path found:")
        for i, (state, action) in enumerate(zip(states, actions)):
            print(f"[DEBUG] Step {i}")
            print(f"[DEBUG]  URL: {state.url}")
            print(f"[DEBUG]  Action: {action.type} - {action}")

        print(f"[DEBUG] Final URL: {states[-1].url}")
        print(f"[DEBUG] Cumulative reward: {result.cum_reward}")
        print(f"[DEBUG] Total steps: {len(actions)}")


async def main():
    print("Starting MCTS")

    playwright_manager = PlaywrightManager()
    await playwright_manager.async_initialize()
    print("Browser started and ready")

    print("[DEBUG] Starting main function")
    actor = AgentQActor()  
    critic = AgentQCritic()  
    vision = VisionAgent()

    objective = "Play shape of you on youtube"
    print(f"[DEBUG] Objective set: {objective}")

    mcts_wrapper = BrowserMCTSWrapper(
        objective=objective,
        actor=actor,
        critic=critic,
        vision=vision,
        n_iterations=1,
        exploration_weight=1.0,
    )

    print("[DEBUG] Running MCTS wrapper")
    result = await mcts_wrapper()

    print("[DEBUG] Printing MCTS result")
    BrowserMCTSWrapper.print_result(result)
    await playwright_manager.stop_playwright()


if __name__ == "__main__":
    print("[DEBUG] Script started")
    asyncio.run(main())
    print("[DEBUG] Script finished")