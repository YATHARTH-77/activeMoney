import sqlite3
import json
import os

os.makedirs('samples/outputs', exist_ok=True)
conn = sqlite3.connect('data/statements.db')

# Fetch only the statements that passed strict validation
rows = conn.execute("SELECT statement_id, provider_name, json_payload FROM statements WHERE status='PASS'").fetchall()

for r in rows:
    stmt_id = r[0]
    provider = r[1].strip().replace(" ", "_").replace("/", "")
    filename = f"samples/outputs/{stmt_id}_{provider}.json"
    
    data = json.loads(r[2])
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

print(f"✅ Exported {len(rows)} verified JSON outputs to samples/outputs/")