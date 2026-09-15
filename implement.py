from dotenv import load_dotenv
import os
from typing import TypedDict, Annotated
import operator


from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage


load_dotenv()

OPEN_AI_API = os.getenv("OPENAI_API_KEY")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")

print(os.getenv("LANGSMITH_TRACING"))
print(os.getenv("LANGSMITH_PROJECT"))
print(bool(os.getenv("LANGSMITH_API_KEY")))


class State(TypedDict):
    messages: Annotated[list, add_messages]
    notes: Annotated[list, operator.add]

def normalize(state: State):
    tmp = state['messages'][-1].content
    tmp = tmp.lower().strip()
    
    return {"messages": [HumanMessage(content=tmp)]}

def respond(state: State):
    return {"messages": [AIMessage(content="<placeholder>")]}


builder = StateGraph(State)

builder.add_node("normalize", normalize)
builder.add_node("respond", respond)

builder.add_edge(START, "normalize")
builder.add_edge("normalize", "respond")
builder.add_edge("respond", END)


graph = builder.compile()

result = graph.invoke(input={"messages": ["Explain how LLM works?"]})
print(result)

print(graph.get_graph().draw_mermaid())