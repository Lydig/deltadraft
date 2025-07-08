# finalize_dataset.py (v3 - SAFE VERSION, does not delete original file)
import pandas as pd
import pyarrow.parquet as pq
import os
from tqdm import tqdm

# --- Configuration ---
INPUT_FILE = "master_dataset.parquet"
OUTPUT_FILE = "master_dataset_final.parquet" # Writing to a new, separate file
BATCH_SIZE = 100000

# --- Data Quality Rules ---
VALID_QUEUE_IDS = [420, 440]
MIN_GAME_DURATION = 600
# ---

def finalize_large_file_safely():
    """
    Reads the master dataset, applies all data quality rules, and saves the
    result to a NEW file, leaving the original file untouched.
    """
    if os.path.exists(OUTPUT_FILE):
        print(f"Warning: Output file '{OUTPUT_FILE}' already exists. It will be overwritten.")
        os.remove(OUTPUT_FILE)

    seen_match_ids = set()
    total_rows_before = 0
    total_rows_after = 0
    
    roles = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
    champion_cols = [f'team_{team}_{role}_championId' for team in [100, 200] for role in roles]

    print(f"Starting final cleaning and deduplication of '{INPUT_FILE}'...")
    print(f"The clean data will be saved to a new file: '{OUTPUT_FILE}'")
    
    pq_file = pq.ParquetFile(INPUT_FILE)
    batch_iterator = pq_file.iter_batches(batch_size=BATCH_SIZE)
    
    first_write = True
    
    for batch in tqdm(batch_iterator, total=pq_file.num_row_groups, desc="Processing chunks"):
        chunk = batch.to_pandas()
        total_rows_before += len(chunk)
        
        # Apply all quality filters
        chunk = chunk[chunk['queueId'].isin(VALID_QUEUE_IDS)]
        chunk = chunk[chunk['gameDuration'] >= MIN_GAME_DURATION]
        chunk = chunk[(chunk[champion_cols] > 0).all(axis=1)]
        
        # Remove duplicates
        chunk.drop_duplicates(subset=['matchId'], keep='first', inplace=True)
        is_new_id = ~chunk['matchId'].isin(seen_match_ids)
        new_rows = chunk[is_new_id]
        
        if not new_rows.empty:
            seen_match_ids.update(new_rows['matchId'])
            total_rows_after += len(new_rows)
            
            if first_write:
                new_rows.to_parquet(OUTPUT_FILE, engine='fastparquet', index=False)
                first_write = False
            else:
                new_rows.to_parquet(OUTPUT_FILE, engine='fastparquet', append=True)

    print("\n--- Finalization Complete ---")
    print(f"Total rows read: {total_rows_before}")
    print(f"Rows removed by filters & deduplication: {total_rows_before - total_rows_after}")
    print(f"Total clean rows in new dataset: {total_rows_after}")
    
    # --- NO DELETION OR RENAMING ---
    print(f"\n✅ Success! The new, clean dataset has been saved to '{OUTPUT_FILE}'.")
    print(f"Your original file, '{INPUT_FILE}', has not been changed or deleted.")

if __name__ == "__main__":
    finalize_large_file_safely()