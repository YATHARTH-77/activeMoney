import argparse
import json
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "src"))
sys.path.insert(0, src_dir)

from parser_app.statement_repository import StatementRepository  # noqa: E402


def print_header(title: str):
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def main():
    parser = argparse.ArgumentParser(description="Activv Money - Statement Review Interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: LIST
    list_parser = subparsers.add_parser("list", help="List statements in the queue")
    list_parser.add_argument("--status", type=str, default="ALL", choices=["ALL", "PASS", "FAIL", "NOT_VERIFIABLE"])
    list_parser.add_argument("--limit", type=int, default=10, help="Pagination limit")

    # Subcommand: VIEW
    view_parser = subparsers.add_parser("view", help="View secure details of a specific statement")
    view_parser.add_argument("id", type=str, help="The Statement ID (e.g., QUAR-abc12345)")

    # Subcommand: RESOLVE
    resolve_parser = subparsers.add_parser("resolve", help="Mark a quarantined statement as reviewed")
    resolve_parser.add_argument("id", type=str, help="The Statement ID to resolve")

    args = parser.parse_args()
    repo = StatementRepository("data/statements.db")

    if args.command == "list":
        statements = repo.list_statements(status_filter=args.status, limit=args.limit)
        print_header(f"STATEMENT QUEUE (Filter: {args.status})")
        print(f"{'ID':<15} | {'STATUS':<6} | {'RSLVD'} | {'PROVIDER':<25} | {'DETAILS'}")
        print("-" * 80)
        for s in statements:
            resolved_mark = "✅" if s["resolved"] else "⏳"
            # Truncate details for table view
            details = (s["details"][:25] + "..") if len(s["details"]) > 25 else s["details"]
            print(f"{s['statement_id']:<15} | {s['status']:<6} | {resolved_mark:<5} | {s['provider_name']:<25} | {details}")
        print("\n")

    elif args.command == "view":
        raw_json = repo.get_statement_json(args.id)
        if not raw_json:
            print(f"Error: Statement {args.id} not found.")
            sys.exit(1)
            
        data = json.loads(raw_json)
        
        # PRIVACY MASKING: Redact client identifier before printing to screen
        if "context" in data and "client_identifier" in data["context"]:
            data["context"]["client_identifier"] = "*** REDACTED PII ***"
            
        print_header(f"SECURE VIEW: {args.id}")
        print(json.dumps(data, indent=2))
        print("\nNote: Client identifiers have been masked for security.")

    elif args.command == "resolve":
        success = repo.mark_resolved(args.id)
        if success:
            print(f"✅ Statement {args.id} has been marked as human-resolved.")
        else:
            print(f"❌ Error: Statement {args.id} not found.")

if __name__ == "__main__":
    main()