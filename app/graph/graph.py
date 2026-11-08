import logging

from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    check_input_node,
    check_output_node,
    generate_node,
    retrieve_node,
)
from app.graph.state import ChatState

log = logging.getLogger(__name__)


def build_graph():
    graph = StateGraph(ChatState)
    graph.add_node("check_input", check_input_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("check_output", check_output_node)

    graph.set_entry_point("check_input")

    def after_input(state: ChatState):
        return "end" if state.get("blocked") else "retrieve"

    graph.add_conditional_edges("check_input", after_input, {"end": END, "retrieve": "retrieve"})
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "check_output")
    graph.add_edge("check_output", END)
    return graph.compile()


graph = build_graph()


if __name__ == "__main__":  # uv run python -m app.graph.graph
    print(graph.get_graph().draw_mermaid())
