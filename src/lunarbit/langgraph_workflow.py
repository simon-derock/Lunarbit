"""Checkpointable LangGraph orchestration for the private GraphRAG runtime.

LangGraph owns workflow state and transitions; the governed planner, Neo4j
reader, deterministic arithmetic, and evidence verifier remain authoritative.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict, cast

from pydantic import ValidationError

from lunarbit.agent import QueryPlan, build_query_plan
from lunarbit.guardrails import QuestionGuardrailError, validate_user_question
from lunarbit.query_planner import ResilientQueryPlanner
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


class LangGraphInputError(ValueError):
    """Raised when a workflow request or thread identifier is invalid."""


class LangGraphGuardrailError(LangGraphInputError):
    """Raised when a question is rejected by Lunarbit's request guardrails."""


class LangGraphExecutionError(RuntimeError):
    """Raised when a workflow node fails during execution."""


class LangGraphStateError(RuntimeError):
    """Raised when a compiled graph returns an invalid or incomplete state."""


class LangGraphCheckpointError(LookupError):
    """Raised when a requested conversation checkpoint does not exist."""


class WorkflowState(TypedDict, total=False):
    """Serializable state carried between governed workflow nodes."""

    question: str
    slots: QuerySlots
    request: RuntimeRequest
    classification: QueryClassification
    plan: QueryPlan
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


def _plan_node(
    state: WorkflowState, *, planner: ResilientQueryPlanner | None = None
) -> WorkflowState:
    request = RuntimeRequest(question=state["question"], slots=state["slots"])
    # The planner is invoked by the runtime and retained in state as an audit
    # signal for tracing and future conditional routing.
    if planner is None:
        plan = build_query_plan(request.question)
        slots = state["slots"]
    else:
        plan, proposed_slots = planner.plan(request.question)
        proposed_values = proposed_slots.model_dump(exclude_unset=True)
        proposed_values.pop("operations", None)
        slots = QuerySlots.model_validate({**state["slots"].model_dump(), **proposed_values})
        request = RuntimeRequest(question=state["question"], slots=slots)
    return {
        "request": request,
        "classification": plan.classification,
        "plan": plan,
    }


def _retrieve_and_verify_node(state: WorkflowState, *, reader: GraphReader) -> WorkflowState:
    context = retrieve_grounded_context(state["request"], reader, plan=state.get("plan"))
    return {"context": context, "status": context.status.value}


def _finalize_node(state: WorkflowState) -> WorkflowState:
    context = state["context"]
    return {"status": context.status.value}


class GraphRAGWorkflow:
    """Run a bounded, checkpointed GraphRAG workflow for one private session."""

    def __init__(
        self,
        reader: GraphReader,
        *,
        checkpointer: object | None = None,
        planner: ResilientQueryPlanner | None = None,
    ) -> None:
        _require_langgraph()
        if checkpointer is None:
            assert MemorySaver is not None
            checkpointer = MemorySaver()
        self._graph = self._compile(reader, checkpointer, planner)

    @staticmethod
    def _compile(
        reader: GraphReader,
        checkpointer: Any,
        planner: ResilientQueryPlanner | None,
    ) -> Any:
        assert StateGraph is not None
        builder = StateGraph(WorkflowState)
        builder.add_node("guardrail", _guardrail_node)
        builder.add_node("plan", lambda state: _plan_node(state, planner=planner))
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
        if not isinstance(question, str) or not question.strip():
            raise LangGraphInputError("question must be a non-empty string")
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise LangGraphInputError("thread_id must be a non-empty string")
        if slots is not None and not isinstance(slots, QuerySlots):
            raise LangGraphInputError("slots must be a QuerySlots instance")
        initial: WorkflowState = {"question": question, "slots": slots or QuerySlots()}
        try:
            result = self._graph.invoke(
                initial,
                config={"configurable": {"thread_id": thread_id}},
            )
        except QuestionGuardrailError as error:
            raise LangGraphGuardrailError(str(error)) from error
        except ValidationError as error:
            raise LangGraphInputError("workflow state validation failed") from error
        except (LangGraphInputError, LangGraphGuardrailError, LangGraphStateError):
            raise
        except Exception as error:
            raise LangGraphExecutionError("workflow execution failed") from error
        context = result.get("context")
        if not isinstance(context, GroundedContext):
            raise LangGraphStateError("workflow completed without grounded context")
        return context

    def state(self, *, thread_id: str = "default") -> Mapping[str, object] | None:
        """Expose checkpoint metadata for observability without raw evidence."""
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise LangGraphInputError("thread_id must be a non-empty string")
        try:
            snapshot = self._graph.get_state({"configurable": {"thread_id": thread_id}})
        except Exception as error:
            raise LangGraphCheckpointError("conversation checkpoint not found") from error
        if snapshot is None or not snapshot.values:
            raise LangGraphCheckpointError("conversation checkpoint not found")
        return cast(Mapping[str, object], snapshot.values)
