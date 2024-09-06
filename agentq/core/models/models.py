from enum import Enum, IntEnum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel
from pydantic.fields import Field


# Global
class State(str, Enum):
    PLAN = "plan"
    BROWSE = "browse"
    COMPLETED = "completed"
    AGENTQ_BASE = "agentq_base"
    AGENTQ_ACTOR = "agentq_actor"
    AGENTQ_CRITIC = "agentq_critic"


class ActionType(str, Enum):
    CLICK = "CLICK"
    TYPE = "TYPE"
    GOTO_URL = "GOTO_URL"
    ENTER_TEXT_AND_CLICK = "ENTER_TEXT_AND_CLICK"
    SOLVE_CAPTCHA = "SOLVE_CAPTCHA"
    # GET_DOM_TEXT_CONTENT = "GET_DOM_TEXT_CONTENT"
    # GET_DOM_INPUT_FILEDS = "GET_DOM_INPUT_FILEDS"
    # GET_DOM_ALL_CONTENTS = "GET_DOM_ALL_CONTENTS"
    # GET_CURRENT_URL = "GET_CURRENT_URL"


class ClickAction(BaseModel):
    type: Literal[ActionType.CLICK] = Field(
        description="""Executes a click action on the element matching the given mmid attribute value. MMID is always a number. Returns Success if click was successful or appropriate error message if the element could not be clicked."""
    )
    mmid: int = Field(
        description="The mmid number of the element that needs to be clicked e.g. 114. mmid will always be a number"
    )
    wait_before_execution: Optional[float] = Field(
        description="Optional wait time in seconds before executing the click event logic"
    )


class TypeAction(BaseModel):
    type: Literal[ActionType.TYPE] = Field(
        description="""Single enter given text in the DOM element matching the given mmid attribute value. This will only enter the text and not press enter or anything else.
   Returns Success if text entry was successful or appropriate error message if text could not be entered."""
    )
    mmid: int = Field(
        description="The mmid number of the element that needs to be clicked e.g. 114. mmid will always be a number"
    )
    content: str = Field(
        description="The text to enter in the element identified by the query_selector."
    )


class GotoAction(BaseModel):
    type: Literal[ActionType.GOTO_URL] = Field(
        description="Opens a specified URL in the web browser instance. Returns url of the new page if successful or appropriate error message if the page could not be opened."
    )
    website: str = Field(
        description="The URL to navigate to. Value must include the protocol (http:// or https://)."
    )
    timeout: Optional[float] = Field(
        description="Additional wait time in seconds after initial load."
    )


class EnterTextAndClickAction(BaseModel):
    type: Literal[ActionType.ENTER_TEXT_AND_CLICK] = Field(
        description="""Enters text into a specified element and clicks another element, both identified by their mmid. Ideal for seamless actions like submitting search queries, this integrated approach ensures superior performance over separate text entry and click commands. Successfully completes when both actions are executed without errors, returning True; otherwise, it provides False or an explanatory message of any failure encountered."""
    )
    text_element_mmid: int = Field(
        description="The mmid number of the element where the text will be entered"
    )
    text_to_enter: str = Field(
        description="The text that will be entered into the element specified by text_element_mmid"
    )
    click_element_mmid: int = Field(
        description="The mmid number of the element that will be clicked after text entry."
    )
    wait_before_click_execution: Optional[float] = Field(
        description="Optional wait time in seconds before executing the click event logic"
    )


class Score(IntEnum):
    FAIL = 0
    PASS = 1


# class GetDomTextAction(BaseModel):
#     type: Literal[ActionType.GET_DOM_TEXT_CONTENT]


# class GetDomInputsAction(BaseModel):
#     type: Literal[ActionType.GET_DOM_INPUT_FILEDS]


# class GetDomAllAction(BaseModel):
#     type: Literal[ActionType.GET_DOM_ALL_CONTENTS]


# class GetCurrentUrlAction(BaseModel):
#     type: Literal[ActionType.GET_CURRENT_URL]


Action = Union[
    ClickAction, TypeAction, GotoAction, EnterTextAndClickAction
    # GetDomTextAction,
    # GetDomInputsAction,
    # GetDomAllAction,
    # GetCurrentUrlAction,
]


class Task(BaseModel):
    id: int
    description: str
    url: Optional[str]
    result: Optional[str]


class TaskWithActions(BaseModel):
    id: int
    description: str
    actions_to_be_performed: Optional[List[Action]]
    result: Optional[str]


class Memory(BaseModel):
    objective: str
    current_state: State
    plan: Optional[Union[List[Task], List[TaskWithActions]]]
    thought: str
    completed_tasks: Optional[Union[List[Task], List[TaskWithActions]]]
    current_task: Optional[Union[Task, TaskWithActions]]
    final_response: Optional[str]
    current_tasks_for_eval: Optional[List[TaskWithActions]]
    sorted_tasks: Optional[List[TaskWithActions]]

    class Config:
        use_enum_values = True


# Planner
class PlannerInput(BaseModel):
    objective: str
    completed_tasks: Optional[List[Task]]
    task_for_review: Optional[Task]


class PlannerOutput(BaseModel):
    plan: Optional[List[Task]]
    thought: str
    next_task: Optional[Task]
    is_complete: bool
    final_response: Optional[str]


# Executor
class BrowserNavInput(BaseModel):
    task: Task


class BrowserNavOutput(BaseModel):
    completed_task: Task


# AgentQ
class AgentQBaseInput(BaseModel):
    objective: str
    completed_tasks: Optional[List[Task]]
    current_page_url: str
    current_page_dom: str


class AgentQBaseOutput(BaseModel):
    thought: str
    plan: List[Task]
    next_task: Optional[Task]
    next_task_actions: Optional[List[Action]]
    is_complete: bool
    final_response: Optional[str]


# Actor
class AgentQActorInput(BaseModel):
    objective: str
    completed_tasks: Optional[List[TaskWithActions]]
    current_page_url: str
    current_page_dom: str


class AgentQActorOutput(BaseModel):
    thought: str
    proposed_tasks: Optional[List[TaskWithActions]]
    is_complete: bool
    final_response: Optional[str]


# Critic
class AgentQCriticInput(BaseModel):
    objective: str
    completed_tasks: Optional[List[TaskWithActions]]
    tasks_for_eval: List[TaskWithActions]
    current_page_url: str
    current_page_dom: str


class AgentQCriticOutput(BaseModel):
    thought: str
    top_task: TaskWithActions


# Vision
class VisionInput(BaseModel):
    objective: str


class VisionOutput(BaseModel):
    is_terminal: bool


class EvalAgentInput(BaseModel):
    objective: str
    agent_output: str
    current_page_url: str
    current_page_dom: str


class EvalAgentOutput(BaseModel):
    score: Score


class CaptchaAgentOutput(BaseModel):
    captcha: str
    success: bool
