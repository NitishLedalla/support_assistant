from typing import Annotated, TypedDict, Literal
import operator
import pandas as pd
import re
import os 
from dotenv import load_dotenv

from pydantic import BaseModel


from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore

from langsmith import traceable
from langsmith import Client


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")


print(os.getenv("LANGSMITH_TRACING"))
print(os.getenv("LANGSMITH_PROJECT"))
print(bool(os.getenv("LANGSMITH_API_KEY")))
print(os.getenv(""))


# ---------- Tools ----------

@tool
def calculator(a: float, b: float, operation: str) -> float:
    """Perform a basic arithmetic calculation on two numbers.

    Use this when the user asks for a math calculation involving two numbers,
    such as multiplying seats by price, or adding/subtracting amounts.

    Args:
        a: The first number.
        b: The second number.
        operation: One of 'add', 'subtract', 'multiply', 'divide'.

    Returns:
        The numeric result of applying the operation to a and b.
    """
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        return a / b
    else:
        raise ValueError(f"Unsupported operation: {operation}")


@tool
def lookup_price(plan: str) -> str:
    """Look up pricing information for a given subscription plan.

    Use this when the user asks how much a plan costs, or asks about
    seat pricing or bulk discounts for a specific plan name.

    Args:
        plan: The plan name to look up, e.g. 'Basic', 'Pro', or 'Enterprise'.

    Returns:
        A string summarizing the plan's price per seat, minimum seats
        required for a discount, and the discount percentage.
    """
    df = pd.read_excel("/Users/nitishledalla/Desktop/projects/support_assistant/data/pricing.xlsx")
    row = df[df["plan"].str.lower() == plan.lower()]

    if row.empty:
        return f"No pricing found for plan '{plan}'."

    row = row.iloc[0]
    return (
        f"Plan: {row['plan']}, "
        f"Price per seat: ${row['price_per_seat']}, "
        f"Min seats for discount: {row['min_seats_for_discount']}, "
        f"Discount: {row['discount_pct']}%"
    )


@traceable
def _pattern_match(policy_id, content):
    pattern = rf'({re.escape(policy_id)} \| .*?)(?=\nP-\d+ \||\Z)'
    match = re.search(pattern, content, re.DOTALL)

    return match


@tool
def lookup_policy(policy_id: str) -> str:
    """Look up the full text of a company policy by its ID.

    Use this when the user asks about a specific policy, refund rules,
    cancellation terms, or anything referencing a policy ID like 'P-001'.

    Args:
        policy_id: The policy ID to look up, e.g. 'P-001', 'P-003'.

    Returns:
        The full text of the matching policy, or a message if not found.
    """
    file_path = "/Users/nitishledalla/Desktop/projects/support_assistant/data/policies.txt"
    with open(file_path, "r") as f:
        content = f.read()

    match = _pattern_match(policy_id, content)

    if match:
        return match.group(1).strip()
    else:
        return f"No policy found for ID '{policy_id}'."


def lookup_customer(customer_id: str) -> dict:
    df = pd.read_csv("/Users/nitishledalla/Desktop/projects/support_assistant/data/customers.csv")
    row = df[df["customer_id"] == customer_id]

    if row.empty:
        return {}

    row = row.iloc[0]
    return {
        "name": row["name"],
        # "preferred_tone": row["preferred_tone"],
        "current_plan": row["current_plan"],
    }


# ---------- Model ----------
llm = ChatOpenAI(model="gpt-4")
llm_with_tools = llm.bind_tools([calculator, lookup_policy, lookup_price])


# ---------- State ----------
class InputState(TypedDict):
    question: str


class OutputState(TypedDict):
    answer: str


class State(TypedDict):
    question: str
    answer: str
    messages: Annotated[list, add_messages]
    notes: Annotated[list, operator.add]
    run: int
    route: str


# ---------- Nodes ----------
def normalize(state: State):
    tmp = state['question']
    tmp = tmp.lower().strip()
    return {"messages": [HumanMessage(content=tmp)]}


def agent(state: State, config: RunnableConfig, store: BaseStore):
    customer_id = config["configurable"].get("customer_id")
    current_run = state.get('run', 0)

    if current_run >= 5:
        return {"messages": [], "run": current_run}

    stored_item = store.get(namespace=("customer", customer_id), key="preferred_tone")
    tone = stored_item.value["preferred_tone"] if stored_item else "neutral"

    formatted_messages = candidate_prompt_template.format_messages(tone=tone)
    system_msg = formatted_messages[0]

    response = llm_with_tools.invoke([system_msg] + state['messages'])

    update = {"messages": [response], "run": current_run + 1}
    if response.content:
        update["answer"] = response.content

    return update

class classification_output(BaseModel):
    route: Literal["pricing", "policy", "general"]

llm_classification_output = llm.with_structured_output(classification_output)


def classify(state: State) -> Command[Literal['normalize']]:
    result = llm_classification_output.invoke(state["question"])

    return Command(update={"route": result.route}, goto="normalize")


tools_node = ToolNode([calculator, lookup_policy, lookup_price])

# ---------- Graph ----------
builder = StateGraph(State, input_schema=InputState, output_schema=OutputState)

builder.add_node("classify", classify)
builder.add_node("normalize", normalize)
builder.add_node("agent", agent)
builder.add_node("tools", tools_node)

builder.add_edge(START, "classify")
builder.add_edge("normalize", "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

memory = InMemorySaver()
memory_store = InMemoryStore()
memory_store.put(("customer", "cust_001"), "preferred_tone", {"preferred_tone": "casual"})
graph = builder.compile(checkpointer=memory, store=memory_store)

client = Client()
candidate_prompt = client.pull_prompt("candidate_prompt", include_model=True, secrets={"OPENAI_API_KEY": OPENAI_API_KEY})
candidate_prompt_template = candidate_prompt.steps[0]  # ChatPromptTemplate only — has .format_messages/.metadata


result = graph.invoke(
    {"question": "What does policy P-001 say about refunds?"}, 
    config={
        "configurable": {"customer_id": "cust_001", "thread_id": "thread_cust_001"},
        "tags": ["day4", "prompt-version-test"],
        "metadata": {
            "prompt_name": "candidate_prompt",
            "prompt_commit": candidate_prompt_template.metadata.get("lc_hub_commit_hash"),},
            
    },
)
result2 = graph.invoke(
    {"question": "What did I just ask you?"},
    config={
        "configurable": {"customer_id": "cust_001", "thread_id": "thread_cust_002"},
        "tags": ["day5", "memory-test"],
    },
)

print(result)
print(result2)
