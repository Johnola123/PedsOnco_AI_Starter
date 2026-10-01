from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_name: str
    original_name: str
    content_type: str | None
    size_bytes: int
    sha256: str
    object_key: str
    status: str
    created_at: datetime
