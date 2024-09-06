from abc import ABC, abstractmethod
from typing import Generic, Protocol, Tuple, TypeVar, Union, runtime_checkable

State = TypeVar("State")
Action = TypeVar("Action")
Example = TypeVar("Example")
Trace = tuple[list[State], list[Action]]


class WorldModel(ABC, Generic[State, Action, Example]):
    def __init__(self) -> None:
        self.example = None
        self.prompt = None

    @abstractmethod
    async def init_state(self) -> State: ...

    @abstractmethod
    async def step(
        self, state: State, action: Action
    ) -> Union[State, Tuple[State, dict]]:
        """Returns the next state and optionally an auxiliary data dict

        :param state: The current state
        :param action: The action to take
        :return: The next state and optionally an auxiliary data dict
        """
        ...

    @abstractmethod
    async def is_terminal(self, state: State) -> bool: ...

    def update_example(self, example: Example, prompt=None) -> None:
        if prompt is not None:
            self.prompt = prompt
        self.example = example


class DefaultWorldModel(WorldModel):
    # A default implementation of WorldModel that only
    # saves the action sequence as the state

    def __init__(self, base_model) -> None:
        super().__init__()
        self.base_model = base_model

    async def init_state(self):
        return []

    async def step(self, state, action):
        return state + [action], {}

    async def is_terminal(self, state):
        # By default the state is never terminal
        return False


class SearchConfig(ABC, Generic[State, Action, Example]):
    def __init__(self) -> None:
        self.example = None
        self.prompt = None

    @abstractmethod
    async def get_actions(self, state: State) -> list[Action]: ...

    def fast_reward(self, state: State, action: Action) -> tuple[float, dict]:
        return 0, {}

    @abstractmethod
    async def reward(self, state, action, **kwargs) -> tuple[float, dict]: ...

    def update_example(self, example: Example, prompt=None) -> None:
        if prompt is not None:
            self.prompt = prompt
        self.example = example


@runtime_checkable
class AlgorithmOutput(Protocol[State]):
    terminal_state: State
    trace: Trace


class SearchAlgorithm(ABC):
    def __init__(self, **kwargs): ...

    @abstractmethod
    async def __call__(
        self, world_model: WorldModel, search_config: SearchConfig, **kwargs
    ) -> AlgorithmOutput: ...


class Reasoner(ABC, Generic[State, Action, Example]):
    def __init__(
        self,
        world_model: WorldModel[State, Action, Example],
        search_config: SearchConfig[State, Action, Example],
        search_algo: SearchAlgorithm,
    ) -> None:
        self.world_model = world_model
        self.search_config = search_config
        self.search_algo = search_algo

    async def __call__(
        self, example: Example, prompt=None, **kwargs
    ) -> AlgorithmOutput[State]:
        self.world_model.update_example(example, prompt=prompt)
        self.search_config.update_example(example, prompt=prompt)
        return await self.search_algo(self.world_model, self.search_config, **kwargs)
