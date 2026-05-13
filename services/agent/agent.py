"""
TrialMind LangGraph Agent.

A ReAct-style agent powered by Claude 3.5 Sonnet (AWS Bedrock) that uses
the TrialMind tool suite to answer clinical trial research questions.

Graph structure:
  START → agent_node → (tool_node | END)
                ↑____________↓
"""
import json
from typing import Annotated, TypedDict

from langchain_aws import ChatBedrock
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from loguru import logger

from config import settings
from tools import ALL_TOOLS

SYSTEM_PROMPT = """You are TrialMind, an expert AI research assistant specialising in \
clinical trial analysis and pharmaceutical research.

You have access to a database of hundreds of thousands of real clinical trials from \
ClinicalTrials.gov, a machine learning model that predicts trial success probability, \
and tools to generate charts and statistics.

## Your capabilities
- Search and retrieve clinical trial records
- Compute aggregate statistics (success rates by phase, sponsor type, therapeutic area, etc.)
- Compare groups of trials against each other
- Predict whether a new trial design is likely to succeed
- Generate structured chart data for visualisation
- Assess your own prediction model's accuracy against historical data

## How to respond
1. Always use your tools to retrieve real data before answering. Do not guess numbers.
2. When the user asks for a chart or graph, call `generate_chart_data` with the appropriate \
   chart_type and include the returned JSON in your response under a ```chart``` code block \
   so the frontend can render it automatically.
3. Cite NCT IDs when discussing specific trials.
4. Be concise but thorough. Structure longer answers with clear headings.
5. When asked about model accuracy, always call `get_model_accuracy` and present the results \
   with the confusion matrix and AUC-ROC.
6. If a question requires multiple tool calls, chain them together.

## Chart types available
- success_rate_by_phase
- success_rate_by_area
- enrollment_distribution
- trial_volume_over_time
- sponsor_comparison
- duration_vs_success

Always be honest about uncertainty, especially around derived labels in the dataset."""


# ─── LangGraph state ──────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ─── Build graph ─────────────────────────────────────────────────────────────

def build_agent():
    llm = ChatBedrock(
        model_id=settings.aws_bedrock_model_id,
        region_name=settings.aws_region,
        model_kwargs={"max_tokens": 4096, "temperature": 0},
    )

    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def agent_node(state: AgentState):
        messages = state["messages"]
        # Prepend system prompt if not already present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    tool_node = ToolNode(ALL_TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


# Singleton
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


async def run_agent(messages: list[dict], conversation_id: str = None) -> dict:
    """
    Run the agent with a list of messages and return the final response.
    messages: [{"role": "user"|"assistant", "content": "..."}]
    """
    agent = get_agent()

    lc_messages = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))

    state = {"messages": lc_messages}

    try:
        final_state = await agent.ainvoke(
            state,
            config={"recursion_limit": settings.max_iterations},
        )
    except Exception as e:
        logger.exception("Agent run failed")
        return {
            "role": "assistant",
            "content": f"I encountered an error while processing your request: {str(e)}",
            "charts": [],
            "tool_calls": [],
        }

    final_message = final_state["messages"][-1]
    content = final_message.content if hasattr(final_message, "content") else str(final_message)

    # Extract any chart data blocks from tool calls in the run
    charts = []
    tool_calls_log = []
    for msg in final_state["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_log.append({"tool": tc["name"], "args": tc["args"]})
        # Look for chart data in tool messages
        if hasattr(msg, "content") and isinstance(msg.content, str):
            try:
                data = json.loads(msg.content)
                if isinstance(data, dict) and data.get("chart_type"):
                    charts.append(data)
            except (json.JSONDecodeError, TypeError):
                pass

    return {
        "role": "assistant",
        "content": content,
        "charts": charts,
        "tool_calls": tool_calls_log,
    }
