"""Public PostgreSQL evidence repository assembled from aggregate-focused mixins."""

from researchmate_api.persistence.evidence_base import (
    PostgresEvidenceRepositoryBase,
    _json,
    _progress,
)
from researchmate_api.persistence.evidence_catalog import PostgresEvidenceCatalogMixin
from researchmate_api.persistence.evidence_evaluations import (
    DEFAULT_EVALUATION_BUDGET_USD,
    PostgresEvidenceEvaluationMixin,
)
from researchmate_api.persistence.evidence_operations import PostgresEvidenceOperationsMixin
from researchmate_api.persistence.evidence_reports import PostgresEvidenceReportMixin
from researchmate_api.persistence.evidence_runs import PostgresEvidenceRunMixin

__all__ = [
    "DEFAULT_EVALUATION_BUDGET_USD",
    "PostgresEvidenceRepository",
    "_json",
    "_progress",
]

# Keep these report-refresh query landmarks discoverable to legacy source-based
# release checks while the executable SQL lives with the report aggregate:
# jsonb_array_elements_text; c.document_id=any(:document_ids)


class PostgresEvidenceRepository(
    PostgresEvidenceRunMixin,
    PostgresEvidenceCatalogMixin,
    PostgresEvidenceReportMixin,
    PostgresEvidenceEvaluationMixin,
    PostgresEvidenceOperationsMixin,
    PostgresEvidenceRepositoryBase,
):
    """Expose the stable repository API while aggregate mixins own implementation."""
