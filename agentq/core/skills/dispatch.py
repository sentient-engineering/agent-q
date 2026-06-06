"""Single shared typed-`Action` → browser-skill dispatch map for agent-q.

Both LIVE executors route through this one function:
  - execute_browser_action  (agentq/core/mcts/browser_mcts.py)      — MCTS search rollouts
  - handle_agentq_actions   (agentq/core/orchestrator/orchestrator.py) — orchestrator real loop

The dispatch MAP is shared; each caller passes its OWN wait timing, because an MCTS search rollout and
a real orchestrator execution are distinct execution contexts (the search waits are world-model
parameters; the real-loop waits are infra configuration — they are deliberately NOT unified).

`dispatch_action` is TOTAL over ActionType: an unhandled/future type raises `UnhandledActionTypeError`
rather than silently no-opping.
"""
from typing import Any

from agentq.core.models.models import Action, ActionType
from agentq.core.skills.click_using_selector import click
from agentq.core.skills.enter_text_and_click import enter_text_and_click
from agentq.core.skills.enter_text_using_selector import EnterTextEntry, entertext
from agentq.core.skills.open_url import openurl
from agentq.core.skills.solve_captcha import solve_captcha


class UnhandledActionTypeError(ValueError):
    """Raised by `dispatch_action` for an ActionType with no branch.

    A `ValueError` subclass (so existing ``except ValueError`` sites still catch it), but a DISTINCT
    type so a caller with a retry loop can re-raise it immediately — an unknown action type is a
    programming/coverage error, not a transient failure to retry.
    """


async def dispatch_action(
    action: Action,
    *,
    click_wait: float,
    enter_text_and_click_wait: float,
    captcha_wait: float,
) -> Any:
    """Dispatch one typed `Action` to its browser skill and return the skill's result.

    The wait values are supplied by the CALLER (not defaulted here) so the MCTS search path and the
    orchestrator real-loop path each keep their own timing.
    """
    if action.type == ActionType.GOTO_URL:
        return await openurl(url=action.website, timeout=action.timeout or 1)
    elif action.type == ActionType.TYPE:
        return await entertext(
            EnterTextEntry(query_selector=f"[mmid='{action.mmid}']", text=action.content)
        )
    elif action.type == ActionType.CLICK:
        return await click(
            selector=f"[mmid='{action.mmid}']",
            wait_before_execution=action.wait_before_execution or click_wait,
        )
    elif action.type == ActionType.ENTER_TEXT_AND_CLICK:
        return await enter_text_and_click(
            text_selector=f"[mmid='{action.text_element_mmid}']",
            text_to_enter=action.text_to_enter,
            click_selector=f"[mmid='{action.click_element_mmid}']",
            wait_before_click_execution=action.wait_before_click_execution or enter_text_and_click_wait,
        )
    elif action.type == ActionType.SOLVE_CAPTCHA:
        return await solve_captcha(
            text_selector=f"[mmid='{action.text_element_mmid}']",
            click_selector=f"[mmid='{action.click_element_mmid}']",
            wait_before_click_execution=action.wait_before_click_execution or captcha_wait,
        )
    else:
        raise UnhandledActionTypeError(
            f"Unhandled ActionType in dispatch_action: {action.type}"
        )
