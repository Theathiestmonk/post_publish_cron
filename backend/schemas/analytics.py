from typing import List, Literal, Optional, Dict
from pydantic import BaseModel

class AnalyticsState(BaseModel):
    """
    Canonical State for Analytics & Insights.
    Shared contract between Emily (Orchestrator) and Orion (Engine).
    """
    intent: Literal["analytics", "insight"]
    source: Literal["social_media", "blog"]
    platforms: List[str]
    metrics: List[str]
    analytics_level: Literal["account", "post"]
    
    # Context
    user_id: str
    
    # Optional fields (all logic to handle them is in Orion)
    date_range: Optional[str] = None
    
    # Post-level specific
    top_n: Optional[int] = None
    sort_order: Optional[Literal["asc", "desc"]] = None
    
    # Post selector (NEW: Deterministic post selection)
    post_selector: Optional[Literal["latest", "top", "recent_n", "specific_id"]] = None
    post_id: Optional[str] = None
    recent_n: Optional[int] = None
    
    # Blog insight specific
    url: Optional[str] = None
    
    class Config:
        extra = "ignore"
