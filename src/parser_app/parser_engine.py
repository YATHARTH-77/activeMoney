import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from parser_app.artifact_schema import LayoutArtifact, TableRule
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

logger = logging.getLogger(__name__)


class DeterministicParser:
    def __init__(self, artifact: LayoutArtifact):
        self.artifact = artifact

    def parse(self, pdf_pages: List[Dict[str, Any]], source_hash: str) -> ParsedStatement:
        context = self._extract_context(pdf_pages)
        summary = self._extract_summary(pdf_pages)
        holdings = self._extract_holdings(pdf_pages)
        transactions = self._extract_transactions(pdf_pages)

        return ParsedStatement(
            statement_id=f"STMT-{source_hash[:8]}",
            context=context,
            summary=summary,
            holdings=holdings,
            transactions=transactions,
            provenance=Provenance(
                source_hash=source_hash,
                layout_fingerprint=self.artifact.layout_fingerprint,
                artifact_version=self.artifact.artifact_version,
            ),
            validation=ValidationResult(
                status=ValidationStatus.NOT_VERIFIABLE,
                details="Parsed deterministically.",
            ),
        )

    def _extract_context(self, pdf_pages: List[Dict[str, Any]]) -> StatementContext:
        provider = self.artifact.provider_name or "Unknown Provider"
        strategy = "Consolidated Portfolio"
        client_id = "Unknown"
        period = "Oct 2026"
        currency = "INR"

        full_text = "\n".join(p.get("text", "") for p in pdf_pages)

        client_match = re.search(
            r"(?:Client|Investor|Account)\s*(?:ID|Code|:)?\s*[:\s-]*([A-Za-z0-9_-]+)",
            full_text,
            re.IGNORECASE,
        )
        if client_match:
            client_id = client_match.group(1).strip()

        if "INR" in full_text or "₹" in full_text or "Rupee" in full_text:
            currency = "INR"
        elif "USD" in full_text or "$" in full_text:
            currency = "USD"

        return StatementContext(
            provider_name=provider,
            strategy_name=strategy,
            client_identifier=client_id,
            statement_period=period,
            currency=currency,
        )

    def _extract_summary(self, pdf_pages: List[Dict[str, Any]]) -> Summary:
        values: Dict[str, Optional[str]] = {
            "opening_value": "0",
            "closing_value": "0",
            "cash_balance": "0",
            "fees_charged": None,
            "nav_per_unit": None,
        }

        full_text = "\n".join(p.get("text", "") for p in pdf_pages)
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]

        for rule in self.artifact.summary_rules:
            norm_rule = rule.name.lower()
            if "open" in norm_rule:
                target_key = "opening_value"
            elif "close" in norm_rule or "net" in norm_rule or "portfolio" in norm_rule:
                target_key = "closing_value"
            elif "cash" in norm_rule or "bank" in norm_rule:
                target_key = "cash_balance"
            elif "fee" in norm_rule or "charge" in norm_rule:
                target_key = "fees_charged"
            elif "nav" in norm_rule:
                target_key = "nav_per_unit"
            else:
                target_key = rule.name

            clean_label = re.sub(r"\[P\d+[^\]]*\]", "", rule.label).strip()
            if not clean_label:
                continue

            label_pattern = re.escape(clean_label)

            for line in lines:
                match = re.search(label_pattern, line, re.IGNORECASE)
                if match:
                    text_after_label = line[match.end() :]
                    numbers = re.findall(
                        r"[-+]?\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b",
                        text_after_label,
                    )
                    if numbers:
                        clean_val = numbers[0].replace(",", "")
                        try:
                            Decimal(clean_val)
                            values[target_key] = clean_val
                            break
                        except InvalidOperation:
                            continue

        # Fallback regex scans if summary rules missed a field
        if values["closing_value"] == "0":
            close_match = re.search(
                r"(?:closing(?:\s+portfolio)?(?:\s+value|\s+val)?|net\s+closing\s+value|portfolio\s+value)[^0-9\n]*([0-9,]+(?:\.[0-9]+)?)",
                full_text,
                re.IGNORECASE,
            )
            if close_match:
                values["closing_value"] = close_match.group(1).replace(",", "")

        if values["cash_balance"] == "0":
            cash_match = re.search(
                r"(?:settled\s+cash(?:\s+balance)?|cash(?:\s+balance)?|bank\s+balance)[^0-9\n]*([0-9,]+(?:\.[0-9]+)?)",
                full_text,
                re.IGNORECASE,
            )
            if cash_match:
                values["cash_balance"] = cash_match.group(1).replace(",", "")

        if values["opening_value"] == "0":
            open_match = re.search(
                r"(?:opening(?:\s+portfolio)?(?:\s+value|\s+balance)?)[^0-9\n]*([0-9,]+(?:\.[0-9]+)?)",
                full_text,
                re.IGNORECASE,
            )
            if open_match:
                values["opening_value"] = open_match.group(1).replace(",", "")

        return Summary(
            opening_value=values.get("opening_value") or "0",
            closing_value=values.get("closing_value") or "0",
            cash_balance=values.get("cash_balance") or "0",
            fees_charged=values.get("fees_charged"),
            nav_per_unit=values.get("nav_per_unit"),
        )

    def _parse_row_tokens_fallback(self, raw_line: str) -> Optional[Holding]:
        """
        Deterministic structural fallback for rows with pipe delimiters ('|')
        or standard ISIN-anchored tabular tokens when LLM X-bounds shift slightly.
        """
        clean_line = raw_line.strip()
        if not clean_line:
            return None

        # 1. Pipe-delimited format: e.g. "Reliance Ind | INE002A01018 | 200 | 2500.00 | 510000.00 | 48.57"
        if "|" in clean_line:
            parts = [p.strip() for p in clean_line.split("|") if p.strip()]
            if len(parts) >= 3:
                sec_name = parts[0]
                if any(
                    k in sec_name.lower()
                    for k in ["security", "opening", "closing", "management fee", "client"]
                ):
                    return None

                isin_val = None
                numeric_vals: List[Decimal] = []

                for p in parts[1:]:
                    if re.match(r"^[A-Z]{2}[A-Z0-9]{8,12}$", p):
                        isin_val = p
                    else:
                        num_clean = re.sub(r"[^\d.-]", "", p)
                        try:
                            numeric_vals.append(Decimal(num_clean))
                        except InvalidOperation:
                            continue

                if len(sec_name) >= 2 and numeric_vals:
                    qty = numeric_vals[0] if len(numeric_vals) >= 1 else Decimal("0")
                    if len(numeric_vals) == 2:
                        # [Qty, MarketValue]
                        cost = Decimal("0")
                        m_val = numeric_vals[1]
                        weight = None
                    elif len(numeric_vals) == 3:
                        # [Qty, Cost, MarketValue]
                        cost = numeric_vals[1]
                        m_val = numeric_vals[2]
                        weight = None
                    else:
                        # [Qty, Cost, MarketValue, Weight/PL]
                        cost = numeric_vals[1]
                        m_val = numeric_vals[2]
                        weight = numeric_vals[3]

                    if m_val > 0:
                        return Holding(
                            security_name=sec_name,
                            isin=isin_val,
                            quantity=qty,
                            cost=cost,
                            market_value=m_val,
                            weight=weight,
                        )

        # 2. ISIN-Anchored Token Stream Fallback:
        # Matches: "<Security Name> <ISIN: INE...> <Qty> [<Cost>] <MarketValue> [<Weight/PL>]"
        isin_match = re.search(r"\b([A-Z]{2}[A-Z0-9]{9,10})\b", clean_line)
        if isin_match:
            sec_name = clean_line[: isin_match.start()].replace("|", "").strip()
            isin_val = isin_match.group(1).strip()
            rest = clean_line[isin_match.end() :].replace("|", " ").strip()

            num_tokens = re.findall(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", rest)
            decimals = []
            for t in num_tokens:
                try:
                    decimals.append(Decimal(t.replace(",", "")))
                except InvalidOperation:
                    continue

            if len(sec_name) >= 2 and len(decimals) >= 2:
                qty = decimals[0]
                if len(decimals) == 2:
                    cost = Decimal("0")
                    m_val = decimals[1]
                else:
                    cost = decimals[1]
                    m_val = decimals[2]

                if m_val > 0:
                    return Holding(
                        security_name=sec_name,
                        isin=isin_val,
                        quantity=qty,
                        cost=cost,
                        market_value=m_val,
                        weight=None,
                    )

        return None

    def _extract_holdings(self, pdf_pages: List[Dict[str, Any]]) -> List[Holding]:
        table_rule: Optional[TableRule] = self.artifact.holdings_table
        columns = table_rule.columns if table_rule and table_rule.columns else []

        holdings: List[Holding] = []
        clean_anchor = (
            re.sub(r"\[P\d+[^\]]*\]", "", table_rule.start_anchor).strip().lower()
            if table_rule and table_rule.start_anchor
            else ""
        )
        state = "SEARCHING"

        terminal_sections = [
            "transaction ledger",
            "transaction history",
            "capital gains",
        ]

        noise_indicators = [
            "disclaimer",
            "confidentiality notice",
            "past performance",
            "disclosures",
            "continued on next page",
            "fee schedule",
            "account summary",
            "executive financial summary",
        ]

        for page in pdf_pages:
            if state == "TERMINATED":
                break

            words = page.get("words", [])
            if not words:
                continue

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

            for top in sorted(lines_dict.keys()):
                line_words = sorted(lines_dict[top], key=lambda item: item["x0"])
                raw_line_str = " ".join(w["text"] for w in line_words).strip()
                line_text = raw_line_str.lower()

                is_header_row = (
                    ("security" in line_text or "scrip" in line_text or "particular" in line_text or "holding" in line_text)
                    and ("value" in line_text or "market" in line_text or "amount" in line_text or "isin" in line_text or "qty" in line_text)
                )

                if state == "SEARCHING":
                    if (
                        (clean_anchor and clean_anchor in line_text)
                        or "holdings ledger" in line_text
                        or "portfolio holdings" in line_text
                        or "current holdings" in line_text
                        or "detailed holdings" in line_text
                        or "holdings" in line_text
                        or is_header_row
                    ):
                        state = "ACTIVE_TABLE"
                    continue

                if is_header_row or "continued" in line_text or "holdings report" in line_text:
                    continue

                if any(term in line_text for term in terminal_sections):
                    if len(holdings) > 0:
                        state = "TERMINATED"
                        break
                    continue

                if any(noise in line_text for noise in noise_indicators) or re.search(
                    r"\bpage\s+\d+\s+of\s+\d+\b", line_text
                ):
                    continue

                # STAGE 1: Center-of-Mass Geometric Column Projection
                extracted_holding: Optional[Holding] = None

                if columns and "|" not in raw_line_str:
                    row_data: Dict[str, str] = {}
                    sorted_cols = sorted(columns, key=lambda c: c.x_start)

                    for idx, col in enumerate(sorted_cols):
                        col_words = []
                        c_start = col.x_start - 15.0
                        c_end = col.x_end + (35.0 if idx == len(sorted_cols) - 1 else 15.0)

                        for w in line_words:
                            if w["text"] == "|":
                                continue
                            mid_x = (w["x0"] + w["x1"]) / 2.0
                            if c_start <= mid_x <= c_end:
                                col_words.append(w["text"])

                        row_data[col.name] = " ".join(col_words).strip()

                    def find_cell(synonyms: List[str]) -> str:
                        for s in synonyms:
                            for col_name, val in row_data.items():
                                norm_col = col_name.lower().replace(" ", "_")
                                if s in norm_col and val.strip():
                                    return val.strip()
                        return ""

                    sec_name = find_cell(["security", "name", "desc", "scrip", "particular", "holding", "company"])
                    isin_val = find_cell(["isin", "code"])
                    qty_raw = find_cell(["quantity", "qty", "units", "shares"])
                    cost_raw = find_cell(["cost", "price", "avg"])
                    market_val_raw = find_cell(["market_value", "market", "value", "val", "amount", "worth"])

                    if not sec_name and sorted_cols:
                        sec_name = row_data.get(sorted_cols[0].name, "")

                    market_val_clean = re.sub(r"[^\d.-]", "", market_val_raw)
                    qty_clean = re.sub(r"[^\d.-]", "", qty_raw) or "0"
                    cost_clean = re.sub(r"[^\d.-]", "", cost_raw) or "0"

                    summary_terms = ["total", "closing", "opening", "balance", "subtotal", "sub-total", "net worth", "end of"]
                    is_summary_line = any(term in sec_name.lower() for term in summary_terms)
                    is_disclaimer_line = any(term in sec_name.lower() for term in ["disclaimer", "statement", "confidential", "risk"])

                    if (
                        len(sec_name) >= 2
                        and len(sec_name) <= 85
                        and not sec_name.replace(".", "").isdigit()
                        and not is_summary_line
                        and not is_disclaimer_line
                    ):
                        try:
                            m_val = Decimal(market_val_clean)
                            if m_val > 0:
                                extracted_holding = Holding(
                                    security_name=sec_name,
                                    isin=isin_val if isin_val else None,
                                    quantity=Decimal(qty_clean),
                                    cost=Decimal(cost_clean),
                                    market_value=m_val,
                                    weight=None,
                                )
                        except (InvalidOperation, ValueError):
                            extracted_holding = None

                # STAGE 2: Pipe-Delimited & ISIN-Anchored Structural Fallback
                if extracted_holding is None:
                    extracted_holding = self._parse_row_tokens_fallback(raw_line_str)

                if extracted_holding is not None:
                    holdings.append(extracted_holding)

        return holdings

    def _extract_transactions(self, pdf_pages: List[Dict[str, Any]]) -> List[Transaction]:
        transactions: List[Transaction] = []
        full_text = "\n".join(p.get("text", "") for p in pdf_pages)
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]

        txn_pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2})\s+(buy|sell|dividend|fee|inflow|outflow)\s+([A-Za-z0-9_\s-]+?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:,\d{3})*(?:\.\d+)?)$",
            re.IGNORECASE,
        )

        for line in lines:
            match = txn_pattern.match(line)
            if match:
                date_str, t_type, sec, qty_str, amt_str = match.groups()
                try:
                    transactions.append(
                        Transaction(
                            date=date_str,
                            transaction_type=t_type.lower(),
                            security=sec.strip(),
                            quantity=Decimal(qty_str),
                            amount=Decimal(amt_str.replace(",", "")),
                        )
                    )
                except InvalidOperation:
                    continue

        return transactions