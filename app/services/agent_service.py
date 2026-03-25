from typing import Any, Dict, List
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.llm import llm
from app.core.database import db
from app.services.tools.stock import get_stock_fundamentals
from app.services.tools.news import search_news, yahoo_tool, wiki_tool

SYSTEM_PROMPT = """
You are FinBot, an expert equity research analyst with deep knowledge of financial markets,
valuation methodologies, and macroeconomic trends.

## Task
Given a stock ticker or company name, produce a concise, structured analyst brief that helps users evaluate the investment. Do not give buy/sell advice. Present data-driven signals only.

## Rules
1. Gather data before analysis. Never rely on memory for numbers.
2. If a tool fails or returns empty data, state it and proceed.
3. Never fabricate prices, ratios, or news.
4. Always follow the output format.
5. Flag notable risks or red flags.

## Output Format

**[TICKER] — Analyst Brief**
- 📊 **Fundamentals:** price, P/E, market cap, revenue growth (one line)
- 📈 **Valuation Signal:** OVERVALUED / FAIRLY VALUED / UNDERVALUED + reason
- 📰 **News Sentiment:** bullish / neutral / bearish + key headline
- ⚠️ **Key Risks:** 1–2 bullets
- 🧭 **Outlook:** 1–2 sentence synthesis, no advice
"""

tools = [
     get_stock_fundamentals,
     yahoo_tool,
     wiki_tool, 
     search_news
]

class FinBotService:
    def __init__(self):
        self._agent = None
        self._checkpointer = None

    async def get_checkpointer(self) -> AsyncPostgresSaver:
        """Lazily initialize the PostgreSQL checkpointer."""
        if not self._checkpointer:
            # We connect to the DB pool managed in app/core/database.py
            await db.open()
            self._checkpointer = AsyncPostgresSaver(db.get_pool())
            # Ensure tables are setup. 
            # Note: In production, migrations are better, but for LangGraph this auto-setup is helpful.
            await self._checkpointer.setup()
        return self._checkpointer

    async def get_agent(self):
        """Lazily initialize the LangGraph agent with checkpointing."""
        if not self._agent:
            checkpointer = await self.get_checkpointer()
            self._agent = create_react_agent(
                model=llm,
                tools=tools,
                checkpointer=checkpointer,
                prompt=SYSTEM_PROMPT
            )
        return self._agent

    async def analyze_stock(self, query: str, thread_id: str) -> str:
        """Execute the agent for a given query and thread ID."""
        agent = await self.get_agent()
        
        # Configuration for checkpointing (persistence)
        config = {"configurable": {"thread_id": thread_id}}
        
        # Invoke agent asynchronously
        response = await agent.ainvoke(
             {"messages": [HumanMessage(content=query)]},
             config=config
        )
        
        # The last AI message contains the analysis result.
        return response["messages"][-1].content

# Singleton instance per production pattern
fin_bot_service = FinBotService()

# For backwards compatibility with original API calls, if any.
# However, for production it's better to use the instance directly.
async def analyze_stock(query: str, thread_id: str = "default-thread") -> str:
    return await fin_bot_service.analyze_stock(query, thread_id)
