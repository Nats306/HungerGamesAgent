"""LangGraph definition of the RAG agent.

    START
      |
    validate_intent --greeting--> greet ------------------------------+
      |            \\--unclear--> ask_clarification ------------------+
      | question                                                      |
    retrieve --(no chunk above threshold)--> reject -----------------+
      |                                                               |
    grade_context --(insufficient)--> reject                          |
      |                                                               |
    generate --(model says NO_ANSWER)--> reject                       |
      |                                                               v
      +----------------------------------------------------------> save_history --> END
"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agent import nodes
from app.agent.state import AgentState


@lru_cache
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("validate_intent", nodes.validate_intent)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("grade_context", nodes.grade_context)
    graph.add_node("generate", nodes.generate)
    graph.add_node("reject", nodes.reject)
    graph.add_node("greet", nodes.greet)
    graph.add_node("ask_clarification", nodes.ask_clarification)
    graph.add_node("save_history", nodes.save_history)

    graph.add_edge(START, "validate_intent")
    graph.add_conditional_edges(
        "validate_intent",
        nodes.route_intent,
        {"retrieve": "retrieve", "greet": "greet", "ask_clarification": "ask_clarification"},
    )
    graph.add_conditional_edges(
        "retrieve", nodes.route_after_retrieve, {"grade_context": "grade_context", "reject": "reject"}
    )
    graph.add_conditional_edges(
        "grade_context", nodes.route_after_grade, {"generate": "generate", "reject": "reject"}
    )
    graph.add_conditional_edges(
        "generate", nodes.route_after_generate, {"save_history": "save_history", "reject": "reject"}
    )
    for node in ("reject", "greet", "ask_clarification"):
        graph.add_edge(node, "save_history")
    graph.add_edge("save_history", END)

    return graph.compile()
