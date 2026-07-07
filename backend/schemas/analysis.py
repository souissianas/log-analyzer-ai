from typing import Any

from pydantic import BaseModel, Field


class StructuredAnalysis(BaseModel):
    explanation: str = ""
    causes: list[str] = Field(default_factory=list)
    solutions: list[str] = Field(default_factory=list)


class LogEntrySchema(BaseModel):
    line_number: int
    timestamp: str
    level: str
    message: str
    category: str | None = None


class LogSummarySchema(BaseModel):
    total_critical: int
    by_level: dict[str, int]


class AnalyzedErrorItem(BaseModel):
    index: int
    line_number: int
    timestamp: str
    level: str
    message: str
    category: str | None = None
    success: bool
    analysis: StructuredAnalysis | dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    processing_time_seconds: float | None = None


class AnalysisResultResponse(BaseModel):
    filename: str
    total_errors_found: int
    total_analyzed: int
    skipped: int = 0
    analyzed: list[AnalyzedErrorItem] = Field(default_factory=list)
    log_id: int | None = None
    message: str | None = None


class AnalysisListItem(BaseModel):
    id: int
    filename: str
    created_at: str
    total_errors_found: int
    total_analyzed: int


class AnalysisListResponse(BaseModel):
    count: int
    items: list[AnalysisListItem]


class AnalysisDetailResponse(BaseModel):
    id: int
    filename: str
    created_at: str
    total_errors_found: int
    total_analyzed: int
    data: dict[str, Any] | None = None


class LegacyAnalyzeResponse(BaseModel):
    filename: str
    summary: LogSummarySchema
    ai_explanation: str
    entries: list[LogEntrySchema]
