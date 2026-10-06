from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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


class PresignRequest(BaseModel):
    project_name: str = Field(default="Default Project", max_length=200)
    filename: str = Field(min_length=1, max_length=500)
    content_type: str | None = Field(default="application/octet-stream", max_length=200)


class PresignResponse(BaseModel):
    object_key: str
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str]
    expires_in: int


class CompleteUploadRequest(BaseModel):
    project_name: str = Field(default="Default Project", max_length=200)
    filename: str = Field(min_length=1, max_length=500)
    object_key: str = Field(min_length=1)
    content_type: str | None = Field(default="application/octet-stream", max_length=200)


class UrlImportRequest(BaseModel):
    project_name: str = Field(default="Default Project", max_length=200)
    url: HttpUrl
    filename: str | None = Field(default=None, max_length=500)
    bearer_token: str | None = Field(default=None, max_length=4096)
