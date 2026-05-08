"""Pydantic schemas package.

Split from a single ``schemas.py`` module in Phase 1.B (see
``Plan/2026-05-06-backend-phase-0-1-routers-services-split.md`` §8.1).

The package re-exports every public symbol that the old single-file module
exposed, so existing ``from schemas import X`` imports keep working without
any change in callers (routers, services, scripts, tests).
"""
from __future__ import annotations

from ._common import (
    CustomerMaterialStatusValue,
    CustomerStatusValue,
    FactSourceTypeValue,
    FactStatusValue,
    MaterialTypeValue,
    ProjectStatusValue,
    ProjectTypeValue,
    ReviewBatchStatusValue,
    ReviewBatchTypeValue,
    normalize_datetime_input,
    normalize_project_name,
    normalize_required_text,
    normalize_string_list,
)
from .customer_materials import (
    CustomerMaterialBase,
    CustomerMaterialCreate,
    CustomerMaterialRead,
    CustomerMaterialUpdate,
)
from .customers import CustomerCreate, CustomerRead, CustomerUpdate
from .dashboard import (
    BoardPreferenceRead,
    BoardPreferenceUpdate,
    BoardSummary,
    DashboardPayload,
    HealthResponse,
    HistorySummary,
    NightlyReviewPlaceholder,
    PlanGroup,
    PlanSummary,
    ProjectRenameRequest,
    ProjectRenameResponse,
    ProjectSummary,
    TodaySummary,
)
from .facts import (
    CustomerMaterialFactCreate,
    CustomerMaterialFactRead,
    FactCreate,
    FactRead,
    FactUpdate,
)
from .knowledge import (
    KnowledgeFactCustomerOverview,
    KnowledgeFactProjectOverview,
    KnowledgeFactsOverview,
    KnowledgePreferenceRead,
    KnowledgePreferenceUpdate,
)
from .projects_v2 import ProjectV2Create, ProjectV2Read, ProjectV2Update
from .review_batches import ReviewBatchCreate, ReviewBatchRead, ReviewBatchUpdate
from .tasks import (
    ReminderCreate,
    ReminderRead,
    TaskActionCancel,
    TaskActionComplete,
    TaskActionDefer,
    TaskBase,
    TaskBoardGroup,
    TaskCreate,
    TaskDetail,
    TaskEventRead,
    TaskRead,
    TaskRecurrenceBase,
    TaskRecurrenceRead,
    TaskRecurrenceWrite,
    TaskUpdate,
    TaskUpdateCompat,
)

__all__ = [
    # _common helpers
    "normalize_datetime_input",
    "normalize_project_name",
    "normalize_required_text",
    "normalize_string_list",
    # Literal aliases
    "CustomerMaterialStatusValue",
    "CustomerStatusValue",
    "FactSourceTypeValue",
    "FactStatusValue",
    "MaterialTypeValue",
    "ProjectStatusValue",
    "ProjectTypeValue",
    "ReviewBatchStatusValue",
    "ReviewBatchTypeValue",
    # tasks
    "ReminderCreate",
    "ReminderRead",
    "TaskActionCancel",
    "TaskActionComplete",
    "TaskActionDefer",
    "TaskBase",
    "TaskBoardGroup",
    "TaskCreate",
    "TaskDetail",
    "TaskEventRead",
    "TaskRead",
    "TaskRecurrenceBase",
    "TaskRecurrenceRead",
    "TaskRecurrenceWrite",
    "TaskUpdate",
    "TaskUpdateCompat",
    # dashboard
    "BoardPreferenceRead",
    "BoardPreferenceUpdate",
    "BoardSummary",
    "DashboardPayload",
    "HealthResponse",
    "HistorySummary",
    "NightlyReviewPlaceholder",
    "PlanGroup",
    "PlanSummary",
    "ProjectRenameRequest",
    "ProjectRenameResponse",
    "ProjectSummary",
    "TodaySummary",
    # customer materials
    "CustomerMaterialBase",
    "CustomerMaterialCreate",
    "CustomerMaterialRead",
    "CustomerMaterialUpdate",
    # customers
    "CustomerCreate",
    "CustomerRead",
    "CustomerUpdate",
    # projects v2
    "ProjectV2Create",
    "ProjectV2Read",
    "ProjectV2Update",
    # facts
    "CustomerMaterialFactCreate",
    "CustomerMaterialFactRead",
    "FactCreate",
    "FactRead",
    "FactUpdate",
    # review batches
    "ReviewBatchCreate",
    "ReviewBatchRead",
    "ReviewBatchUpdate",
    # knowledge
    "KnowledgeFactCustomerOverview",
    "KnowledgeFactProjectOverview",
    "KnowledgeFactsOverview",
    "KnowledgePreferenceRead",
    "KnowledgePreferenceUpdate",
]
