from typing import Optional
from datetime import datetime, timezone
from beanie import Document
from pydantic import Field

class UserModel(Document):
    mobileNo: str = Field(min_length=9, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
