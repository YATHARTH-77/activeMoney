import re
from decimal import Decimal
from typing import Any, Dict, List

from parser_app.artifact_schema import (
    ColumnDefinition,
    ExtractionRule,
    LayoutArtifact,
    TableDefinition,
)
from parser_app.schema import (
    Holding,
    ParsedStatement,
    Provenance,
    StatementContext,
    Summary,
    Transaction,
    ValidationResult,
    ValidationStatus,
)


class DeterministicParser:
    def __init__(self, artifact: LayoutArtifact):
        self.artifact = artifact

    def parse(self, pdf_pages: List[Dict[str, Any]], source_hash: str) -> ParsedStatement:
        all_words = []
        for page in pdf_pages:
            all_words.extend(page["words"])

        context_data = self._extract_key_values(all_words, self.artifact.context_rules)
        summary_data = self._extract_key_values(all_words, self.artifact.summary_rules)
        
        holdings = []
        if self.artifact.holdings_table:
            raw_holdings = self._extract_table(all_words, self.artifact.holdings_table)
            for row in raw_holdings:
                holding_obj = self._map_holding(row)
                if holding_obj is not None:
                    holdings.append(holding_obj)

        transactions = []
        if self.artifact.transactions_table:
            raw_txns = self._extract_table(all_words, self.artifact.transactions_table)
            for row in raw_txns:
                txn_obj = self._map_transaction(row)
                if txn_obj is not None:
                    transactions.append(txn_obj)

        return ParsedStatement(
            statement_id=f"STMT-{source_hash[:8]}",
            context=StatementContext(
                provider_name=self.artifact.provider_name,
                strategy_name=context_data.get("strategy_name", "Unknown"),
                client_identifier=context_data.get("client_identifier", "Unknown"),
                statement_period=context_data.get("statement_period", "Unknown"),
            ),
            summary=Summary(
                opening_value=self._clean_decimal(summary_data.get("opening_value", "0")),
                closing_value=self._clean_decimal(summary_data.get("closing_value", "0")),
                cash_balance=self._clean_decimal(summary_data.get("cash_balance", "0")),
                nav_per_unit=(
                    self._clean_decimal(summary_data["nav_per_unit"]) 
                    if summary_data.get("nav_per_unit") else None
                )
            ),
            holdings=holdings,
            transactions=transactions,
            provenance=Provenance(
                source_hash=source_hash,
                layout_fingerprint=self.artifact.layout_fingerprint,
                artifact_version=self.artifact.artifact_version
            ),
            validation=ValidationResult(
                status=ValidationStatus.NOT_VERIFIABLE,
                details="Pending Phase 7 Financial Engine"
            )
        )

    def _extract_key_values(
        self, words: List[Dict[str, Any]], rules: List[ExtractionRule]
    ) -> Dict[str, str]:
        results = {}
        for rule in rules:
            for i, word in enumerate(words):
                if rule.label.lower() in word['text'].lower():
                    if rule.direction == "right" and i + rule.offset_words < len(words):
                        val = words[i + rule.offset_words]['text']
                        results[rule.name] = val.rstrip("|:,") 
                    break
        return results

    def _extract_table(
        self, words: List[Dict[str, Any]], table_def: TableDefinition
    ) -> List[Dict[str, str]]:
        anchor_parts = table_def.start_anchor.lower().split()
        start_idx = -1
        
        for i, word in enumerate(words):
            if anchor_parts[0] in word['text'].lower():
                match = True
                for j, part in enumerate(anchor_parts):
                    if i + j >= len(words) or part not in words[i+j]['text'].lower():
                        match = False
                        break
                if match:
                    start_idx = i
                    break
        
        if start_idx == -1:
            return []

        table_words = []
        header_y = words[start_idx]['top']
        for word in words[start_idx+1:]:
            if word['top'] > header_y + 5: 
                table_words.append(word)

        rows = []
        current_row_words = []
        current_y = -1

        for w in table_words:
            if current_y == -1 or abs(w['top'] - current_y) < 5:
                current_row_words.append(w)
                current_y = w['top']
            else:
                if current_row_words:
                    mapped_row = self._map_row_to_columns(current_row_words, table_def.columns)
                    if any(mapped_row.values()):
                        rows.append(mapped_row)
                current_row_words = [w]
                current_y = w['top']

        if current_row_words:
            mapped_row = self._map_row_to_columns(current_row_words, table_def.columns)
            if any(mapped_row.values()):
                rows.append(mapped_row)

        return rows

    def _map_row_to_columns(
        self, row_words: List[Dict], columns: List[ColumnDefinition]
    ) -> Dict[str, str]:
        row_data = {col.name: [] for col in columns}
        for w in row_words:
            center_x = (w['x0'] + w['x1']) / 2
            for col in columns:
                if col.x_start <= center_x <= col.x_end:
                    row_data[col.name].append(w['text'])
                    break
        
        return {k: " ".join(v) for k, v in row_data.items()}

    def _map_holding(self, row: Dict[str, str]) -> Holding | None:
        sec_name = row.get("security_name", "").strip()
        
        if not sec_name or "Security" in sec_name: 
            return None 

        try:
            return Holding(
                security_name=sec_name,
                isin=row.get("isin") if row.get("isin") else None,
                quantity=self._clean_decimal(row.get("quantity", "0")),
                cost=self._clean_decimal(row.get("cost")) if row.get("cost") else None,
                market_value=self._clean_decimal(row.get("market_value", "0")),
                weight=self._clean_decimal(row.get("weight")) if row.get("weight") else None
            )
        except Exception:
            return None 

    def _map_transaction(self, row: Dict[str, str]) -> Transaction | None:
        return None 

    @staticmethod
    def _clean_decimal(val: str) -> Decimal:
        if not val or val.strip() == "-":
            return Decimal("0")
        cleaned = re.sub(r'[^\d.\-]', '', val)
        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0")