import operator
from typing import Dict, List, Sequence, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, AnyMessage
from chat.workflow_context import WorkflowContext, WorkflowState
from langgraph.graph import add_messages


class PipelineState(TypedDict):
    # messages: Annotated[Sequence[BaseMessage], operator.add]
    messages: Annotated[list[AnyMessage], add_messages]
    sender: Annotated[str, operator.add]
    workflow_context: Annotated[WorkflowState, lambda workflow_context1, workflow_context2: workflow_context1]
    include: Annotated[str, operator.add]
    llm_info: Annotated[dict, lambda llm_info1, llm_info2: llm_info1]
    response_format_schema: Annotated[str, lambda response_format_schema1, response_format_schema2: response_format_schema1]

    @staticmethod
    def get_workflow_context_object_from_state(state) -> WorkflowContext:
        """
        Read the serialized workflow context from the state (dict) 
        and convert it back to a WorkflowContext object.
        """


        context_dict = state["workflow_context"]
        return WorkflowContext.from_dict(context_dict)