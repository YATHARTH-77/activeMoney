from typing import List, Optional

from pydantic import BaseModel, Field


class ContextRule(BaseModel):
    name: str
    label: str

class SummaryRule(BaseModel):
    name: str
    label: str
    direction: str = "right"
    offset_words: int = 1

class ColumnRule(BaseModel):
    name: str
    x_start: float
    x_end: float

class TableRule(BaseModel):
    start_anchor: str
    columns: List[ColumnRule]

class LayoutArtifact(BaseModel):
    artifact_version: str
    layout_fingerprint: str
    provider_name: str
    context_rules: List[ContextRule] = Field(default_factory=list)
    summary_rules: List[SummaryRule] = Field(default_factory=list)
    holdings_table: Optional[TableRule] = None