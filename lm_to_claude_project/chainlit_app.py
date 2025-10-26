import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import json
from agent import create_agent_graph

@cl.on_chat_start
async def start():
    """
    Initializes the agent and stores it in the session.
    """
    await cl.Message(content="Initializing agent...").send()
    agent_graph = create_agent_graph()
    cl.user_session.set("agent_graph", agent_graph)
    await cl.Message(content="Hello! I am your personal software architect. How can I assist you today?").send()

@cl.on_message
async def main(message: cl.Message):
    """
    Runs the agent graph and streams the response with clear steps.
    """
    agent_graph = cl.user_session.get("agent_graph")
    inputs = {"messages": [HumanMessage(content=message.content)]}

    final_answer = ""
    try:
        async with cl.Step(name="Agent Execution") as root_step:
            root_step.input = message.content
            
            async for chunk in agent_graph.astream(inputs, {"recursion_limit": 15}):
                # Agent node: contains LLM's thoughts and tool calls
                if "agent" in chunk:
                    agent_messages = chunk["agent"].get("messages", [])
                    if agent_messages:
                        last_message = agent_messages[-1]
                        # Display LLM's reasoning if it's not a final answer
                        if last_message.content and last_message.tool_calls:
                             root_step.output += f"\n\n**Thinking:**\n{last_message.content}"
                             await root_step.update()
                        # Check for final answer
                        if isinstance(last_message, AIMessage) and not last_message.tool_calls:
                            final_answer = last_message.content
                            break # Exit loop once final answer is found
    
                # Tools node: contains the output of the tools
                if "tools" in chunk:
                    tool_messages = chunk["tools"].get("messages", [])
                    if tool_messages:
                        for tool_msg in tool_messages:
                            if isinstance(tool_msg, ToolMessage):
                                tool_name = tool_msg.name
                                try:
                                    tool_args = json.loads(tool_msg.additional_kwargs.get("tool_call", "{}")).get("arguments", {})
                                except json.JSONDecodeError:
                                    tool_args = {}
                                tool_output = tool_msg.content
    
                                async with cl.Step(name=f"Tool: `{tool_name}`", parent_id=root_step.id) as tool_step:
                                    tool_step.input = json.dumps(tool_args, indent=2)
                                    tool_step.output = str(tool_output) # Ensure output is a string
                                    await tool_step.send()
    
            if not final_answer:
                 final_answer = "The agent finished without providing a final answer."
    
    except Exception as e:
        final_answer = f"An error occurred: {str(e)}"
        
    await cl.Message(content=final_answer).send()