
import json
from typing import Dict, List
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage
from functools import partial
from dataclasses import dataclass, asdict, field
from typing import List, Optional

from chat.clients.workflows.agent_state import PipelineState
from chat.clients.workflows import all_tools
from chat.clients.workflows.checkpointer.async_redis_checkpointer import AsyncRedisCheckpointer
from chat.clients.workflows.checkpointer.sync_redis_checkpointer import SyncRedisCheckpointer
from chat.clients.workflows.workflow_node import WorkflowLlmNode
from basics.custom_exception import WorkflowCreationException
from langfuse.decorators import observe
from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)




@dataclass
class Serializable:
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)

@dataclass
class NodeData(Serializable):
    
    # Graph Feature
    uniq_id: str = ""
    pos_x: float = 0.0
    pos_y: float = 0.0
    width: float = 200.0  # Default width
    height: float = 200.0  # Default height


    nexts: List[int] = field(default_factory=list)

    # LangGraph attribute
    # "START", "STEP", "TOOL", "CONDITION"
    type: str = "START"

    # AGENT
    name: str = ""
    include_in_response: str = ""
    checkpoint: str = ""
    response_schema: str = ""

    # STEP
    tool: str = ""

    # CONDITION
    true_next: Optional[int] = None
    false_next: Optional[int] = None
    

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class WorkflowFactory:
    workflow_cache={}
    
    def __init__(self):
        pass
        
    def get_workflow(self, workflow_name, workflow_json, workflow_type):
        if workflow_name not in WorkflowFactory.workflow_cache:
            WorkflowFactory.workflow_cache[workflow_name] = self.create_workflow(workflow_name, workflow_json, workflow_type)
            
        return WorkflowFactory.workflow_cache[workflow_name]
    
    def add_edges_default(self, workflow, node_map, step_nodes):
        print("\nAdding edges using default method...\n")
        # Find all next nodes from step_nodes
        for node in step_nodes:
            print("Current Node: ", node.name)
            next_nodes = [node_map[next_id] for next_id in node.nexts]
            conditional_map = {}
            step_neighbors = []  
            conditional_neighbors=[]   
            for next_node in next_nodes:
                print(f"{node.name}'s next node: {next_node.name}, Type: {next_node.type}")
                workflow_logger.add(f"{node.name}'s next node: {next_node.name}, Type: {next_node.type}")
                if next_node.type == "STEP":
                    step_neighbors.append(next_node.name)
                elif next_node.type == "CONDITION":
                    next_conditional_nodes = [node_map[next_id] for next_id in next_node.nexts]
                    conditional_neighbors.extend([next_cond_node.name for next_cond_node in next_conditional_nodes])
    
                        
            if node.tool:
                tool_names = node.tool.split(',')
                for tool in tool_names:
                    tool = tool.replace(" ", "")
                    conditional_map[tool] = node.name+"_"+tool
                    workflow.add_edge(node.name+"_"+tool, node.name)
                    
                if step_neighbors:
                    workflow.add_conditional_edges(node.name, partial(self.router_step, neighbors=step_neighbors, tool_neighbors={}))
                elif conditional_neighbors:
                    workflow.add_conditional_edges(node.name, partial(self.router_conditional, neighbors=conditional_neighbors, tool_neighbors={}))
                else :
                    workflow.add_conditional_edges(node.name, partial(self.router_conditional, neighbors=conditional_neighbors, tool_neighbors={}))
            else:
                if step_neighbors:
                    for neighbor in step_neighbors:
                        workflow.add_edge(node.name, neighbor)
                elif conditional_neighbors:
                    workflow.add_conditional_edges(node.name, partial(self.router_conditional, neighbors=conditional_neighbors, tool_neighbors={}))
    
    def add_edges_custom(self, workflow, node_map, step_nodes):
        print("\nAdding edges using custom method...\n")
        # Find all next nodes from step_nodes
        for node in step_nodes:
            print("Current Node: ", node.name)
            next_nodes = [node_map[next_id] for next_id in node.nexts]
            step_neighbors = []
            conditional_neighbors = []
            tool_neighbors = {}
            for next_node in next_nodes:
                print(f"{node.name}'s next node: {next_node.name}, Type: {next_node.type}")
                workflow_logger.add(f"{node.name}'s next node: {next_node.name}, Type: {next_node.type}")
                if next_node.type == 'STEP':
                    step_neighbors.append(next_node.name)
                elif next_node.type == 'CONDITION':
                    conditional_neighbors.extend([node_map[next_id].name for next_id in next_node.nexts])
                elif next_node.type == 'TOOL':
                    tool_next = [node_map[next_id].name for next_id in next_node.nexts]
                    
                    if node.name not in tool_next:
                        tool_neighbors[next_node.name] = tool_next
                        
                    workflow.add_edge(next_node.name, node.name)
                        
                    
                        
            if step_neighbors or tool_neighbors:
                workflow.add_conditional_edges(node.name, partial(self.router_step, neighbors=step_neighbors, tool_neighbors=tool_neighbors))
            else:
                workflow.add_conditional_edges(node.name, partial(self.router_conditional, neighbors=conditional_neighbors, tool_neighbors=tool_neighbors))
                
            
                    
    @observe()  
    def create_workflow(self, workflow_name, workflow_json, workflow_type):
        node_map = self.load_nodes_from_json(workflow_name, workflow_json)

        # Define the state machine
        workflow = StateGraph(PipelineState)

        # Start node, only one start point
        start_node = self.find_nodes_by_type(node_map, "START")[0]
        print(f"Start root ID: {start_node.uniq_id}")
        workflow_logger.add(f"Start root ID: {start_node.uniq_id}")
        

        # Step nodes
        tool_nodes_created = []
        step_nodes = self.find_nodes_by_type(node_map, "STEP")
        for current_node in step_nodes:
            print("Current Step Node: ", current_node.name)
            workflow_logger.add(f"Current Step Node: {current_node.name}")
            
            tools_list = []
            if current_node.tool:
                tool_names = current_node.tool.split(',')
                for tool in tool_names:
                    tool = tool.replace(" ", "")
                    tools_list.append(getattr(all_tools, tool))
                    if tool not in tool_nodes_created:
                        workflow.add_node(current_node.name+"_"+tool, ToolNode([getattr(all_tools, tool)]))
                        tool_nodes_created.append(current_node.name+"_"+tool)
            else:
                next_nodes = [node_map[next_id] for next_id in current_node.nexts]
                for next_node in next_nodes:
                    if next_node.type == 'TOOL':
                        if not next_node.name:
                            raise WorkflowCreationException(f"Workflow : {workflow_name} | Error: Tool name must be given.")
                        tools_list.append(getattr(all_tools, next_node.name))
            
            workflow_node = WorkflowLlmNode(name=current_node.name, tools=tools_list, prompt_name=current_node.name, include_in_final_response=current_node.include_in_response, response_schema=current_node.response_schema)
            workflow.add_node(current_node.name, workflow_node.execute, metadata={"include": current_node.include_in_response})
        
        # Tool nodes
        tool_nodes = self.find_nodes_by_type(node_map, "TOOL")
        for node in tool_nodes:
            print("Current Tool Node: ", node.name)
            workflow_logger.add(f"Current Tool Node: {node.name}")
            if not node.name:
                raise WorkflowCreationException(f"Workflow : {workflow_name} | Error: Tool name must be given.")
            workflow.add_node(node.name, ToolNode([getattr(all_tools, node.name)]))
        
        
        if start_node.checkpoint:
            print("checkpoint found")
            workflow.add_node("__workflow_start__", getattr(all_tools, start_node.checkpoint))
            workflow.add_edge(START, "__workflow_start__")
            
            next_node_ids = start_node.nexts
            next_nodes = [node_map[next_id] for next_id in next_node_ids]
            next_node_names = []
            for next_node in next_nodes:
                next_node_names.append(next_node.name)
                
            workflow.add_conditional_edges("__workflow_start__", partial(self.waha_router, neighbors=next_node_names))
        else:
            print("No checkpoint")
            # Find all next nodes from start_node
            next_node_ids = start_node.nexts
            next_nodes = [node_map[next_id] for next_id in next_node_ids]
            for next_node in next_nodes:
                print(f"Next node name: {next_node.name}, Type: {next_node.type}")
                workflow_logger.add(f"Next node name: {next_node.name}, Type: {next_node.type}")
                
                workflow.add_edge(START, next_node.name)

        # Edges
            
        # If workflow_type is default then add_edges_default will be called otherwise add_edges_custom will be called
        add_edges = getattr(self, f"add_edges_{workflow_type}")
        add_edges(workflow, node_map, step_nodes)
        
        checkpointer = AsyncRedisCheckpointer.from_cache_service()

        app = workflow.compile(checkpointer=checkpointer)
        # app = workflow.compile()
        print("Workflow created!")
        workflow_logger.add("Workflow created!")
        return app
    
            
    @observe()
    def load_nodes_from_json(self, workflow_name, data) -> Dict[str, NodeData]:
        """Adding try catch in case json file is unable to load for any reason while workflow creation."""
        try:
            node_map = {}
            for node_data in data["nodes"]:
                node = NodeData.from_dict(node_data)
                node_map[node.uniq_id] = node
            return node_map
        except Exception as e:
            workflow_logger.add(f"Error: {e}")
            print(f"Error: {e}")
            raise WorkflowCreationException(f"Unable to load json for workflow: {workflow_name}")
        
    @observe()
    def find_nodes_by_type(self, node_map: Dict[str, NodeData], node_type: str) -> List[NodeData]:
        
        return [node for node in node_map.values() if node.type == node_type]
    
    @observe()
    def router_conditional(self, state: PipelineState, neighbors:List, tool_neighbors:Dict):
        
        if state["messages"][-1].tool_calls:
            return state['messages'][-1].name+"_"+ state["messages"][-1].tool_calls[0]['name']
        
        if len(state["messages"]) > 1 and isinstance(state["messages"][-2], ToolMessage):
            for next in tool_neighbors.get(state["messages"][-2].name, []):
                if next not in neighbors:
                    neighbors.append(next)
                    
        message = state["messages"][-1].content.lower()
        for neighbor in sorted(neighbors, key=len, reverse=True):
            
            try :
                json_message = json.loads(message)
                if message.startswith("{") or message.startswith("["): 
                    if state["response_format_schema"] and "agent_redirect_response_format" in state["response_format_schema"]:
                        message = json_message.get("next_agent", "")
                        
                    if neighbor.lower() in message.lower():
                        state['messages'][-1].content = json_message.get("content", "")
                        return neighbor
                else:
                    raise ValueError
            except ValueError:
                print("Not a json response")
                    
                if neighbor.lower() in message.lower():
                    state['messages'][-1].content = ''
                    return neighbor
        
        return END
    
    @observe()
    def router_step(self, state: PipelineState, neighbors:List, tool_neighbors:Dict):
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return last_message.name+"_"+last_message.tool_calls[0]['name']
        
        if len(state["messages"]) > 1 and isinstance(state["messages"][-2], ToolMessage):
            for next in tool_neighbors.get(state["messages"][-2].name, []):
                if next not in neighbors:
                    neighbors.append(next)
        
        return neighbors
        
    def waha_router(self, state: PipelineState, neighbors:List):
        last_message = state["messages"][-1]
        state["messages"] = state["messages"][:-1]
        if last_message.content == 'ignore':
            return END
        
        return neighbors

