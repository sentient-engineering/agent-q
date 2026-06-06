"""R2 (DeepSeek learning-cycle): the typed-Action skill-dispatch map must live in ONE shared
`dispatch_action` (agentq/core/skills/dispatch.py), total over ActionType, and BOTH live executors
(execute_browser_action in the MCTS search path; handle_agentq_actions in the orchestrator real loop)
must route through it — NOT keep their own inline `action.type -> await <skill>` chains.

Committee-converged design (Option A, behavior-preserving dedup): the dispatch MAP is shared; each caller
keeps its OWN wait timing by passing it in (MCTS 2/2/2; real loop 1/1.5/1 — distinct execution kinds).

This asserts, via AST (no browser deps) + focused runtime checks:
  (1) COVERAGE     — dispatch_action has a branch for every ActionType member;
  (2) DISPATCH     — each branch actually awaits a call (not a pass/print no-op);
  (3) TOTALITY     — dispatch_action ends in an `else` that RAISES (UnhandledActionTypeError);
  (4) NO-DUP       — NEITHER execute_browser_action NOR handle_agentq_actions awaits any browser SKILL
                     directly; the only skill dispatch they perform is `await dispatch_action(...)`.
                     (False-positive-free: the surviving GOTO `if` in handle_agentq_actions awaits only
                     dispatch_action + page.wait_for_load_state, neither of which is in the skill set.)
  (5) MAP-OWNS     — dispatch_action itself awaits all five skills (the map lives there, nowhere else);
  (6) SURFACES     — dispatch_action raises UnhandledActionTypeError on an unknown type (runtime), and
                     handle_agentq_actions has `except UnhandledActionTypeError: raise` BEFORE the broad
                     `except Exception` (so an unknown type is not retried/swallowed);
  (7) SINK-WAITS   — dispatch_action passes the CALLER's wait to the skill (=1 vs =2), proving Option A.
"""
import ast
import asyncio
import os
from types import SimpleNamespace

import pytest

from agentq.core.models.models import ActionType

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODELS = os.path.join(REPO, "agentq/core/models/models.py")
_DISPATCH = os.path.join(REPO, "agentq/core/skills/dispatch.py")
_MCTS = os.path.join(REPO, "agentq/core/mcts/browser_mcts.py")
_ORCH = os.path.join(REPO, "agentq/core/orchestrator/orchestrator.py")

# The browser-skill names the dispatch map routes to. A caller awaiting any of these directly is a
# duplicate of the map. Pinned here AND asserted to equal what dispatch.py imports (test_map_owns).
_SKILLS = {"openurl", "entertext", "click", "enter_text_and_click", "solve_captcha"}


def _action_type_members() -> set[str]:
    src = open(_MODELS).read()
    members: set[str] = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.ClassDef) and n.name == "ActionType":
            for b in n.body:
                if isinstance(b, ast.Assign) and isinstance(b.targets[0], ast.Name):
                    members.add(b.targets[0].id)
    return members


def _func(path: str, name: str) -> ast.AsyncFunctionDef:
    for n in ast.walk(ast.parse(open(path).read())):
        if isinstance(n, ast.AsyncFunctionDef) and n.name == name:
            return n
    raise AssertionError(f"{name} not found in {path}")


def _dispatch_func() -> ast.AsyncFunctionDef:
    return _func(_DISPATCH, "dispatch_action")


def _dispatch_if(func: ast.AsyncFunctionDef) -> ast.If:
    for stmt in func.body:
        if isinstance(stmt, ast.If) and any(
            isinstance(a, ast.Attribute)
            and isinstance(a.value, ast.Name)
            and a.value.id == "ActionType"
            for a in ast.walk(stmt.test)
        ):
            return stmt
    raise AssertionError("no `if action.type == ActionType...` dispatch chain found")


def _walk_chain(if_node: ast.If):
    node = if_node
    while True:
        member = next(
            (a.attr for a in ast.walk(node.test)
             if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name)
             and a.value.id == "ActionType"),
            None,
        )
        yield (member, node.body, False)
        orelse = node.orelse
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            node = orelse[0]
        else:
            yield (None, orelse, True)
            return


def _branches():
    return list(_walk_chain(_dispatch_if(_dispatch_func())))


def _awaited_call_names(node: ast.AST) -> set[str]:
    """Names directly awaited as `await name(...)` anywhere under node."""
    names: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Await) and isinstance(n.value, ast.Call):
            f = n.value.func
            if isinstance(f, ast.Name):
                names.add(f.id)
    return names


# ── (1) COVERAGE ──────────────────────────────────────────────────────────────
def test_coverage_every_action_type_has_a_branch():
    members = _action_type_members()
    handled = {m for m, _body, is_else in _branches() if m and not is_else}
    assert members, "no ActionType members parsed — test wiring broken"
    missing = members - handled
    assert not missing, f"dispatch_action has no branch for ActionType(s): {sorted(missing)}"


# ── (2) DISPATCH ──────────────────────────────────────────────────────────────
def test_each_branch_actually_dispatches_not_a_noop():
    for member, body, is_else in _branches():
        if is_else or member is None:
            continue
        has_real_dispatch = any(
            isinstance(n, ast.Await) and isinstance(n.value, ast.Call)
            for stmt in body for n in ast.walk(stmt)
        )
        assert has_real_dispatch, (
            f"ActionType.{member} branch has no `await <skill>(...)` dispatch"
        )


