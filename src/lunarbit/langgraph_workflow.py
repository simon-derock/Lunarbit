"""Checkpointable LangGraph orchestration for the private GraphRAG runtime.

LangGraph owns workflow state and transitions; the governed planner, Neo4j
reader, deterministic arithmetic, and evidence verifier remain authoritative.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict, cast

from lunarbit.agent import build_query_plan
from lunarbit.guardrails import validate_user_question
from lunarbit.retrieval import QueryClassification
from lunarbit.runtime import (
    GraphReader,
    GroundedContext,
    QuerySlots,
    RuntimeRequest,
    retrieve_grounded_context,
)

try:
    from langgraph.checkpoint.memory import MemorySaver as _MemorySaver
    from langgraph.graph import END as _END
    from langgraph.graph import START as _START
    from langgraph.graph import StateGraph as _StateGraph
except ImportError as error:  # pragma: no cover - exercised only without the agent extra
    _MemorySaver: Any = None  # type: ignore[no-redef]
    _END: Any = None  # type: ignore[no-redef]
    _START: Any = None  # type: ignore[no-redef]
    _StateGraph: Any = None  # type: ignore[no-redef]
    _LANGGRAPH_IMPORT_ERROR: ImportError | None = error
else:
    _LANGGRAPH_IMPORT_ERROR = None

MemorySaver = _MemorySaver
END = _END
START = _START
StateGraph = _StateGraph


class LangGraphUnavailableError(RuntimeError):
    """Raised when the optional LangGraph dependency has not been installed."""


class WorkflowState(TypedDict, total=False):
    """Serializable state carried between governed workflow nodes."""

    question: str
    slots: QuerySlots
    request: RuntimeRequest
    classification: QueryClassification
    context: GroundedContext
    status: str
    error: str


def _require_langgraph() -> None:
    if _LANGGRAPH_IMPORT_ERROR is not None:
        raise LangGraphUnavailableError(
            "install the agent extra to use the LangGraph workflow"
        ) from _LANGGRAPH_IMPORT_ERROR


def _guardrail_node(state: WorkflowState) -> WorkflowState:
    question = validate_user_question(state["question"])
    return {"question": question, "slots": state.get("slots", QuerySlots())}


def _plan_node(state: WorkflowState) -> WorkflowState:
    request = RuntimeRequest(question=state["question"], slots=state["slots"])
    # The planner is invoked by the runtime and retained in state as an audit
    # signal for tracing and future conditional routing.
    plan = build_query_plan(request.question)
    return {
        "request": request,
        "classification": plan.classification,
    }


def _retrieve_and_verify_node(state: WorkflowState, *, reader: GraphReader) -> WorkflowState:
    context = retrieve_grounded_context(state["request"], reader)
    return {"context": context, "status": context.status.value}


def _finalize_node(state: WorkflowState) -> WorkflowState:
    context = state["context"]
    return {"status": context.status.value}


class GraphRAGWorkflow:
    """Run a bounded, checkpointed GraphRAG workflow for one private session."""

    def __init__(self, reader: GraphReader, *, checkpointer: object | None = None) -> None:
        _require_langgraph()
        if checkpointer is None:
            assert MemorySaver is not None
            checkpointer = MemorySaver()
        self._graph = self._compile(reader, checkpointer)

    @staticmethod
    def _compile(reader: GraphReader, checkpointer: Any) -> Any:
        assert StateGraph is not None
        builder = StateGraph(WorkflowState)
        builder.add_node("guardrail", _guardrail_node)
        builder.add_node("plan", _plan_node)
        builder.add_node(
            "retrieve_and_verify",
            lambda state: _retrieve_and_verify_node(state, reader=reader),
        )
        builder.add_node("finalize", _finalize_node)
        builder.add_edge(START, "guardrail")
        builder.add_edge("guardrail", "plan")
        builder.add_edge("plan", "retrieve_and_verify")
        builder.add_edge("retrieve_and_verify", "finalize")
        builder.add_edge("finalize", END)
        return builder.compile(checkpointer=checkpointer)

    def invoke(
        self,
        question: str,
        *,
        slots: QuerySlots | None = None,
        thread_id: str = "default",
    ) -> GroundedContext:
        """Execute one turn and return only the verified runtime context."""
        initial: WorkflowState = {"question": question, "slots": slots or QuerySlots()}
        result = self._graph.invoke(initial, config={"configurable": {"thread_id": thread_id}})
        return cast(GroundedContext, result["context"])

    def state(self, *, thread_id: str = "default") -> Mapping[str, object] | None:
        """Expose checkpoint metadata for observability without raw evidence."""
        snapshot = self._graph.get_state({"configurable": {"thread_id": thread_id}})
        return snapshot.values if snapshot is not None else None
