import asyncio

from flask import Flask, jsonify, request

from agentq.__main__ import run_agent_sync
from agentq.core.mcts.browser_mcts import main as run_browser_mcts

app = Flask(__name__)


@app.route("/execute", methods=["GET"])
def execute_command():
    goal = request.args.get("goal")
    if not goal:
        return jsonify({"error": "No command provided"}), 400

    # Ensure we have an event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run the agent asynchronously
    result = run_agent_sync(command=goal)
    return jsonify({"result": result})


@app.route("/execute_mcts", methods=["GET"])
def run_mcts():
    objective = request.args.get("goal")
    if not objective:
        return jsonify({"error": "No objective provided"}), 400

    # Ensure we have an event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run the MCTS algorithm asynchronously
    result = loop.run_until_complete(run_browser_mcts(objective, eval_mode=True))
    return result


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=False)
