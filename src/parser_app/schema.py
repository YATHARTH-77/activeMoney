from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    FEE = "fee"
    INFLOW = "inflow"
    OUTFLOW = "outflow"
    OTHER = "other"

class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"

class StatementContext(BaseModel):
    provider_name: str
    strategy_name: str
    client_identifier: str
    statement_period: str
    currency: str = "INR"

class Holding(BaseModel):
    security_name: str
    isin: Optional[str] = None
    quantity: Decimal
    cost: Optional[Decimal] = None
    market_value: Decimal
    weight: Optional[Decimal] = None

class Transaction(BaseModel):
    date: date
    transaction_type: TransactionType
    security: Optional[str] = None
    quantity: Optional[Decimal] = None
    amount: Decimal

class Summary(BaseModel):
    opening_value: Decimal
    closing_value: Decimal
    cash_balance: Decimal
    fees_charged: Optional[Decimal] = None
    nav_per_unit: Optional[Decimal] = None

class ValidationResult(BaseModel):
    status: ValidationStatus
    details: str

class Provenance(BaseModel):
    source_hash: str
    layout_fingerprint: str
    artifact_version: str

class ParsedStatement(BaseModel):
    statement_id: str
    context: StatementContext
    summary: Summary
    holdings: List[Holding] = Field(default_factory=list)
    transactions: List[Transaction] = Field(default_factory=list)
    provenance: Provenance
    validation: ValidationResult