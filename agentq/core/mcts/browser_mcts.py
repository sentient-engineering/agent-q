import asyncio
from typing import List, Optional, Tuple

import numpy as np
from playwright.async_api import async_playwright as playwright
from pydantic import BaseModel
from pydantic.fields import Field

from agentq.core.agent.agentq_actor import AgentQActor
from agentq.core.agent.agentq_critic import AgentQCritic
from agentq.core.agent.base import BaseAgent
from agentq.core.agent.vision_agent import VisionAgent
from agentq.core.mcts.base import Reasoner, SearchConfig, WorldModel
from agentq.core.mcts.mcts import MCTS, MCTSResult
from agentq.core.models.models import (
    Action,
    ActionType,
    AgentQActorInput,
    AgentQActorOutput,
    AgentQCriticInput,
    AgentQCriticOutput,
    TaskWithActions,
    VisionInput,
    VisionOutput,
)
from agentq.core.skills.click_using_selector import click
from agentq.core.skills.enter_text_and_click import enter_text_and_click
from agentq.core.skills.enter_text_using_selector import EnterTextEntry, entertext
from agentq.core.skills.get_dom_with_content_type import get_dom_with_content_type
from agentq.core.skills.get_screenshot import get_screenshot
from agentq.core.skills.get_url import geturl
from agentq.core.skills.open_url import openurl
from agentq.core.web_driver.playwright import PlaywrightManager

# ANSI color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"


class BrowserState(BaseModel):
    dom: str
    url: str
    objective: str
    completed_tasks: Optional[List[TaskWithActions]]


class BrowserAction(BaseModel):
    action: Action
    rank: float = Field(description="The rank of this action, higher is better")


class BrowserWorldModel(WorldModel[BrowserState, BrowserAction, str]):
    def __init__(self, objective: str, vision: BaseAgent) -> None:
        super().__init__()
        self.objective = objective
        self.vision = vision
        print(
            f"{BLUE}[DEBUG] BrowserWorldModel initialized with objective: {self.objective}{RESET}"
        )

    async def init_state(self) -> BrowserState:
        initial_dom = await self.get_current_dom()
        initial_url = await self.get_current_url()
        print(f"{GREEN}[DEBUG] Initial state created - URL: {initial_url}{RESET}")
        return BrowserState(
            dom=initial_dom,
            url=initial_url,
            objective=self.objective,
            completed_tasks=[],
        )

    async def step(
        self, state: BrowserState, action: BrowserAction
    ) -> Tuple[BrowserState, dict]:
        print(f"{YELLOW}[DEBUG] Executing step with action: {action}{RESET}")
        new_dom, new_url = await self.execute_browser_action(action)
        current_task = TaskWithActions(
            id=len(state.completed_tasks) + 1,
            description=f"Executed action: {action.action.type}",
            actions_to_be_performed=[action.action],
            result="done",
        )
        new_completed_tasks = state.completed_tasks + [current_task]
        new_state = BrowserState(
            dom=new_dom,
            url=new_url,
            objective=state.objective,
            completed_tasks=new_completed_tasks,
        )
        print(f"{GREEN}[DEBUG] New state after step - URL: {new_url}{RESET}")
        return new_state, {}

    async def is_terminal(self, state: BrowserState) -> bool:
        terminal = await is_terminal(state, self.vision)
        print(f"{CYAN}[DEBUG] Checking if state is terminal: {terminal}{RESET}")
        return terminal

    async def execute_browser_action(self, action: BrowserAction) -> Tuple[str, str]:
        print(f"{YELLOW}[DEBUG] Executing browser action: {action.action.type}{RESET}")
        playwright_manager = PlaywrightManager()
        page = await playwright_manager.get_current_page()

        async def wait_for_navigation():
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except playwright._impl._errors.TimeoutError:
                print(
                    f"{MAGENTA}[DEBUG] Navigation timeout, proceeding with current state{RESET}"
                )

        if action.action.type == ActionType.GOTO_URL:
            await openurl(url=action.action.website, timeout=action.action.timeout or 0)
        elif action.action.type == ActionType.TYPE:
            entry = EnterTextEntry(
                query_selector=f"[mmid='{action.action.mmid}']",
                text=action.action.content,
            )
            await entertext(entry)
            await wait_for_navigation()
            print(f"{CYAN}[DEBUG] Typed text into element{RESET}")
        elif action.action.type == ActionType.CLICK:
            await click(
                selector=f"[mmid='{action.action.mmid}']",
                wait_before_execution=action.action.wait_before_execution or 0,
            )
            await page.wait_for_load_state("networkidle", timeout=10000)
            print(f"{CYAN}[DEBUG] Clicked element{RESET}")
        elif action.action.type == ActionType.ENTER_TEXT_AND_CLICK:
            await enter_text_and_click(
                text_selector=f"[mmid='{action.action.text_element_mmid}']",
                text_to_enter=action.action.text_to_enter,
                click_selector=f"[mmid='{action.action.click_element_mmid}']",
                wait_before_click_execution=action.action.wait_before_click_execution
                or 0,
            )
            await wait_for_navigation()
            print(f"{CYAN}[DEBUG] Entered text and clicked element{RESET}")

        await wait_for_navigation()
        try:
            new_dom = await self.get_current_dom()
        except playwright._impl._errors.Error as e:
            print(f"{RED}[DEBUG] Error getting DOM after action: {e}{RESET}")
            new_dom = "Error: Unable to retrieve DOM"

        try:
            new_url = await self.get_current_url()
        except playwright._impl._errors.Error as e:
            print(f"{RED}[DEBUG] Error getting URL after action: {e}{RESET}")
            new_url = "Error: Unable to retrieve URL"

        print(f"{GREEN}[DEBUG] After action execution - New URL: {new_url}{RESET}")
        return new_dom, new_url

    async def get_current_dom(self) -> str:
        dom = await get_dom_with_content_type(content_type="all_fields")
        print(f"{CYAN}[DEBUG] Got current DOM (length: {len(dom)}){RESET}")
        return str(dom)

    async def get_current_url(self) -> str:
        url = await geturl()
        print(f"{CYAN}[DEBUG] Got current URL: {url}{RESET}")
        return url


