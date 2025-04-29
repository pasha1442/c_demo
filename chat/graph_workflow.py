import importlib
import inspect
import os
import json
import re
from typing import Dict, List, TypedDict, Any, Annotated, Callable, Literal, Union
import operator

from langchain_openai import ChatOpenAI
from backend import settings
from chat.node_data import NodeData
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage, FunctionMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END, START

# Tool registry to hold information about tools
tool_registry: Dict[str, Callable] = {}

# Decorator to register tools
def tool(func: Callable) -> Callable:
    tool_registry[func.__name__] = func
    return func

def load_nodes_from_json(json_input: Union[str, Dict]) -> Dict[str, NodeData]:
    if isinstance(json_input, str):
        with open(json_input, 'r') as file:
            data = json.load(file)
    elif isinstance(json_input, dict):
        data = json_input
    else:
        raise TypeError(f"Expected str (file path) or dict (loaded JSON), not {type(json_input)}")
    
    node_map = {}
    for node_data in data["nodes"]:
        node = NodeData.from_dict(node_data)
        node_map[node.uniq_id] = node
    return node_map

def find_nodes_by_type(node_map: Dict[str, NodeData], node_type: str) -> List[NodeData]:
    return [node for node in node_map.values() if node.type == node_type]

class PipelineState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    task: str
    condition: bool
    tool_calls: int
    max_tool_calls: int

def execute_step(name: str, state: PipelineState, prompt_template: str, llm) -> PipelineState:
    print(f"Executing step: {name}")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_template),
        MessagesPlaceholder(variable_name="messages"),
    ])
    OPENAI_API_KEY = os.getenv('OPEN_AI_KEY')
    api_key = OPENAI_API_KEY
    llm = ChatOpenAI(temperature=0, model="gpt-4o", openai_api_key=api_key)
    chain = prompt | llm | StrOutputParser()
    
    response = chain.invoke({"messages": state["messages"]})
    
    state["messages"].append(AIMessage(content=response))
    return state

def get_tool_signature(tool_name: str) -> str:
    if tool_name not in tool_registry:
        raise ValueError(f"Tool {tool_name} not found in registry.")
    
    tool_func = tool_registry[tool_name]
    signature = inspect.signature(tool_func)
    params = []
    for name, param in signature.parameters.items():
        if param.default is inspect.Parameter.empty:
            params.append(f"{name}")
        else:
            params.append(f"{name}={param.default}")
    
    return f"{tool_name}({', '.join(params)})"

def execute_tool(name: str, state: PipelineState, prompt_template: str, llm, tool_name: str) -> PipelineState:
    print(f"Executing tool: {name} (Call {state['tool_calls'] + 1}/{state['max_tool_calls']})")
    tool_signature = get_tool_signature(tool_name)
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=f"""
        {prompt_template}
        You can call the tool '{tool_name}' up to {state['max_tool_calls']} times.
        Current call: {state['tool_calls'] + 1}.
        The tool signature is: {tool_signature}
        If you need to use the tool, include a JSON in this format in your response:
        {{"function": "{tool_name}", "args": {{"arg1": value1, "arg2": value2, ...}}}}
        Make sure to use the correct argument names as specified in the tool signature.
        You can provide explanations before and after the JSON.
        If you don't need to use the tool or have the final answer, respond normally without including any JSON.
        """),
        MessagesPlaceholder(variable_name="messages"),
    ])
    OPENAI_API_KEY = os.getenv('OPEN_AI_KEY')
    api_key = OPENAI_API_KEY
    llm = ChatOpenAI(temperature=0, model="gpt-4o", openai_api_key=api_key)
    chain = prompt | llm | StrOutputParser()
    
    while state['tool_calls'] < state['max_tool_calls']:
        response = chain.invoke({"messages": state["messages"]})
        
        # Extract JSON from the response if it exists
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        
        if json_match:
            json_str = json_match.group()
            try:
                data = json.loads(json_str)
                if "function" in data and "args" in data and data["function"] == tool_name:
                    args = data["args"]
                    
                    if tool_name not in tool_registry:
                        raise ValueError(f"Tool {tool_name} not found in registry.")
                    
                    # print(f"Executing tool: {tool_name} with args: {args}")
                    result = tool_registry[tool_name](*args)
                    # print("result after tool is called\n\n\n\n\n",result,"\n\n\n\n\n\n")
                    state["tool_calls"] += 1
                    
                    # Extract the explanation part (if any) before the JSON
                    explanation = response[:json_match.start()].strip()
                    if explanation:
                        state["messages"].append(AIMessage(content=explanation))
                    
                    state["messages"].append(AIMessage(content=f"Tool {tool_name} executed"))
                    state["messages"].append(FunctionMessage(name = f"{tool_name}", content=result))
                    # Extract any content after the JSON (if any)
                    after_json = response[json_match.end():].strip()
                    if after_json:
                        state["messages"].append(AIMessage(content=after_json))
                else:
                    # JSON found but not a valid tool call
                    state["messages"].append(AIMessage(content=response))
                    break
            except json.JSONDecodeError as e:
                print("JSONDecodeError",e)
                # Invalid JSON, treat the whole response as natural language
                state["messages"].append(AIMessage(content=response))
                break
        else:
            # No JSON found, treat the whole response as natural language
            state["messages"].append(AIMessage(content=response))
            break
    
    return state

def condition_switch(name: str, state: PipelineState, prompt_template: str, llm) -> PipelineState:
    print(f"Evaluating condition: {name}")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_template),
        MessagesPlaceholder(variable_name="messages"),
    ])
    chain = prompt | llm | StrOutputParser()
    
    response = chain.invoke({"messages": state["messages"]})
    
    try:
        data = json.loads(response)
        condition = data["switch"]
        state["condition"] = condition
        state["messages"].append(AIMessage(content=f"Condition evaluated to: {condition}"))
    except json.JSONDecodeError:
        state["condition"] = False
        state["messages"].append(AIMessage(content=f"Failed to parse condition. Defaulting to False. Response: {response}"))
    
    return state

