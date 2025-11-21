from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ToolResearchRequest(BaseModel):
    """Request model for tool research"""
    tool_name: str = Field(..., description="Name of the tool identified by Google Vision")
    tool_description: Optional[str] = Field(None, description="Additional description from image recognition")
    language: str = Field(default="en", description="Language for the response")
    max_results: int = Field(default=10, description="Maximum number of research results")


class YouTubeLink(BaseModel):
    """YouTube tutorial link"""
    title: str
    url: str


class ResearchResult(BaseModel):
    """Individual research result"""
    title: str
    url: str
    content: str
    score: float


class ToolResearchResponse(BaseModel):
    """Response model for tool research"""
    tool_name: str
    query: str
    results: List[ResearchResult]
    youtube_links: List[YouTubeLink]
    research_context: str 
    timestamp: datetime


class ResearchRequest(BaseModel):
    """Original research request model"""
    query: str
    language: str = "en"
    max_results: int = 10


class ResearchResponse(BaseModel):
    """Original research response model"""
    query: str
    results: List[ResearchResult]
    summary: str
    timestamp: datetime