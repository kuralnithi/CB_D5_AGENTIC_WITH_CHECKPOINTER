import os
from langchain.tools import tool
from langchain_community.utilities import SerpAPIWrapper
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_community.tools.yahoo_finance_news import YahooFinanceNewsTool
from app.core.config import settings

if settings.SERPAPI_API_KEY:
    os.environ["SERPAPI_API_KEY"] = settings.SERPAPI_API_KEY

serp = SerpAPIWrapper(
    params={
        "tbm": "nws",     # Search in Google News
        "tbs": "qdr:d",   # Past day (24 hours)
    },
)

@tool
def search_news(query: str) -> str:
    """
    Search last-24h Google News via SerpAPI.
    Returns news results with URLs.
    """
    return serp.run(query)

yahoo_tool = YahooFinanceNewsTool()
wiki_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
