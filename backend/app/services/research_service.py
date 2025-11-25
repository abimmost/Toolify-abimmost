from app.model.schemas import ToolResearchResponse, ResearchResult, YouTubeLink
from app.services.tavily_service import tavily_service
from datetime import datetime
from typing import List, Optional

def perform_tool_research(
    tool_name: str,
    tool_description: Optional[str] = None,
    language: str = "en",
    max_results: int = 5
) -> ToolResearchResponse:
    """
    Performs tool research using Tavily service.
    """
    general_query = f"{tool_name} tool usage guide tutorial"
    raw_results = tavily_service.search_tool_info(
        query=general_query,
        max_results=max_results
    )
    
    youtube_query = f"{tool_name} how to use tutorial"
    youtube_results = tavily_service.search_youtube_tutorials(
        query=youtube_query,
        max_results=max_results
    )
    
    formatted_general = tavily_service.format_results(raw_results)
    formatted_youtube = tavily_service.format_results(raw_results=youtube_results, tool_name=tool_name, youtube_only=True)
    
    youtube_links = [
        YouTubeLink(title=r["title"], url=r["url"], content=r['content'], score=r.get("score", 0.0))
        for r in formatted_youtube
        if "youtube.com" in r["url"] or "youtu.be" in r["url"]
    ]
    
    research_results = [
        ResearchResult(
            title=r["title"],
            url=r["url"],
            content=r["content"],
            score=r["score"]
        )
        for r in formatted_general
    ]
    
    return ToolResearchResponse(
        tool_name=tool_name,
        query=general_query,
        research_results=research_results,
        youtube_info=youtube_links,
        timestamp=datetime.now()
    )