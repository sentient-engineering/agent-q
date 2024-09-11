import asyncio

from flask import Flask, jsonify, request

from agentq.__main__ import run_agent_sync

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=False)
