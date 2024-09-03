import asyncio
import textwrap
import uuid
from typing import Dict, List

from colorama import Fore, init
from dotenv import load_dotenv
from langsmith import traceable

from agentq.core.agent.base import BaseAgent
from agentq.core.models.models import (
    Action,
    ActionType,
    AgentQActorInput,
    AgentQActorOutput,
    AgentQBaseInput,
    AgentQBaseOutput,
    AgentQCriticInput,
    AgentQCriticOutput,
    BrowserNavInput,
    BrowserNavOutput,
    Memory,
    PlannerInput,
    PlannerOutput,
    State,
    Task,
    TaskWithActions,
)
from agentq.core.skills.click_using_selector import click
from agentq.core.skills.enter_text_and_click import enter_text_and_click
from agentq.core.skills.enter_text_using_selector import EnterTextEntry, entertext
from agentq.core.skills.get_dom_with_content_type import get_dom_with_content_type
from agentq.core.skills.get_screenshot import get_screenshot
from agentq.core.skills.get_url import geturl
from agentq.core.skills.open_url import openurl
from agentq.core.web_driver.playwright import PlaywrightManager

init(autoreset=True)


class Orchestrator:
    def __init__(
        self, state_to_agent_map: Dict[State, BaseAgent], eval_mode: bool = False
    ):
        load_dotenv()
        self.state_to_agent_map = state_to_agent_map
        self.playwright_manager = PlaywrightManager()
        self.eval_mode = eval_mode
        self.shutdown_event = asyncio.Event()
        self.session_id = str(uuid.uuid4())

    async def start(self):
        print("Starting orchestrator")
        await self.playwright_manager.async_initialize(eval_mode=self.eval_mode)
        print("Browser started and ready")

        if not self.eval_mode:
            await self._command_loop()

    async def _command_loop(self):
        while not self.shutdown_event.is_set():
            try:
                command = await self._get_user_input()
                if command.strip().lower() == "exit":
                    await self.shutdown()
                else:
                    await self.execute_command(command)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"An error occurred: {e}")

    async def _get_user_input(self):
        return await asyncio.get_event_loop().run_in_executor(
            None, input, "Enter your command (or type 'exit' to quit) "
        )

    @traceable(run_type="chain", name="execute_command")
    async def execute_command(self, command: str):
        try:
            # Create initial memory
            self.memory = Memory(
                objective=command,
                # change current state to
                # 1. PLAN for using separate planner and browser agent
                # 2. AGENTQ_BASE for using the base AgentQ
                # 3. AGENTQ_ACTOR for using the AgentQ actor-critic model
                current_state=State.AGENTQ_BASE,
                plan=[],
                thought="",
                completed_tasks=[],
                current_task=None,
                final_response=None,
                current_tasks_for_eval=None,
                sorted_tasks=None,
            )
            print(f"Executing command {self.memory.objective}")
            while self.memory.current_state != State.COMPLETED:
                await self._handle_state()
            self._print_final_response()

            if self.eval_mode:
                return self.memory.final_response
            else:
                return
        except Exception as e:
            print(f"Error executing the command {self.memory.objective}: {e}")

    def run(self) -> Memory:
        while self.memory.current_state != State.COMPLETED:
            self._handle_state()

        self._print_final_response()
        return self.memory

    async def _handle_state(self):
        current_state = self.memory.current_state

        if current_state not in self.state_to_agent_map:
            raise ValueError(f"Unhandled state! No agent for {current_state}")

        if current_state == State.PLAN:
            await self._handle_planner()
        elif current_state == State.BROWSE:
            await self._handle_browser_navigation()
        elif current_state == State.AGENTQ_BASE:
            await self._handle_agnetq_base()
        elif current_state == State.AGENTQ_ACTOR:
            await self._handle_agnetq_actor()
        elif current_state == State.AGENTQ_CRITIC:
            await self._handle_agnetq_critic(
                tasks_for_eval=self.memory.current_tasks_for_eval
            )
        else:
            raise ValueError(f"Unhandled state: {current_state}")

    async def _handle_planner(self):
        agent = self.state_to_agent_map[State.PLAN]
        self._print_memory_and_agent(agent.name)

        screenshot = await get_screenshot()

        input_data = PlannerInput(
            objective=self.memory.objective,
            task_for_review=self.memory.current_task,
            completed_tasks=self.memory.completed_tasks,
        )

        output: PlannerOutput = await agent.run(input_data, screenshot, self.session_id)

        self._update_memory_from_planner(output)

        print(f"{Fore.MAGENTA}Planner has updated the memory.")

    async def _handle_browser_navigation(self):
        agent = self.state_to_agent_map[State.BROWSE]
        self._print_memory_and_agent(agent.name)

        # Update task with url
        current_task: Task = self.memory.current_task
        current_task.url = await geturl()

        input_data = BrowserNavInput(task=current_task)

        output: BrowserNavOutput = await agent.run(
            input_data, session_id=self.session_id
        )

        self._print_task_result(output.completed_task)

        self._update_memory_from_browser_nav(output)

        print(f"{Fore.MAGENTA}Executor has completed a task.")

    async def _handle_agnetq_base(self):
        agent = self.state_to_agent_map[State.AGENTQ_BASE]
        self._print_memory_and_agent(agent.name)

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                # Get the current page
                page = await self.playwright_manager.get_current_page()

                # Wait for the page to load
                await page.wait_for_load_state("networkidle", timeout=10000)

                # Get DOM and URL
                dom = await get_dom_with_content_type(content_type="all_fields")
                url = await geturl()

                input_data = AgentQBaseInput(
                    objective=self.memory.objective,
                    completed_tasks=self.memory.completed_tasks,
                    current_page_url=str(url),
                    current_page_dom=str(dom),
                )

                output: AgentQBaseOutput = await agent.run(
                    input_data, session_id=self.session_id
                )

                await self._update_memory_from_agentq_base(output)

                print(f"{Fore.MAGENTA}Base Agent Q has updated the memory.")
                break  # If successful, break out of the retry loop

            except Exception as e:
                print(f"{Fore.YELLOW}An error occurred: {e}")
                if attempt < max_retries - 1:
                    print(f"{Fore.YELLOW}Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    print(
                        f"{Fore.RED}Max retries reached. Unable to complete the action."
                    )
                    raise

        # After the loop, check if we've successfully completed the operation
        if attempt == max_retries - 1:
            raise Exception("Failed to handle AgentQ Base after maximum retries")

    async def _handle_agnetq_actor(self):
        agent = self.state_to_agent_map[State.AGENTQ_ACTOR]
        self._print_memory_and_agent(agent.name)

        # repesenting state with dom representation
        dom = await get_dom_with_content_type(content_type="all_fields")
        url = await geturl()

        input_data = AgentQActorInput(
            objective=self.memory.objective,
            completed_tasks=self.memory.completed_tasks,
            current_page_url=str(url),
            current_page_dom=str(dom),
        )

        output: AgentQActorOutput = await agent.run(
            input_data, session_id=self.session_id
        )

        await self._update_memory_from_agentq_actor(output)

        print(f"{Fore.MAGENTA}Base Agent Q has updated the memory.")

    async def _handle_agnetq_critic(self, tasks_for_eval: List[TaskWithActions]):
        agent = self.state_to_agent_map[State.AGENTQ_CRITIC]
        self._print_memory_and_agent(agent.name)

        sorted_tasks = []
        remaining_tasks = tasks_for_eval.copy()

        while len(remaining_tasks) > 1:
            # Reassign consecutive IDs to remaining tasks
            for i, task in enumerate(remaining_tasks, start=1):
                task.id = i

            dom = await get_dom_with_content_type(content_type="all_fields")
            url = await geturl()

            print(f"{Fore.GREEN}Critic agent has been called")

            input_data = AgentQCriticInput(
                objective=self.memory.objective,
                completed_tasks=self.memory.completed_tasks,
                tasks_for_eval=remaining_tasks,
                current_page_url=str(url),
                current_page_dom=str(dom),
            )

            output: AgentQCriticOutput = await agent.run(
                input_data, session_id=self.session_id
            )

            top_task = output.top_task
            sorted_tasks.append(top_task)
            task_to_remove = next(
                (task for task in remaining_tasks if task.id == top_task.id), None
            )
            if task_to_remove:
                remaining_tasks.remove(task_to_remove)
            else:
                print(
                    f"{Fore.RED}Warning: Top task not found in remaining tasks. Skipping. {top_task} && {remaining_tasks}"
                )

        # Add the last remaining task
        if remaining_tasks:
            sorted_tasks.append(remaining_tasks[0])

        await self._update_memory_from_agentq_critic(sorted_tasks)

        print(f"{Fore.MAGENTA}Critic Agent has sorted all the tasks.")

    def _update_memory_from_planner(self, planner_output: PlannerOutput):
        if planner_output.is_complete:
            self.memory.current_state = State.COMPLETED
            self.memory.final_response = planner_output.final_response
        elif planner_output.next_task:
            self.memory.current_state = State.BROWSE
            self.memory.plan = planner_output.plan
            self.memory.thought = planner_output.thought
            next_task_id = len(self.memory.completed_tasks) + 1
            self.memory.current_task = Task(
                id=next_task_id,
                description=planner_output.next_task.description,
                url=None,
                result=None,
            )
        else:
            raise ValueError("Planner did not provide next task or completion status")

    def _update_memory_from_browser_nav(self, browser_nav_output: BrowserNavOutput):
        self.memory.completed_tasks.append(browser_nav_output.completed_task)
        self.memory.current_task = None
        self.memory.current_state = State.PLAN

    async def _update_memory_from_agentq_base(self, agentq_output: AgentQBaseOutput):
        if agentq_output.is_complete:
            self.memory.current_state = State.COMPLETED
            self.memory.final_response = agentq_output.final_response
        elif agentq_output.next_task:
            self.memory.current_state = State.AGENTQ_BASE
            if agentq_output.next_task_actions:
                action_results = await self.handle_agentq_actions(
                    agentq_output.next_task_actions
                )
                print("Action results:", action_results)
                flattened_results = "; ".join(action_results)
                agentq_output.next_task.result = flattened_results

            self.memory.completed_tasks.append(agentq_output.next_task)
            self.memory.plan = agentq_output.plan
            self.memory.thought = agentq_output.thought
            current_task_id = len(self.memory.completed_tasks) + 1
            self.memory.current_task = Task(
                id=current_task_id,
                description=agentq_output.next_task.description,
                url=None,
                result=None,
            )
        else:
            raise ValueError("Planner did not provide next task or completion status")

    async def _update_memory_from_agentq_actor(self, actor_output: AgentQActorOutput):
        if actor_output.is_complete:
            self.memory.current_state = State.COMPLETED
            self.memory.final_response = actor_output.final_response
        elif actor_output.proposed_tasks:
            self.memory.current_state = State.AGENTQ_CRITIC
            self.memory.current_tasks_for_eval = actor_output.proposed_tasks
        else:
            raise ValueError("Planner did not provide next task or completion status")

    async def _update_memory_from_agentq_critic(
        self, sorted_tasks: List[TaskWithActions]
    ):
        self.memory.sorted_tasks = sorted_tasks

        # Execute the top task
        top_task = sorted_tasks[0]
        action_results = await self.handle_agentq_actions(
            top_task.actions_to_be_performed
        )
        print("Action results:", action_results)
        flattened_results = "; ".join(action_results)

        top_task.id = len(self.memory.completed_tasks) + 1
        top_task.result = flattened_results

        self.memory.completed_tasks.append(top_task)

        # Make proposed and sorted tasks empty
        self.memory.current_tasks_for_eval = None
        self.memory.sorted_tasks = None

        # Set the next state
        self.memory.current_state = State.AGENTQ_ACTOR

    async def handle_agentq_actions(self, actions: List[Action]):
        results = []
        for action in actions:
            page = await self.playwright_manager.get_current_page()
            if action.type == ActionType.GOTO_URL:
                result = await openurl(url=action.website, timeout=action.timeout or 0)
                await page.wait_for_load_state("networkidle", timeout=10000)
                print("Action - GOTO")
            elif action.type == ActionType.TYPE:
                await page.wait_for_selector(f"[mmid='{action.mmid}']", timeout=5000)
                entry = EnterTextEntry(
                    query_selector=f"[mmid='{action.mmid}']", text=action.content
                )
                result = await entertext(entry)
                print("Action - TYPE")
            elif action.type == ActionType.CLICK:
                await page.wait_for_selector(f"[mmid='{action.mmid}']", timeout=5000)
                result = await click(
                    selector=f"[mmid='{action.mmid}']",
                    wait_before_execution=action.wait_before_execution or 0,
                )
                print("Action - CLICK")
            elif action.type == ActionType.ENTER_TEXT_AND_CLICK:
                await page.wait_for_selector(
                    f"[mmid='{action.text_element_mmid}']", timeout=5000
                )
                await page.wait_for_selector(
                    f"[mmid='{action.click_element_mmid}']", timeout=5000
                )
                result = await enter_text_and_click(
                    text_selector=f"[mmid='{action.text_element_mmid}']",
                    text_to_enter=action.text_to_enter,
                    click_selector=f"[mmid='{action.click_element_mmid}']",
                    wait_before_click_execution=action.wait_before_click_execution or 0,
                )
                print("Action - ENTER TEXT AND CLICK")
            else:
                result = f"Unsupported action type: {action.type}"

            results.append(result)

        return results

    async def shutdown(self):
        print("Shutting down orchestrator!")
        self.shutdown_event.set()
        await self.playwright_manager.stop_playwright()

    def _print_memory_and_agent(self, agent_type: str):
        print(f"{Fore.CYAN}{'='*50}")
        print(f"{Fore.YELLOW}Current State: {Fore.GREEN}{self.memory.current_state}")
        print(f"{Fore.YELLOW}Agent: {Fore.GREEN}{agent_type}")
        print(f"{Fore.YELLOW}Current Thought: {Fore.GREEN}{self.memory.thought}")
        if len(self.memory.plan) == 0:
            print(f"{Fore.YELLOW}Plan:{Fore.GREEN} none")
        else:
            print(f"{Fore.YELLOW}Plan:")
            for task in self.memory.plan:
                print(f"{Fore.GREEN} {task.id}. {task.description}")
        if self.memory.current_task:
            print(
                f"{Fore.YELLOW}Current Task: {Fore.GREEN}{self.memory.current_task.description}"
            )
        if len(self.memory.completed_tasks) == 0:
            print(f"{Fore.YELLOW}Completed Tasks:{Fore.GREEN} none")
        else:
            print(f"{Fore.YELLOW}Completed Tasks:")
            for task in self.memory.completed_tasks:
                status = "✓" if task.result else " "
                print(f"{Fore.GREEN}  [{status}] {task.id}. {task.description}")
        print(f"{Fore.CYAN}{'='*50}")

    def _print_task_result(self, task: Task):
        print(f"{Fore.CYAN}{'='*50}")
        print(f"{Fore.YELLOW}Task Completed: {Fore.GREEN}{task.description}")
        print(f"{Fore.YELLOW}Result:")
        wrapped_result = textwrap.wrap(task.result, width=80)
        for line in wrapped_result:
            print(f"{Fore.WHITE}{line}")
        print(f"{Fore.CYAN}{'='*50}")

    def _print_final_response(self):
        print(f"\n{Fore.GREEN}{'='*50}")
        print(f"{Fore.GREEN}Objective Completed!")
        print(f"{Fore.GREEN}{'='*50}")
        print(f"{Fore.YELLOW}Final Response:")
        wrapped_response = textwrap.wrap(self.memory.final_response, width=80)
        for line in wrapped_response:
            print(f"{Fore.WHITE}{line}")
        print(f"{Fore.GREEN}{'='*50}")
