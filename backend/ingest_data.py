import json
import os
import ast
import psycopg2

# --- IMPORTANT: Paste your Neon database connection URL here ---
DATABASE_URL = ""

print("Connecting to the database...")
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
print("✅ Connection successful.")

# --- Create the database table ---
print("Creating 'matchups' table if it doesn't exist...")
cur.execute("""
    CREATE TABLE IF NOT EXISTS matchups (
        champ1 TEXT,
        role1 TEXT,
        champ2 TEXT,
        role2 TEXT,
        relationship TEXT,
        wins INTEGER,
        total_games INTEGER,
        win_rate REAL,
        PRIMARY KEY (champ1, role1, champ2, role2, relationship)
    );
""")
# Create an index for faster lookups
cur.execute("""
    CREATE INDEX IF NOT EXISTS matchups_idx 
    ON matchups (champ1, role1, champ2, role2, relationship);
""")
conn.commit()
print("✅ Table and index are ready.")


# --- Load local data files ---
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
MAPPING_FILE = os.path.join(DATA_DIR, "champion_mapping.json")
MATCHUP_WR_FILE = os.path.join(DATA_DIR, "matchup_winrates.json")

print("Loading local JSON files...")
with open(MAPPING_FILE, 'r') as f: id_to_name = json.load(f)
with open(MATCHUP_WR_FILE, 'r') as f: matchup_data_raw = json.load(f)
print("✅ JSON files loaded.")

# --- Prepare and insert data ---
print("Preparing data for ingestion. This may take a moment...")
all_matchups = []
for str_key, values in matchup_data_raw.items():
    key = ast.literal_eval(str_key)
    p1_name = id_to_name.get(str(key[0]))
    p2_name = id_to_name.get(str(key[2]))
    
    if p1_name and p2_name:
        all_matchups.append((
            p1_name, key[1], p2_name, key[3], key[4],
            values['wins'], values['total_games'], values['win_rate']
        ))

print(f"✅ Data prepared. {len(all_matchups)} matchups to ingest.")
print("Starting ingestion. This will take several minutes...")

# Use executemany for efficient batch insertion
insert_query = """
    INSERT INTO matchups (champ1, role1, champ2, role2, relationship, wins, total_games, win_rate)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (champ1, role1, champ2, role2, relationship) DO NOTHING;
"""

# Insert in chunks to manage memory
chunk_size = 10000
for i in range(0, len(all_matchups), chunk_size):
    chunk = all_matchups[i:i + chunk_size]
    cur.executemany(insert_query, chunk)
    conn.commit()
    print(f"  ... Inserted chunk {i // chunk_size + 1} / {len(all_matchups) // chunk_size + 1}")

print("✅ Data ingestion complete!")
cur.close()
conn.close()