class BrowserMCTSSearchConfig(SearchConfig[BrowserState, BrowserAction, str]):
    def __init__(self, actor: BaseAgent, critic: BaseAgent, vision: BaseAgent) -> None:
        super().__init__()
        self.actor = actor
        self.critic = critic
        self.vision = vision
        print(f"{BLUE}[DEBUG] BrowserMCTSSearchConfig initialized{RESET}")

    async def get_actions(self, state: BrowserState) -> List[BrowserAction]:
        print(f"{YELLOW}[DEBUG] Getting actions for current state{RESET}")
        actor_input: AgentQActorInput = AgentQActorInput(
            objective=state.objective,
            completed_tasks=state.completed_tasks,
            current_page_dom=state.dom,
            current_page_url=state.url,
        )
        actor_output: AgentQActorOutput = await self.actor.run(actor_input)

        proposed_tasks: List[TaskWithActions] = actor_output.proposed_tasks
        print(f"{CYAN}[DEBUG] Number of proposed tasks: {len(proposed_tasks)}{RESET}")

        ranked_actions = await self._rank_actions(state, proposed_tasks)
        print(f"{CYAN}[DEBUG] Number of sorted actions: {len(ranked_actions)}{RESET}")

        return ranked_actions

    async def reward(
        self, state: BrowserState, action: BrowserAction, **kwargs
    ) -> Tuple[float, dict]:
        if await is_terminal(state=state, vision=self.vision):
            print(f"{GREEN}[DEBUG] Terminal state reached, reward: 1.0{RESET}")
            return 1.0, {}
        else:
            print(f"{YELLOW}[DEBUG] Non-terminal state, reward: -0.01{RESET}")
            return -0.01, {}

    def fast_reward(
        self, state: BrowserState, action: BrowserAction
    ) -> tuple[float, dict]:
        return action.rank, {}

    async def _rank_actions(
        self, state: BrowserState, tasks: List[TaskWithActions]
    ) -> List[BrowserAction]:
        ranked_actions = []
        remaining_tasks = tasks.copy()
        total_tasks = len(remaining_tasks)

        for iteration in range(total_tasks):
            if not remaining_tasks:
                break

            critic_input = AgentQCriticInput(
                objective=state.objective,
                completed_tasks=state.completed_tasks,
                tasks_for_eval=remaining_tasks,
                current_page_url=state.url,
                current_page_dom=state.dom,
            )

            critic_output: AgentQCriticOutput = await self.critic.run(critic_input)
            top_task = critic_output.top_task

            if top_task and top_task.actions_to_be_performed:
                rank = 1.0 / (iteration + 1)  # Higher rank for earlier iterations
                ranked_actions.append(
                    BrowserAction(action=top_task.actions_to_be_performed[0], rank=rank)
                )

                # Remove the top task from remaining tasks
                remaining_tasks = [
                    task for task in remaining_tasks if task.id != top_task.id
                ]
            else:
                print(
                    f"{MAGENTA}[DEBUG] Warning: No valid top task found in iteration {iteration}. Skipping.{RESET}"
                )

        print(f"{CYAN}[DEBUG] Sorted actions: {ranked_actions}{RESET}")
        return ranked_actions


