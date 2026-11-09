import json
import os
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Dataset, DatasetSource, DatasetProfile, CohortWorkspaceRecord, CohortMerge
from app.main import dataset_delete_preview, delete_dataset


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        one = Dataset(project_name="Neuro", original_name="clinical.csv", size_bytes=123,
                      sha256="a" * 64, object_key="raw/clinical.csv")
        one.source = DatasetSource(source_type="browser")
        one.profile = DatasetProfile(format_name="csv", table_count=1, profile_json='{}')
        two = Dataset(project_name="Neuro", original_name="expression.tsv", size_bytes=321,
                      sha256="b" * 64, object_key="raw/expression.tsv")
        session.add_all([one, two])
        session.flush()
        session.add_all([
            CohortWorkspaceRecord(project_name="Neuro", record_type="harmonization", name="Map clinical", payload_json=json.dumps({"dataset_id": one.id})),
            CohortWorkspaceRecord(project_name="Neuro", record_type="integration", name="clinical plus expression", payload_json=json.dumps({"left_dataset_id": one.id, "right_dataset_id": two.id})),
            CohortWorkspaceRecord(project_name="Neuro", record_type="edit", name="Expression-only edit", payload_json=json.dumps({"dataset_id": two.id})),
            CohortMerge(name="Combined", source_cohorts_json='["Neuro", "Sarcoma"]'),
        ])
        session.commit()
        yield session
    engine.dispose()


def test_preview_lists_exact_dependencies_without_mutation(db):
    preview = dataset_delete_preview(1, db)
    assert preview["filename"] == "clinical.csv"
    assert preview["has_profile"] and preview["has_source_metadata"]
    assert {r["name"] for r in preview["dependent_records"]} == {"Map clinical", "clinical plus expression"}
    assert preview["other_files_preserved"] == 1
    assert preview["merged_views_affected"] == ["Combined"]
    assert db.get(Dataset, 1) is not None


def test_requires_fresh_confirmation_token(db):
    with pytest.raises(HTTPException) as error:
        delete_dataset(1, "incorrect", db)
    assert error.value.status_code == 409
    assert db.get(Dataset, 1) is not None


def test_deletes_only_source_and_linked_records(db):
    preview = dataset_delete_preview(1, db)
    with patch("app.main.delete_object") as remove_object:
        result = delete_dataset(1, preview["token"], db)
    remove_object.assert_called_once_with("raw/clinical.csv")
    assert result["status"] == "deleted"
    assert result["removed_workspace_records"] == 2
    assert db.get(Dataset, 1) is None
    assert db.get(Dataset, 2) is not None
    assert db.get(CohortMerge, 1) is not None
    remaining = db.query(CohortWorkspaceRecord).all()
    assert len(remaining) == 1 and remaining[0].name == "Expression-only edit"
    assert db.query(DatasetProfile).count() == 0
    assert db.query(DatasetSource).count() == 0


def test_impact_change_blocks_stale_approval(db):
    token = dataset_delete_preview(1, db)["token"]
    db.add(CohortWorkspaceRecord(project_name="Neuro", record_type="edit", name="New mapping", payload_json='{"dataset_id": 1}'))
    db.commit()
    with pytest.raises(HTTPException) as error:
        delete_dataset(1, token, db)
    assert error.value.status_code == 409
    assert db.get(Dataset, 1) is not None
