from typing import List, Optional

from pydantic import BaseModel, Field


class ColumnDefinition(BaseModel):
    name: str
    x_start: float
    x_end: float

class TableDefinition(BaseModel):
    start_anchor: str  
    columns: List[ColumnDefinition]
    stop_anchor: Optional[str] = None

class ExtractionRule(BaseModel):
    name: str          # Added the missing 'name' field here
    label: str         
    direction: str     
    offset_words: int = 1 

class LayoutArtifact(BaseModel):
    artifact_version: str
    layout_fingerprint: str
    provider_name: str
    context_rules: List[ExtractionRule] = Field(default_factory=list)
    summary_rules: List[ExtractionRule] = Field(default_factory=list)
    holdings_table: Optional[TableDefinition] = None
    transactions_table: Optional[TableDefinition] = None