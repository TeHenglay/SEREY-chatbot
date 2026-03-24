# Pydantic v2 request schemas for the builder API.

from pydantic import BaseModel, Field


class BuilderRequest(BaseModel):
    prompt: str = Field(
        ...,
        description="The user's natural language request",
        min_length=3,
        max_length=2000,
        examples=["Build a SaaS landing page with a dark hero section"],
    )
    user_id: str = Field(
        ...,
        description="Unique identifier for the user (for long-term memory)",
        min_length=1,
        max_length=128,
        examples=["user_123"],
    )
    session_id: str = Field(
        ...,
        description="Unique identifier for the current chat session",
        min_length=1,
        max_length=128,
        examples=["session_abc"],
    )
    n_components: int = Field(
        default=4,
        ge=1,
        le=8,
        description="How many ChromaDB component results to fetch",
    )
