import json
from enum import Enum
from typing import Sequence, Union

from agentq.core.mcts.core.mcts import MCTSNode, MCTSResult
from agentq.core.mcts.visualization.tree_snapshot import (
    EdgeData,
    EdgeId,
    NodeData,
    NodeId,
    TreeSnapshot,
)


class TreeLogEncoder(json.JSONEncoder):
    def default(self, o):
        from numpy import float32

        if isinstance(o, TreeSnapshot.Node):
            return o.__dict__
        elif isinstance(o, TreeSnapshot.Edge):
            return o.__dict__
        elif isinstance(o, TreeSnapshot):
            return o.__dict__()
        elif isinstance(o, float32):
            return float(o)
        elif isinstance(o, TreeLog):
            return {"logs": list(o)}
        elif hasattr(o, "__dict__"):
            return o.__dict__
        elif isinstance(o, Enum):
            return o.value
        else:
            return str(o)


class TreeLog:
    def __init__(self, tree_snapshots: Sequence[TreeSnapshot]) -> None:
        self._tree_snapshots = tree_snapshots

    def __getitem__(self, item):
        return self._tree_snapshots[item]

    def __iter__(self):
        return iter(self._tree_snapshots)

    def __len__(self):
        return len(self._tree_snapshots)

    def __str__(self):
        return json.dumps(self, cls=TreeLogEncoder, indent=2)

    @classmethod
    def from_mcts_results(
        cls,
        mcts_results: MCTSResult,
        node_data_factory: callable = None,
        edge_data_factory: callable = None,
    ) -> "TreeLog":
        def get_reward_details(n: MCTSNode) -> Union[dict, None]:
            if hasattr(n, "reward_details"):
                return n.reward_details
            return n.fast_reward_details if hasattr(n, "fast_reward_details") else None

        def default_node_data_factory(n: MCTSNode) -> NodeData:
            if not n.state:
                return NodeData({})
            if hasattr(n.state, "_asdict"):
                state_dict = n.state._asdict()
            elif isinstance(n.state, list):
                state_dict = {idx: value for idx, value in enumerate(n.state)}
            else:
                try:
                    state_dict = json.loads(json.dumps(n.state, cls=TreeLogEncoder))
                except TypeError:
                    state_dict = str(n.state)

            # Add color information to the node data
            state_dict["color"] = "green"
            return NodeData(state_dict)

        def default_edge_data_factory(n: MCTSNode) -> EdgeData:
            edge_data = {"Q": n.Q, "reward": n.reward, **get_reward_details(n)}

            # Add color information to the edge data
            edge_data["color"] = "brown"
            return EdgeData(edge_data)

        node_data_factory = node_data_factory or default_node_data_factory
        edge_data_factory = edge_data_factory or default_edge_data_factory

        snapshots = []

        def all_nodes(node: MCTSNode):
            node_id = NodeId(node.id)

            nodes[node_id] = TreeSnapshot.Node(node_id, node_data_factory(node))
            if node.children is None:
                return
            for child in node.children:
                edge_id = EdgeId(len(edges))
                edges.append(
                    TreeSnapshot.Edge(
                        edge_id, node.id, child.id, edge_data_factory(child)
                    )
                )
                all_nodes(child)

        if mcts_results.tree_state_after_each_iter is None:
            tree_states = [mcts_results.tree_state]
        else:
            tree_states = mcts_results.tree_state_after_each_iter
        for step in range(len(tree_states)):
            edges = []
            nodes = {}

            root = tree_states[step]
            all_nodes(root)
            tree = TreeSnapshot(list(nodes.values()), edges)

            if mcts_results.trace_in_each_iter:
                trace = mcts_results.trace_in_each_iter[step]
                for step_idx in range(len(trace) - 1):
                    in_node_id = trace[step_idx].id
                    out_node_id = trace[step_idx + 1].id
                    for edges in tree.out_edges(in_node_id):
                        if edges.target == out_node_id:
                            nodes[in_node_id].selected_edge = edges.id
                            break

            for node in tree.nodes.values():
                if node.selected_edge is None and tree.children(node.id):
                    node.selected_edge = max(
                        tree.out_edges(node.id),
                        key=lambda edge: edge.data.get("Q", -float("inf")),
                    ).id

            snapshots.append(tree)

        return cls(snapshots)
