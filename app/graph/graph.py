from langgraph.graph import END, StateGraph

from app.graph.nodes import generate_node, guardrails_in, guardrails_out, retrieve_node
from app.graph.state import ChatState


def build_graph():
    g = StateGraph(ChatState)
    g.add_node("guardrails_in", guardrails_in)
    g.add_node("retrieve", retrieve_node)
    g.add_node("generate", generate_node)
    g.add_node("guardrails_out", guardrails_out)

    g.set_entry_point("guardrails_in")

    def after_input(state: ChatState):
        return "end" if state.get("blocked") else "retrieve"

    g.add_conditional_edges("guardrails_in", after_input, {"end": END, "retrieve": "retrieve"})
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "guardrails_out")
    g.add_edge("guardrails_out", END)
    return g.compile()


graph = build_graph()