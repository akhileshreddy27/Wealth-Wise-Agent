"""The advisor agent: a LangGraph tool-calling loop with a number-verification step.

    START -> agent --(tool calls?)--> tools -> agent ... --(final answer)--> verify --(ok)--> END
                                                                               \\--(made-up numbers, 1 retry)--> agent

The agent may only *explain*; every figure must come from a tool (see guard.py).
"""
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agents import guard

MAX_RETRIES = 1
GUARD_NAME = "number_guard"   # marks our feedback messages so their numbers don't count as "user-provided"

SYSTEM_PROMPT = """You are Wealth Wise, an educational personal-finance assistant for Indian users.

Rules:
- Every number you state (amounts, returns, rates, scores, percentages) must come from a tool result in this
  conversation. Never estimate, calculate or recall figures yourself. If no tool provides it, say so.
- For questions about the user's money, plan, spending or goals, call the relevant tool first.
- You explain the app's rule-based recommendations; you don't invent new ones or name products the tools didn't return.
- Be brief and plain-spoken (under 180 words unless asked for more). Use ₹ with Indian digit grouping (₹1,50,000).
- This is education, not SEBI-registered investment advice; say so when the user asks what exactly to buy or sell."""

FEEDBACK = ("Your answer contains figures that don't appear in any tool result: {nums}. "
            "Call a tool to get those numbers, or rewrite the answer without them. Don't apologise; just give the corrected answer.")


class AdvisorState(MessagesState):
    history_len: int        # messages that came from the chat history (before this run)
    retries: int
    unverified: list[str]


def _sources(messages: list[BaseMessage], history_len: int) -> list:
    """Text the answer's numbers may legitimately come from: tool results, the user's words, and
    assistant replies from earlier turns (already verified then). A rejected draft from *this* run never counts."""
    out = []
    for i, m in enumerate(messages):
        if isinstance(m, ToolMessage):
            out.append(m.content)
        elif isinstance(m, HumanMessage) and m.name != GUARD_NAME:
            out.append(m.content)
        elif isinstance(m, AIMessage) and i < history_len:
            out.append(m.content)
    return out


def build_advisor(llm: BaseChatModel, tools: list[BaseTool]):
    model = llm.bind_tools(tools)

    def agent(state: AdvisorState):
        return {"messages": [model.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])]}

    def verify(state: AdvisorState):
        msgs = state["messages"]
        result = guard.check(str(msgs[-1].content), *_sources(msgs, state["history_len"]))
        if result.ok:
            return {"unverified": []}
        if state.get("retries", 0) >= MAX_RETRIES:
            return {"unverified": result.unverified}
        return {"retries": state.get("retries", 0) + 1, "unverified": result.unverified,
                "messages": [HumanMessage(FEEDBACK.format(nums=", ".join(result.unverified)), name=GUARD_NAME)]}

    def after_verify(state: AdvisorState):
        last = state["messages"][-1]
        return "agent" if isinstance(last, HumanMessage) and last.name == GUARD_NAME else END

    g = StateGraph(AdvisorState)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(tools))
    g.add_node("verify", verify)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "verify"})
    g.add_edge("tools", "agent")
    g.add_conditional_edges("verify", after_verify, {"agent": "agent", END: END})
    return g.compile()


def run_advisor(llm: BaseChatModel, tools: list[BaseTool], history: list[dict]) -> dict:
    """history: [{"role": "user"|"assistant", "content": str}, ...] ending with the user's question."""
    messages = [HumanMessage(m["content"]) if m["role"] == "user" else AIMessage(m["content"]) for m in history]
    final = build_advisor(llm, tools).invoke({"messages": messages, "history_len": len(messages), "retries": 0, "unverified": []},
                                             {"recursion_limit": 20})
    new = final["messages"][len(messages):]
    tool_calls = [{"name": c["name"], "args": c["args"]} for m in new if isinstance(m, AIMessage) for c in m.tool_calls]
    return {"reply": str(new[-1].content), "tool_calls": tool_calls,
            "grounded": not final["unverified"], "unverified": final["unverified"]}
