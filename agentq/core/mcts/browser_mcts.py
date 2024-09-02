import asyncio
from typing import List, NamedTuple, Tuple

import numpy as np

from agentq.core.agent.agentq_actor import AgentQActor
from agentq.core.agent.agentq_critic import AgentQCritic
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
)
from agentq.core.skills.click_using_selector import click
from agentq.core.skills.enter_text_using_selector import EnterTextEntry, entertext
from agentq.core.skills.get_dom_with_content_type import get_dom_with_content_type
from agentq.core.skills.get_url import geturl
from agentq.core.skills.open_url import openurl


class BrowserState(NamedTuple):
    dom: str
    url: str
    objective: str


class BrowserWorldModel(WorldModel[BrowserState, BrowserAction, str]):
    def __init__(self, objective: str) -> None:
        super().__init__()
        self.objective = objective

    def init_state(self) -> BrowserState:
        initial_dom = self.get_current_dom()
        initial_url = self.get_current_url()
        return BrowserState(dom=initial_dom, url=initial_url, objective=self.objective)

    async def step(
        self, state: BrowserState, action: BrowserAction
    ) -> Tuple[BrowserState, dict]:
        new_dom, new_url = await self.execute_browser_action(action)
        new_state = BrowserState(dom=new_dom, url=new_url, objective=state.objective)
        return new_state, {}

    def is_terminal(self, state: BrowserState) -> bool:
        return is_terminal(state)

    async def execute_browser_action(self, action: BrowserAction) -> Tuple[str, str]:
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
        return new_dom, new_url

    async def get_current_dom(self) -> str:
        return await get_dom_with_content_type(content_type="all_fields")

    async def get_current_url(self) -> str:
        return await geturl()


class BrowserMCTSSearchConfig(SearchConfig[BrowserState, BrowserAction, str]):
    def __init__(self, actor: BaseAgent, critic: BaseAgent) -> None:
        super().__init__()
        self.actor = actor
        self.critic = critic

    async def get_actions(self, state: BrowserState) -> List[BrowserAction]:
        # Check if completed task is cauing a problem
        actor_input: AgentQInput = AgentQInput(
            objective=state.objective,
            current_page_dom=state.dom,
            current_page_url=state.url,
        )
        actor_output: AgentQActorOutput = await self.actor.run(actor_input)
        proposed_tasks: List[TaskWithActions] = actor_output.proposed_tasks

        critic_input = AgentQCriticInput(
            objective=state.objective,
            tasks_for_eval=proposed_tasks,
            current_page_dom=state.dom,
            current_page_url=state.url,
        )

        critic_output: AgentQCriticOutput = await self.critic.run(critic_input)

        return critic_output.top_task.actions_to_be_performed

    async def reward(
        self, state: BrowserState, action: BrowserAction, **kwargs
    ) -> Tuple[float, dict]:
        if is_terminal(state=state):
            return 1.0, {}
        else:
            return -0.01, {}  # small penalty for each step to encourage shorter path


async def is_terminal(state: BrowserState) -> bool:
    # Todo: Implement terminal state using vision
    return False


class BrowserMCTSWrapper(Reasoner[BrowserState, BrowserAction, str]):
    def __init__(
        self,
        objective: str,
        actor: BaseAgent,
        critic: BaseAgent,
        n_iterations: int = 100,
        exploration_weight: float = 1.0,
    ):
        world_model = BrowserWorldModel(objective)
        search_config = BrowserMCTSSearchConfig(actor, critic)
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

    async def __call__(self) -> MCTSResult:
        return await super().__call__("")

    @staticmethod
    def print_result(result: MCTSResult):
        if result.trace is None:
            print("No valid path found")
            return

        states, actions = result.trace
        print("Path found: ")
        for i, (state, action) in enumerate(zip(states, actions)):
            print(f"Step {i}")
            print(f" URL: {state.url}")
            print(f"  Action: {action.type} - {action}")

        print(f"Final URL: {states[-1].url}")
        print(f"Cumulative reward: {result.cum_reward}")
        print(f"Total steps: {len(actions)}")


async def main():
    actor = AgentQActor()  # TODO: do this
    critic = AgentQCritic()  # TODO: do this

    objective = "Play shape of you on youtube"

    mcts_wrapper = BrowserMCTSWrapper(
        objective=objective,
        actor=actor,
        critic=critic,
        n_iterations=100,
        exploration_weight=1.0,
    )

    result = await mcts_wrapper()

    BrowserMCTSWrapper.print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