# ── (3) TOTALITY ──────────────────────────────────────────────────────────────
def test_chain_ends_in_else_that_raises():
    member, else_body, is_else = _branches()[-1]
    assert is_else, "dispatch chain has no terminal `else` — unknown ActionType silently no-ops"
    has_raise = any(isinstance(n, ast.Raise) for stmt in else_body for n in ast.walk(stmt))
    assert has_raise, "terminal `else` does not raise — unknown/future ActionType silently no-ops"


# ── (4) NO-DUP: neither caller awaits a skill directly ────────────────────────
@pytest.mark.parametrize("path,fn", [
    (_MCTS, "execute_browser_action"),
    (_ORCH, "handle_agentq_actions"),
])
def test_caller_does_not_inline_skill_dispatch(path, fn):
    awaited = _awaited_call_names(_func(path, fn))
    leaked = awaited & _SKILLS
    assert not leaked, (
        f"{fn} still awaits browser skill(s) {sorted(leaked)} directly — it must route through "
        f"dispatch_action instead (duplicate dispatch map)"
    )
    assert "dispatch_action" in awaited, f"{fn} does not await dispatch_action"


# ── (5) MAP-OWNS: dispatch_action awaits all five skills; the set is pinned ────
def test_dispatch_action_owns_the_whole_skill_map():
    awaited = _awaited_call_names(_dispatch_func())
    assert _SKILLS <= awaited, f"dispatch_action missing skill dispatch for: {sorted(_SKILLS - awaited)}"


# ── (6) SURFACES: unknown type raises, and the orchestrator bypasses the retry ─
def test_dispatch_action_raises_on_unknown_type():
    from agentq.core.skills.dispatch import dispatch_action, UnhandledActionTypeError
    bogus = SimpleNamespace(type="NOT_A_REAL_ACTION_TYPE")
    with pytest.raises(UnhandledActionTypeError):
        asyncio.run(
            dispatch_action(bogus, click_wait=1, enter_text_and_click_wait=1.5, captcha_wait=1)
        )


def test_orchestrator_reraises_unhandled_before_broad_except():
    fn = _func(_ORCH, "handle_agentq_actions")
    # find the try whose handlers include the typed bypass
    for tnode in ast.walk(fn):
        if not isinstance(tnode, ast.Try):
            continue
        names = [
            (h.type.id if isinstance(h.type, ast.Name) else None) for h in tnode.handlers
        ]
        if "UnhandledActionTypeError" in names and "Exception" in names:
            assert names.index("UnhandledActionTypeError") < names.index("Exception"), (
                "`except UnhandledActionTypeError` must come BEFORE `except Exception`"
            )
            # and it must re-raise, not swallow
            h = tnode.handlers[names.index("UnhandledActionTypeError")]
            assert any(isinstance(n, ast.Raise) for n in ast.walk(h)), (
                "the UnhandledActionTypeError handler must re-raise"
            )
            return
    raise AssertionError("handle_agentq_actions has no try with the typed-exception bypass")


# ── (7) SINK-WAITS: the caller's own wait reaches the skill (Option A) ─────────
# Each wait-bearing ActionType: (type, skill attr in dispatch module, action fields, the dispatch
# wait-param that should reach it, the skill's wait kwarg name). Covers ALL three wait-bearing branches
# (CLICK, ENTER_TEXT_AND_CLICK, SOLVE_CAPTCHA) so Option A is verified at every sink, not just CLICK.
_WAIT_SINKS = [
    (ActionType.CLICK, "click",
     dict(mmid="42", wait_before_execution=None), "click_wait", "wait_before_execution"),
    (ActionType.ENTER_TEXT_AND_CLICK, "enter_text_and_click",
     dict(text_element_mmid="1", text_to_enter="x", click_element_mmid="2", wait_before_click_execution=None),
     "enter_text_and_click_wait", "wait_before_click_execution"),
    (ActionType.SOLVE_CAPTCHA, "solve_captcha",
     dict(text_element_mmid="1", click_element_mmid="2", wait_before_click_execution=None),
     "captcha_wait", "wait_before_click_execution"),
]


@pytest.mark.parametrize("caller_wait", [1, 2])
@pytest.mark.parametrize("atype,skill,action_fields,wait_param,wait_kwarg", _WAIT_SINKS)
def test_dispatch_passes_callers_own_wait_to_skill(
    monkeypatch, caller_wait, atype, skill, action_fields, wait_param, wait_kwarg
):
    import agentq.core.skills.dispatch as dispatch_mod

    captured = {}

    async def fake_skill(**kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(dispatch_mod, skill, fake_skill)
    action = SimpleNamespace(type=atype, **action_fields)
    waits = {"click_wait": 1, "enter_text_and_click_wait": 1.5, "captcha_wait": 1}
    waits[wait_param] = caller_wait  # this branch's caller-supplied wait
    asyncio.run(dispatch_mod.dispatch_action(action, **waits))
    assert captured[wait_kwarg] == caller_wait  # the CALLER's wait reaches the skill (Option A)
