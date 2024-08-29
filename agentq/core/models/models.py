from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel


# Global
class State(str, Enum):
    PLAN = "plan"
    BROWSE = "browse"
    COMPLETED = "completed"
    CONTINUE = "continue"


class ActionType(str, Enum):
    CLICK = "CLICK"
    TYPE = "TYPE"
    GOTO = "GOTO"


class ClickAction(BaseModel):
    type: Literal[ActionType.CLICK]
    mmid: str


class TypeAction(BaseModel):
    type: Literal[ActionType.TYPE]
    mmid: str
    content: str


class GotoAction(BaseModel):
    type: Literal[ActionType.GOTO]
    website: str


Action = Union[ClickAction, TypeAction, GotoAction]


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
    current_task: Optional[Task]
    completed_tasks: Optional[List[Task]]
    # task_for_review: Optional[Task]


class AgentQOutput(BaseModel):
    plan: Optional[List[Task]]
    thought: str
    current_task_with_result: Optional[Task]
    current_task_actions: Optional[List[Action]]
    next_task: Optional[Task]
    is_complete: bool
    final_response: Optional[str]