async def is_terminal(state: BrowserState, vision: BaseAgent) -> bool:
    print(f"{YELLOW}[DEBUG] Checking if state is terminal{RESET}")
    screenshot = await get_screenshot()
    vision_input: VisionInput = VisionInput(objective=state.objective)
    vision_output: VisionOutput = await vision.run(vision_input, screenshot)
    print(f"{CYAN}[DEBUG] Output of vision LLM {vision_output.is_terminal}{RESET}")
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
            simulate_strategy="max",
            output_strategy="max_reward",
            depth_limit=20,
        )
        super().__init__(world_model, search_config, search_algo)
        print(
            f"{BLUE}[DEBUG] BrowserMCTSWrapper initialized with objective: {objective}{RESET}"
        )

    async def __call__(self) -> MCTSResult:
        print(f"{YELLOW}[DEBUG] Starting MCTS search{RESET}")
        return await super().__call__("")

    @staticmethod
    def print_result(result: MCTSResult):
        if result.trace is None:
            print(f"{RED}[DEBUG] No valid path found{RESET}")
            return

        states, actions = result.trace
        print(f"{GREEN}[DEBUG] Path found:{RESET}")
        for i, (state, action) in enumerate(zip(states, actions)):
            print(f"{CYAN}[DEBUG] Step {i}{RESET}")
            print(f"{CYAN}[DEBUG]  URL: {state.url}{RESET}")
            print(f"{CYAN}[DEBUG]  Action: {action.action.type} - {action}{RESET}")

        print(f"{GREEN}[DEBUG] Final URL: {states[-1].url}{RESET}")
        print(f"{GREEN}[DEBUG] Cumulative reward: {result.cum_reward}{RESET}")
        print(f"{GREEN}[DEBUG] Total steps: {len(actions)}{RESET}")


async def main():
    print(f"{BLUE}Starting MCTS{RESET}")

    playwright_manager = PlaywrightManager()
    await playwright_manager.async_initialize()
    print(f"{GREEN}Browser started and ready{RESET}")

    print(f"{BLUE}[DEBUG] Starting main function{RESET}")
    actor = AgentQActor()
    critic = AgentQCritic()
    vision = VisionAgent()

    objective = "play shape of you on youtube"
    print(f"{CYAN}[DEBUG] Objective set: {objective}{RESET}")

    mcts_wrapper = BrowserMCTSWrapper(
        objective=objective,
        actor=actor,
        critic=critic,
        vision=vision,
        n_iterations=1,
        exploration_weight=1.0,
    )

    print(f"{YELLOW}[DEBUG] Running MCTS wrapper{RESET}")
    result = await mcts_wrapper()

    print(f"{CYAN}[DEBUG] Printing MCTS result{RESET}")
    BrowserMCTSWrapper.print_result(result)
    await playwright_manager.stop_playwright()


if __name__ == "__main__":
    print(f"{BLUE}[DEBUG] Script started{RESET}")
    asyncio.run(main())
    print(f"{GREEN}[DEBUG] Script finished{RESET}")
