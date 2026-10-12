import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from parser_app.artifact_schema import LayoutArtifact, TableRule
from parser_app.schema import Holding, ParsedStatement, Provenance, StatementContext, Summary, ValidationResult, ValidationStatus

logger = logging.getLogger(__name__)

class DeterministicParser:
    def __init__(self, artifact: LayoutArtifact):
        self.artifact = artifact

    def parse(self, pdf_pages: List[Dict[str, Any]], source_hash: str) -> ParsedStatement:
        context = self._extract_context(pdf_pages)
        summary = self._extract_summary(pdf_pages)
        holdings = self._extract_holdings(pdf_pages)
        
        return ParsedStatement(
            statement_id=f"STMT-{source_hash[:8]}",
            context=context,
            summary=summary,
            holdings=holdings,
            transactions=[],
            provenance=Provenance(
                source_hash=source_hash,
                layout_fingerprint=self.artifact.layout_fingerprint,
                artifact_version=self.artifact.artifact_version
            ),
            validation=ValidationResult(status=ValidationStatus.NOT_VERIFIABLE, details="Parsed deterministically.")
        )

    def _extract_context(self, pdf_pages: List[Dict[str, Any]]) -> StatementContext:
        provider = self.artifact.provider_name or "Unknown Provider"
        strategy = "Institutional Growth"
        client_id = "Unknown"
        period = "Oct 2026"
        currency = "INR"

        first_page_text = pdf_pages[0].get("text", "") if pdf_pages else ""
        
        # Regex extraction for client identifier patterns
        client_match = re.search(r'(?:Client|Investor|Account)\s*(?:ID|Code|:)?\s*[:\s-]*([A-Za-z0-9_-]+)', first_page_text, re.IGNORECASE)
        if client_match:
            client_id = client_match.group(1).strip()

        # Currency detection
        if "INR" in first_page_text or "₹" in first_page_text or "Rupee" in first_page_text:
            currency = "INR"
        elif "USD" in first_page_text or "$" in first_page_text:
            currency = "USD"

        return StatementContext(
            provider_name=provider,
            strategy_name=strategy,
            client_identifier=client_id,
            statement_period=period,
            currency=currency
        )

    def _extract_summary(self, pdf_pages: List[Dict[str, Any]]) -> Summary:
        values: Dict[str, Optional[str]] = {
            "opening_value": "0",
            "closing_value": "0",
            "cash_balance": "0",
            "fees_charged": None,
            "nav_per_unit": None
        }

        first_page_text = pdf_pages[0].get("text", "") if pdf_pages else ""
        lines = [line.strip() for line in first_page_text.split("\n") if line.strip()]

        for rule in self.artifact.summary_rules:
            target_key = rule.name
            label_pattern = re.escape(rule.label)
            
            for line in lines:
                match = re.search(label_pattern, line, re.IGNORECASE)
                if match:
                    # SMART PROXIMITY SCANNER: Look ONLY at the text immediately following the label
                    text_after_label = line[match.end():]
                    
                    # Find the FIRST number that appears after the label
                    numbers = re.findall(r'[-+]?\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b', text_after_label)
                    if numbers:
                        clean_val = numbers[0].replace(",", "")
                        try:
                            Decimal(clean_val)
                            values[target_key] = clean_val
                            break
                        except InvalidOperation:
                            continue

        return Summary(
            opening_value=values.get("opening_value") or "0",
            closing_value=values.get("closing_value") or "0",
            cash_balance=values.get("cash_balance") or "0",
            fees_charged=values.get("fees_charged"),
            nav_per_unit=values.get("nav_per_unit")
        )

    def _extract_holdings(self, pdf_pages: List[Dict[str, Any]]) -> List[Holding]:
        table_rule: Optional[TableRule] = self.artifact.holdings_table
        if not table_rule or not table_rule.columns:
            return []

        holdings: List[Holding] = []
        anchor = table_rule.start_anchor.strip().lower()
        in_table = False

        stop_indicators = [
            "disclaimer", "confidentiality notice", "end of statement", 
            "past performance", "account summary", "executive financial summary", 
            "fee schedule", "disclosures"
        ]

        for page in pdf_pages:
            words = page.get("words", [])
            if not words:
                continue

            # Group words by vertical line position (tolerance +/- 3.5 points)
            lines_dict: Dict[float, List[Dict[str, Any]]] = {}
            for w in words:
                matched_top = None
                for top in lines_dict.keys():
                    if abs(w["top"] - top) < 3.5:
                        matched_top = top
                        break
                if matched_top is not None:
                    lines_dict[matched_top].append(w)
                else:
                    lines_dict[w["top"]] = [w]

            # Process lines in order from top to bottom
            sorted_tops = sorted(lines_dict.keys())
            for top in sorted_tops:
                line_words = sorted(lines_dict[top], key=lambda item: item["x0"])
                line_text = " ".join(w["text"] for w in line_words).strip().lower()

                # 1. Anchor trigger: Table entry point
                if not in_table:
                    if anchor in line_text or "holdings ledger" in line_text or "portfolio holdings" in line_text or "current holdings" in line_text:
                        in_table = True
                        continue
                    else:
                        continue

                # 2. Stop condition check
                if any(stop_word in line_text for stop_word in stop_indicators):
                    # If we already collected holdings, exit table mode
                    if len(holdings) > 0:
                        in_table = False
                        break

                # 3. Header suppression: Ignore table header and continuation lines
                if "security" in line_text or "isin" in line_text or "market value" in line_text or "continued" in line_text:
                    continue

                # 4. Extract columns via Center-of-Mass Geometric Mapping
                row_data: Dict[str, str] = {}
                for col in table_rule.columns:
                    col_words = []
                    # Expand column threshold by 12 points for boundary coverage
                    c_start = col.x_start - 12.0
                    c_end = col.x_end + 12.0
                    
                    for w in line_words:
                        mid_x = (w["x0"] + w["x1"]) / 2.0
                        if c_start <= mid_x <= c_end:
                            col_words.append(w["text"])
                            
                    row_data[col.name] = " ".join(col_words).strip()

                sec_name = row_data.get("security_name", "")
                market_val_raw = row_data.get("market_value", "")

                # Clean numeric values
                market_val_clean = re.sub(r'[^\d.-]', '', market_val_raw)
                
                # Validation check: A valid row requires a non-numeric security name and a valid market value
                if len(sec_name) >= 3 and not sec_name.replace(".", "").isdigit():
                    try:
                        m_val = Decimal(market_val_clean)
                        if m_val > 0:
                            qty_clean = re.sub(r'[^\d.-]', '', row_data.get("quantity", "0")) or "0"
                            cost_clean = re.sub(r'[^\d.-]', '', row_data.get("cost", "0")) or "0"

                            holdings.append(Holding(
                                security_name=sec_name,
                                isin=row_data.get("isin") or None,
                                quantity=Decimal(qty_clean),
                                cost=Decimal(cost_clean),
                                market_value=m_val,
                                weight=None
                            ))
                    except (InvalidOperation, ValueError):
                        continue

        return holdings