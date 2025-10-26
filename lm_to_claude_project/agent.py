from typing import List, TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.llms import Ollama
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import operator
import os
import json

# --- Core Tools --- 
# These are the only functions the agent will call directly.
from skills.test_case_retriever.functions import get_test_case_details

# --- Helper Functions for the Agent --- 

def _read_file(path):
    """Helper to read a file, returns empty string if not found."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""

def find_relevant_skill_package(query: str) -> str:
    """Finds the most relevant skill package directory based on keywords."""
    # In a real scenario, this could be a more sophisticated search.
    # For this workflow, we know the end goal is always to assemble a test.
    if "test" in query.lower() or "commonr" in query.lower():
        return "/Users/admin/Documents/2025_project/QE_RAG_COMPANY/QE_RAG_2025/lm_to_claude_project/skills/g-sdk_test_assembler"
    return ""

def load_skill_package_and_guides(skill_path: str) -> dict:
    """Loads all content from a skill package and all G-SDK guides."""
    context = {}
    
    # 1. Load the chosen skill package
    if os.path.isdir(skill_path):
        skill_content = []
        for filename in os.listdir(skill_path):
            content = _read_file(os.path.join(skill_path, filename))
            skill_content.append(f"--- START {filename} ---\n{content}\n--- END {filename} ---")
        context["skill_package"] = "\n".join(skill_content)
    
    # 2. Load all G-SDK guides
    base_guide_path = "/Users/admin/Documents/2025_project/QE_RAG_COMPANY/QE_RAG_2025/gsdk_rag_context"
    context["workflow_guide"] = _read_file(os.path.join(base_guide_path, "01_WORKFLOW_GUIDE.md"))
    context["reference_guide"] = _read_file(os.path.join(base_guide_path, "02_REFERENCE_GUIDE.md"))
    context["test_data_guide"] = _read_file(os.path.join(base_guide_path, "03_TEST_DATA_GUIDE.md")),
    
    # 3. Load all G-SDK resources
    resource_path = os.path.join(base_guide_path, "resources")
    context["category_map"] = _read_file(os.path.join(resource_path, "category_map.json"))
    context["event_codes"] = _read_file(os.path.join(resource_path, "event_codes.json"))
    context["manager_api_index"] = _read_file(os.path.join(resource_path, "manager_api_index.json"))

    return context

# --- Agent State Definition --- 

class AgentState(TypedDict):
    original_query: str
    test_case_details: str
    skill_path: str
    full_context: dict
    final_script: str
    messages: Annotated[List[BaseMessage], operator.add]

# --- Agent Node Functions --- 

llm = Ollama(model="gpt-oss/gpt-oss-20b", base_url="http://127.0.0.1:1234/v1", temperature=0.0)

def retrieve_test_case_node(state: AgentState):
    print("--- Node: retrieve_test_case --- ")
    query = state['original_query']
    details = get_test_case_details(query)
    return {"test_case_details": details, "messages": [HumanMessage(content=f"Test case details retrieved: {details}")]}

def find_skill_node(state: AgentState):
    print("--- Node: find_skill --- ")
    query = state['original_query']
    skill_path = find_relevant_skill_package(query)
    return {"skill_path": skill_path}

def load_context_node(state: AgentState):
    print("--- Node: load_context --- ")
    skill_path = state['skill_path']
    full_context = load_skill_package_and_guides(skill_path)
    return {"full_context": full_context}

def generate_script_node(state: AgentState):
    print("--- Node: generate_script --- ")
    test_case_details = state['test_case_details']
    full_context = state['full_context']

    system_prompt = """You are an elite G-SDK Test Automation Engineer. Your task is to generate a single, complete, and runnable Python unittest script based on the provided context.

1.  **GOAL**: First, understand the user's goal from the 'Test Case Details'.
2.  **STUDY**: Second, you MUST study the provided 'G-SDK Guides' and the 'Skill Package' to understand the correct coding patterns, APIs, and constants.
3.  **GENERATE**: Finally, generate the complete Python script. Do not explain, just provide the code in a single block.

--- GOAL: Test Case Details ---
{test_case_details}

--- KNOWLEDGE: G-SDK Guides ---
{guides}

--- KNOWLEDGE: Skill Package ---
{skill_package}
"""
    
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt)])
    
    chain = prompt | llm

    # Prepare the context for the prompt
    guides_context = f"\n[WORKFLOW GUIDE]\n{full_context['workflow_guide']}\n\n[REFERENCE GUIDE]\n{full_context['reference_guide']}\n\n[TEST DATA GUIDE]\n{full_context['test_data_guide']}\n\n[RESOURCES]\n{full_context['category_map']}\n{full_context['event_codes']}\n{full_context['manager_api_index']}"

    response = chain.invoke({
        "test_case_details": test_case_details,
        "guides": guides_context,
        "skill_package": full_context['skill_package']
    })
    
    return {"final_script": response.content}

# --- Graph Definition --- 

def create_agent_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("retrieve_test_case", retrieve_test_case_node)
    workflow.add_node("find_skill", find_skill_node)
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("generate_script", generate_script_node)

    workflow.set_entry_point("retrieve_test_case")
    workflow.add_edge("retrieve_test_case", "find_skill")
    workflow.add_edge("find_skill", "load_context")
    workflow.add_edge("load_context", "generate_script")
    workflow.add_edge("generate_script", END)

    return workflow.compile()
