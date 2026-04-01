"""
FinBot Agent Service — Production-grade with tenacity retries.

Production patterns:
- tenacity for retry with exponential backoff (same lib used by OpenAI SDK)
- Structured logging with context (request_id, thread_id, attempt)
- Auto-heal corrupted chat history
- Reset stale connections on SSL errors
"""

import uuid
import logging
import time
from typing import Any, Dict, List

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
    RetryError,
)

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.core.database import db
from app.services.tools.stock import get_stock_fundamentals
from app.services.tools.news import search_news, yahoo_tool, wiki_tool

logger = logging.getLogger("finbot.agent")

SYSTEM_PROMPT = """
You are FinBot, an expert equity research analyst. Your primary goal is to provide accurate, data-driven financial insights.

## Core Rules
1. **Gather Data First**: Never answer from memory. Use the provided tools (get_stock_fundamentals, search_news, etc.) to fetch real-time data before performing any analysis.
2. **Tool-Call Protocol**: When you need data, you MUST emit a tool call. Do not attempt to simulate, fabricate, or use XML tags manually. Use the standard tool-calling mechanism.
3. **Accuracy**: If a tool returns no data, state "Data not available" for that specific field and proceed with what you have. Never fabricate numbers.
4. **No Advice**: Provide signals and data, not buy/sell recommendations.

## Workflow
1. **Initialize**: Identify the ticker or company in the user's query.
2. **Research**: Call `get_stock_fundamentals` and `search_news` (or others) to get current metrics and headlines.
3. **Analyze**: Evaluate the gathered data (valuation, sentiment, risks).
4. **Format**: Once ALL data is gathered, produce the final Analyst Brief using the output format below.

## Output Format (Only for final response)
**[TICKER] — Analyst Brief**
- 📊 **Fundamentals:** price, P/E, market cap, revenue growth (formatted as a concise one-liner)
- 📈 **Valuation Signal:** [OVERVALUED / FAIRLY VALUED / UNDERVALUED] + concise reason
- 📰 **News Sentiment:** [BULLISH / NEUTRAL / BEARISH] + key headline snippet
- ⚠️ **Key Risks:** 1–2 bullet points
- 🧭 **Outlook:** 1–2 sentence professional synthesis
"""

tools = [
     get_stock_fundamentals,
     yahoo_tool,
     wiki_tool, 
     search_news
]


# ── Retry predicate ─────────────────────────────────────────────────────────
def _is_connection_error(exception: BaseException) -> bool:
    """Return True if the error is a transient connection/SSL issue worth retrying."""
    err_msg = str(exception)
    return any(pattern in err_msg for pattern in (
        "SSL connection",
        "consuming input failed",
        "connection is closed",
        "server closed the connection",
        "connection refused",
        "broken pipe",
        "ConnectionResetError",
    ))


class FinBotService:
    def __init__(self):
        # Cache agents per model_id to avoid redundant initialization
        self._agents: Dict[str, Any] = {}
        self._checkpointer = None

    async def get_checkpointer(self) -> AsyncPostgresSaver:
        """Lazily initialize the PostgreSQL checkpointer."""
        if not self._checkpointer:
            await db.open()
            self._checkpointer = AsyncPostgresSaver(db.get_pool())
            await self._checkpointer.setup()
            logger.info("Checkpointer initialized")
        return self._checkpointer

    async def get_agent(self, model_id: str = "llama-3.3-70b-versatile"):
        """Lazily initialize or retrieve the LangGraph agent for a specific model."""
        if model_id not in self._agents:
            checkpointer = await self.get_checkpointer()
            llm = get_llm(model_id)
            self._agents[model_id] = create_react_agent(
                model=llm,
                tools=tools,
                checkpointer=checkpointer,
                prompt=SYSTEM_PROMPT
            )
            logger.info(f"Agent initialized with model: {model_id}")
        return self._agents[model_id]

    async def _reset(self):
        """Reset cached agents so next call gets fresh connections."""
        logger.warning("Resetting all agents (stale connection detected)")
        self._agents = {}
        self._checkpointer = None

    async def analyze_stock(self, query: str, thread_id: str, model_id: str = "llama-3.3-70b-versatile") -> str:
        """
        Execute the agent for a given query, thread ID, and model ID.
        """
        config = {"configurable": {"thread_id": thread_id}}
        start_time = time.monotonic()

        last_exception = None
        for attempt in range(1, 4):  # 3 attempts
            try:
                agent = await self.get_agent(model_id)

                logger.info(
                    "Agent invocation starting",
                    extra={"thread_id": thread_id, "attempt": attempt, "query": query[:80]}
                )

                response = await agent.ainvoke(
                    {"messages": [HumanMessage(content=query)]},
                    config=config
                )

                latency = round((time.monotonic() - start_time) * 1000)
                logger.info(
                    "Agent invocation completed",
                    extra={"thread_id": thread_id, "latency_ms": latency, "attempt": attempt}
                )
                return response["messages"][-1].content

            except Exception as e:
                last_exception = e
                err_msg = str(e)

                # ── Corrupted chat history (non-retryable, auto-heal) ──────
                if "ToolMessage" in err_msg or "INVALID_CHAT_HISTORY" in err_msg:
                    fresh_thread_id = f"{thread_id}_rescue_{uuid.uuid4().hex[:8]}"
                    logger.warning(
                        "Corrupted thread detected, starting fresh",
                        extra={"thread_id": thread_id, "fresh_thread_id": fresh_thread_id}
                    )
                    config = {"configurable": {"thread_id": fresh_thread_id}}
                    agent = await self.get_agent(model_id)
                    response = await agent.ainvoke(
                        {"messages": [HumanMessage(content=query)]},
                        config=config
                    )
                    return response["messages"][-1].content

                # ── Connection/SSL errors (retryable) ──────────────────────
                if _is_connection_error(e) and attempt < 3:
                    wait_time = 2 ** (attempt - 1)  # 1s, 2s
                    logger.warning(
                        f"Connection error on attempt {attempt}, retrying in {wait_time}s",
                        extra={"thread_id": thread_id, "attempt": attempt, "error": err_msg[:200]}
                    )
                    await self._reset()
                    import asyncio
                    await asyncio.sleep(wait_time)
                    continue

                # ── Unrecoverable error ────────────────────────────────────
                logger.error(
                    "Agent invocation failed (non-retryable)",
                    extra={"thread_id": thread_id, "attempt": attempt, "error": err_msg[:500]},
                    exc_info=True
                )
                raise

        # All retries exhausted
        logger.error("All retry attempts exhausted", extra={"thread_id": thread_id})
        raise last_exception or RuntimeError("analyze_stock: all retry attempts exhausted")


# Singleton instance per production pattern
fin_bot_service = FinBotService()


async def analyze_stock(query: str, thread_id: str = "default-thread", model_id: str = "llama-3.3-70b-versatile") -> str:
    """Public API — backwards compatible wrapper."""
    return await fin_bot_service.analyze_stock(query, thread_id, model_id)