def conditional_edge(state: PipelineState) -> Literal["True", "False"]:
    return "True" if state["condition"] else "False"

def RunWorkFlow(node_map: Dict[str, NodeData], default_llm, tools_module: Any, max_tool_calls: int = 3):
    workflow = StateGraph(PipelineState)
    
    start_nodes = find_nodes_by_type(node_map, "START")
    if not start_nodes:
        raise ValueError("No START node found in the workflow")
    start_node = start_nodes[0]
    print(f"Start node ID: {start_node.uniq_id}")
    
    # Add all nodes to the graph
    for current_node in node_map.values():
        print(f"Processing node: {current_node.name} (ID: {current_node.uniq_id}, Type: {current_node.type})")
        if current_node.type == "START":
            workflow.add_node(current_node.uniq_id, lambda x: x)
        elif current_node.type == "STEP":
            llm = current_node.llm if current_node.llm else default_llm
            if current_node.tool:
                prompt_template = f"""
                {current_node.description}
                Available tool: {current_node.tool}
                Based on the available tool, provide arguments in the JSON format:
                {{"function": "{current_node.tool}", "args": [<arg1>, <arg2>, ...]}}
                """
                workflow.add_node(
                    current_node.uniq_id, 
                    lambda state, template=prompt_template, llm=llm, tool=current_node.tool, name=current_node.name: 
                        execute_tool(name, state, template, llm, tool)
                )
            else:
                prompt_template = current_node.description
                workflow.add_node(
                    current_node.uniq_id, 
                    lambda state, template=prompt_template, llm=llm, name=current_node.name: execute_step(name, state, template, llm)
                )
        elif current_node.type == "CONDITION":
            llm = current_node.llm if current_node.llm else default_llm
            condition_template = f"""
            {current_node.description}
            Decide the condition result in the JSON format:
            {{"switch": true/false}}
            """
            workflow.add_node(
                current_node.uniq_id, 
                lambda state, template=condition_template, llm=llm, name=current_node.name: condition_switch(name, state, template, llm)
            )
    
    # Add edges
    for node in node_map.values():
        if node.type == "START":
            for next_id in node.nexts:
                workflow.add_edge(node.uniq_id, next_id)
        elif node.type == "CONDITION":
            workflow.add_conditional_edges(
                node.uniq_id,
                conditional_edge,
                {
                    "True": node.true_next if node.true_next else END,
                    "False": node.false_next if node.false_next else END
                }
            )
        else:
            for next_id in node.nexts:
                if next_id in node_map:
                    workflow.add_edge(node.uniq_id, next_id)
                elif next_id == "END":
                    workflow.add_edge(node.uniq_id, END)
    
    # Add edge from langgraph START to our start node
    workflow.add_edge(START, start_node.uniq_id)
    
    initial_state = PipelineState(
        messages=[HumanMessage(content="Can you search the archives to find the shloka in sanskrit about atma and paramatma")],
        task="",
        condition=False,
        tool_calls=0,
        max_tool_calls=max_tool_calls
    )
    
    app = workflow.compile()
    ########################
    from IPython.display import Image, display

    try:
        img_data = app.get_graph(xray=True).draw_mermaid_png()
        with open("output.png", "wb") as f:
            f.write(img_data)
    except Exception:
        # This requires some extra dependencies and is optional
        pass
    ########################
    all_ai_messages = []

    for state in app.stream(initial_state):
        # print(f"\n\nCurrent state: {state}\n\n")
        # Collect AI messages from all nodes
        for node_state in state.values():
            if "messages" in node_state:
                ai_messages = [msg.content for msg in node_state["messages"] if isinstance(msg, AIMessage)]
                all_ai_messages.extend(ai_messages)

    unique_ai_messages = []
    seen = set()
    for message in all_ai_messages:
        if message not in seen:
            seen.add(message)
            unique_ai_messages.append(message)

    return unique_ai_messages
    
    return "Workflow completed without final message"
    # return final_state["messages"][-1].content if final_state and final_state["messages"] else "Workflow completed without final message"

def load_tools(tool_file: str) -> Any:
    full_path = os.path.join(settings.BASE_DIR, 'chat', tool_file)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Tool file not found: {full_path}")
    
    spec = importlib.util.spec_from_file_location("tools", full_path)
    tools_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tools_module)
    return tools_module

def run_workflow(json_input: Union[str, Dict], default_llm, tool_file: str, max_tool_calls: int = 3):
    try:
        node_map = load_nodes_from_json(json_input)
        tools_module = load_tools(tool_file)
        return RunWorkFlow(node_map, default_llm, tools_module, max_tool_calls)
    except Exception as e:
        print(f"Error in run_workflow: {str(e)}")
        return f"Error occurred: {str(e)}"

def run_workflow_for_client(company_name: str, default_llm, tool_file: str, max_tool_calls: int = 3):
    try:
        client_json = get_client_flow_json(company_name)
        return run_workflow(client_json, default_llm, tool_file, max_tool_calls)
    except Exception as e:
        print(f"Error in run_workflow_for_client: {str(e)}")
        return f"Error occurred for client {company_name}: {str(e)}"

def get_client_flow_json(company_name: str) -> Dict:
    sanitized_name = ''.join(c.lower() for c in company_name if c.isalnum())
    file_path = os.path.join(settings.BASE_DIR, 'chat', 'clients', 'flows', f"{sanitized_name}.json")
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"No JSON file found for the organization: {company_name}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON file for the organization: {company_name}")