from decimal import Decimal
from typing import Dict, List

from parser_app.schema import ParsedStatement, ValidationResult, ValidationStatus


class FinancialValidator:
    # Allow up to 1.00 (e.g., 1 INR or 1 USD) discrepancy due to provider rounding errors
    TOLERANCE = Decimal("1.00")

    @classmethod
    def validate(cls, statement: ParsedStatement) -> ParsedStatement:
        """
        Runs modular financial checks and returns the statement 
        with an updated validation result.
        """
        checks: Dict[str, ValidationStatus] = {}
        details: List[str] = []

        # 1. Total Portfolio Value Check
        val_status, val_msg = cls._check_holdings_sum(statement)
        checks["portfolio_sum"] = val_status
        details.append(val_msg)

        # 2. AIF NAV Check
        nav_status, nav_msg = cls._check_aif_nav(statement)
        checks["aif_nav"] = nav_status
        details.append(nav_msg)

        # Determine overall status
        statuses = checks.values()
        if ValidationStatus.FAIL in statuses:
            final_status = ValidationStatus.FAIL
        elif ValidationStatus.PASS in statuses:
            # If at least one check passed and nothing failed
            final_status = ValidationStatus.PASS
        else:
            final_status = ValidationStatus.NOT_VERIFIABLE

        statement.validation = ValidationResult(
            status=final_status,
            details=" | ".join(details)
        )
        return statement

    @classmethod
    def _check_holdings_sum(cls, statement: ParsedStatement) -> tuple[ValidationStatus, str]:
        """Verifies: Sum(Holdings Market Value) + Cash == Closing Value"""
        if not statement.holdings:
            return ValidationStatus.NOT_VERIFIABLE, "No holdings to verify sum."

        total_holdings_val = sum((h.market_value for h in statement.holdings), Decimal("0"))
        expected_closing = total_holdings_val + statement.summary.cash_balance
        actual_closing = statement.summary.closing_value
        
        diff = abs(expected_closing - actual_closing)
        
        if diff <= cls.TOLERANCE:
            return ValidationStatus.PASS, f"Portfolio sum matched (Diff: {diff})"
        else:
            return (
                ValidationStatus.FAIL, 
                f"Portfolio sum mismatch. Expected {expected_closing}, got {actual_closing} (Diff: {diff})"
            )

    @classmethod
    def _check_aif_nav(cls, statement: ParsedStatement) -> tuple[ValidationStatus, str]:
        """Verifies: Total Units * NAV per Unit == Closing Value (for AIFs)"""
        if not statement.summary.nav_per_unit:
            return ValidationStatus.NOT_VERIFIABLE, "No NAV per unit provided."
            
        if not statement.holdings or len(statement.holdings) > 1:
            return ValidationStatus.NOT_VERIFIABLE, "Complex NAV structure; requires manual verification."

        # In simple AIFs, there is often 1 holding (the fund itself)
        fund_qty = statement.holdings[0].quantity
        expected_val = fund_qty * statement.summary.nav_per_unit
        actual_val = statement.summary.closing_value
        
        diff = abs(expected_val - actual_val)
        
        # AIFs have higher rounding variance on NAV multiplication (often NAV is truncated to 4 decimals)
        nav_tolerance = Decimal("5.00") 
        if diff <= nav_tolerance:
            return ValidationStatus.PASS, f"AIF NAV matched (Diff: {diff})"
        else:
            return (
                ValidationStatus.FAIL, 
                f"AIF NAV mismatch. Expected {expected_val}, got {actual_val} (Diff: {diff})"
            )