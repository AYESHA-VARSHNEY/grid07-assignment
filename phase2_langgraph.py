# Phase 2: Autonomous Content Engine (LangGraph)
# A 3-node state machine: decide topic -> search -> draft post.
# Output is a strict JSON object: {bot_id, topic, post_content}.

import os
import json
from dotenv import load_dotenv
from typing import TypedDict
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

load_dotenv()

# --- LLM ---
llm = ChatGroq(
    model="llama3-8b-8192",
    api_key=os.getenv("GROQ_API_KEY"),
)

# --- Bot Personas (shared with main.py) ---
BOT_PERSONAS = {
    "bot_a": (
        "I believe AI and crypto will solve all human problems. Highly optimistic "
        "about technology, Elon Musk, and space exploration. I dismiss regulatory concerns."
    ),
    "bot_b": (
        "I believe tech monopolies are destroying society. I am highly critical of AI, "
        "social media, and billionaires. I value privacy and nature."
    ),
    "bot_c": (
        "I strictly care about markets, ROI, and making money. "
        "I speak only in finance jargon."
    ),
}


# --- Mock Search Tool ---
@tool
def mock_searxng_search(query: str) -> str:
    """
    Simulates a SearXNG web search by returning hardcoded headlines.
    In production this would call a real SearXNG or news API.
    """
    q = query.lower()
    if any(kw in q for kw in ["crypto", "bitcoin", "btc"]):
        return "Bitcoin hits new all-time high amid regulatory ETF approvals."
    if any(kw in q for kw in ["ai", "openai", "llm", "gpt"]):
        return "OpenAI releases GPT-5. AI set to automate 30% of coding jobs by 2025."
    if any(kw in q for kw in ["market", "stock", "fed", "rate", "economy"]):
        return "Fed holds rates at 5.25%. S&P 500 hits record. Tech stocks rally on AI earnings."
    if any(kw in q for kw in ["elon", "tesla", "spacex"]):
        return "SpaceX Starship completes orbital test. Tesla unveils autonomous robotaxi."
    if any(kw in q for kw in ["climate", "environment", "nature"]):
        return "UN warns of irreversible climate tipping points. Carbon emissions at record high."
    if any(kw in q for kw in ["privacy", "surveillance", "data"]):
        return "Meta fined $1.3B for GDPR violations. Governments expand digital surveillance."
    return f"No specific results for '{query}'. Global AI investment surpasses $500B."


# --- LangGraph State ---
class GraphState(TypedDict):
    bot_id: str
    persona: str
    topic: str
    search_query: str
    search_results: str
    post_content: str


# --- Node 1: Decide what to search ---
def node_decide_search(state: GraphState) -> GraphState:
    """
    The LLM reads the bot's persona and decides a topic + search query
    for today's post.
    """
    print(f"\n[Node 1] {state['bot_id']} deciding topic...")

    prompt = f"""You are a social media bot with this persona:
{state['persona']}

Decide ONE topic you want to post about today based on your personality.
Respond with ONLY valid JSON — no markdown, no explanation:
{{"topic": "short topic name", "search_query": "search string"}}"""

    response = llm.invoke(prompt)
    text = response.content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

    try:
        data = json.loads(text)
        state["topic"] = data["topic"]
        state["search_query"] = data["search_query"]
    except json.JSONDecodeError:
        # Fallback if LLM doesn't return clean JSON
        state["topic"] = "technology"
        state["search_query"] = "latest AI news"

    print(f"[Node 1] Topic: '{state['topic']}' | Query: '{state['search_query']}'")
    return state


# --- Node 2: Run the mock search ---
def node_web_search(state: GraphState) -> GraphState:
    """Calls the mock search tool and stores the results in state."""
    print(f"[Node 2] Searching: '{state['search_query']}'")
    results = mock_searxng_search.invoke({"query": state["search_query"]})
    state["search_results"] = results
    print(f"[Node 2] Results: {results}")
    return state


# --- Node 3: Draft the post ---
def node_draft_post(state: GraphState) -> GraphState:
    """
    Uses the bot's persona + search results to generate a 280-character
    opinionated post. Output is forced into strict JSON.
    """
    print(f"[Node 3] {state['bot_id']} drafting post...")

    prompt = f"""You are a social media bot. Your persona:
{state['persona']}

Topic: {state['topic']}
Recent news: {state['search_results']}

Write a bold, opinionated post (max 280 characters) that fits your persona.
Respond with ONLY valid JSON — no markdown, no explanation:
{{"bot_id": "{state['bot_id']}", "topic": "{state['topic']}", "post_content": "your post here"}}"""

    response = llm.invoke(prompt)
    text = response.content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

    try:
        data = json.loads(text)
        state["post_content"] = data.get("post_content", "")
        print(f"[Node 3] Post: {state['post_content'][:100]}...")
    except json.JSONDecodeError:
        state["post_content"] = "Error generating post content."
        print("[Node 3] JSON parse failed — fallback used.")

    return state


# --- Build the LangGraph ---
def build_content_graph():
    graph = StateGraph(GraphState)
    graph.add_node("decide_search", node_decide_search)
    graph.add_node("web_search", node_web_search)
    graph.add_node("draft_post", node_draft_post)

    graph.set_entry_point("decide_search")
    graph.add_edge("decide_search", "web_search")
    graph.add_edge("web_search", "draft_post")
    graph.add_edge("draft_post", END)

    return graph.compile()


# --- Public function used by main.py ---
def generate_bot_post(bot_id: str, persona: str) -> dict:
    """Runs the full LangGraph pipeline and returns the final JSON output."""
    app = build_content_graph()
    final_state = app.invoke(
        GraphState(
            bot_id=bot_id,
            persona=persona,
            topic="",
            search_query="",
            search_results="",
            post_content="",
        )
    )
    return {
        "bot_id": final_state["bot_id"],
        "topic": final_state["topic"],
        "post_content": final_state["post_content"],
    }


# --- Standalone test ---
if __name__ == "__main__":
    for bot_id, persona in BOT_PERSONAS.items():
        print(f"\n{'=' * 55}")
        print(f"Running {bot_id}...")
        result = generate_bot_post(bot_id, persona)
        print(f"\nFinal JSON output:")
        print(json.dumps(result, indent=2))