from datetime import datetime
from typing import Any

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


class DatasetProfileOut(BaseModel):
    dataset_id: int
    format_name: str
    table_count: int
    profile: dict[str, Any]


class CohortSummary(BaseModel):
    name: str
    kind: str
    file_count: int
    size_bytes: int
    formats: list[str]
    source_cohorts: list[str] = []


class CohortMergeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_cohorts: list[str] = Field(min_length=2)
    notes: str | None = Field(default=None, max_length=2000)


class CohortMergeOut(BaseModel):
    id: int
    name: str
    source_cohorts: list[str]
    notes: str | None
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


class WorkspaceRecordRequest(BaseModel):
    record_type: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=250)
    payload: dict[str, Any] = {}


class WorkspaceRecordOut(BaseModel):
    id: int
    project_name: str
    record_type: str
    name: str
    payload: dict[str, Any]
    created_at: datetime


class CohortExportOut(BaseModel):
    cohort: str
    generated_at: datetime
    files: list[DatasetOut]
    workspace_records: list[WorkspaceRecordOut]

class MappingValidationItem(BaseModel):
    source: str = Field(min_length=1, max_length=250)
    canonical: str = Field(default="", max_length=250)
    confidence: int = Field(default=0, ge=0, le=100)
    status: str = Field(default="review", pattern="^(accept|review|reject)$")


class HarmonizationValidationRequest(BaseModel):
    dataset_id: int
    table_name: str | None = Field(default=None, max_length=250)
    mappings: list[MappingValidationItem]


class ValidationIssue(BaseModel):
    level: str
    code: str
    field: str | None = None
    message: str


class HarmonizationValidationOut(BaseModel):
    valid: bool
    dataset_id: int
    dataset_name: str
    table_name: str | None
    score: int
    accepted_count: int
    review_count: int
    rejected_count: int
    issues: list[ValidationIssue]


class IntegrationValidationRequest(BaseModel):
    left_dataset_id: int
    left_key: str = Field(min_length=1, max_length=250)
    right_dataset_id: int
    right_key: str = Field(min_length=1, max_length=250)
    relationship: str = Field(default="1:1", pattern="^(1:1|1:many|many:1|many:many)$")


class IntegrationValidationOut(BaseModel):
    valid: bool
    left_dataset_name: str
    right_dataset_name: str
    issues: list[ValidationIssue]
