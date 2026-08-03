"""收藏相关 Pydantic 模型"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class FavoriteWorkerResponse(BaseModel):
    worker_id: int
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    rating: Optional[float] = None
    service_count: Optional[int] = None
    is_favorite: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
