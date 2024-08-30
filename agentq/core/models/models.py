from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel
from pydantic.fields import Field


# Global
class State(str, Enum):
    PLAN = "plan"
    BROWSE = "browse"
    COMPLETED = "completed"
    CONTINUE = "continue"


class ActionType(str, Enum):
    CLICK = "CLICK"
    TYPE = "TYPE"
    GOTO_URL = "GOTO_URL"
    GET_DOM_TEXT_CONTENT = "GET_DOM_TEXT_CONTENT"
    GET_DOM_INPUT_FILEDS = "GET_DOM_INPUT_FILEDS"
    GET_DOM_ALL_CONTENTS = "GET_DOM_ALL_CONTENTS"
    GET_CURRENT_URL = "GET_CURRENT_URL"


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


class GetDomTextAction(BaseModel):
    type: Literal[ActionType.GET_DOM_TEXT_CONTENT]


class GetDomInputsAction(BaseModel):
    type: Literal[ActionType.GET_DOM_INPUT_FILEDS]


class GetDomAllAction(BaseModel):
    type: Literal[ActionType.GET_DOM_ALL_CONTENTS]


class GetCurrentUrlAction(BaseModel):
    type: Literal[ActionType.GET_CURRENT_URL]


Action = Union[
    ClickAction,
    TypeAction,
    GotoAction,
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


class Memory(BaseModel):
    objective: str
    current_state: State
    plan: Optional[List[Task]]
    thought: str
    completed_tasks: Optional[List[Task]]
    current_task: Optional[List[Task]]
    final_response: Optional[str]

    class Config:
        use_enum_values = True


# Planner
class PlannerInput(BaseModel):
    objective: str
    plan: Optional[List[Task]]
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
class AgentQInput(BaseModel):
    objective: str
    completed_tasks: Optional[List[Task]]
    current_page_dom: str


class AgentQOutput(BaseModel):
    thought: str
    plan: List[Task]
    next_task: Optional[Task]
    next_task_actions: Optional[List[Action]]
    is_complete: bool
    final_response: Optional[str]
