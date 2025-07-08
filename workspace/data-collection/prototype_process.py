# prototype_process.py
import pandas as pd
import glob
import os
from tqdm import tqdm

# --- Configuration ---
RAW_DATA_DIR = "raw_data"
PROTOTYPE_OUTPUT_FILE = "prototype_dataset.parquet" # <-- CHANGED: Different output file
ENGINE = "fastparquet"
BATCH_SIZE = 200
PROTOTYPE_FILE_COUNT = 600 # <-- CHANGED: Only process a small number of files
# --- End Configuration ---

def prototype_processing():
    """
    Runs the robust batch processing logic on a small sample of the data
    to quickly verify that it works.
    """
    script_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(script_dir, '..'))
    raw_data_path = os.path.join(base_dir, RAW_DATA_DIR)
    output_path = os.path.join(base_dir, PROTOTYPE_OUTPUT_FILE)

    if os.path.exists(output_path):
        os.remove(output_path)

    all_files = glob.glob(os.path.join(raw_data_path, "*.parquet"))
    if not all_files:
        print(f"Error: No .parquet files found in '{raw_data_path}'.")
        return

    # --- KEY CHANGE: Use only a small slice of the files for the prototype ---
    files_to_process = all_files[:PROTOTYPE_FILE_COUNT]
    
    print("--- PROTOTYPE RUN ---")
    print(f"Processing a sample of {len(files_to_process)} files to verify logic.")
    
    batch_list = []
    successful_files = 0
    failed_files = 0
    first_write = True

    for f in tqdm(files_to_process, desc="Processing prototype sample"):
        try:
            df = pd.read_parquet(f)
            if 'matchId' not in df.columns or 'region' not in df.columns:
                failed_files += 1
                continue

            df["match_prefix"] = df["matchId"].str.split("_").str[0]
            region_match_mask = df["match_prefix"] == df["region"]
            cleaned_df = df[region_match_mask].drop("match_prefix", axis=1)

            if not cleaned_df.empty:
                batch_list.append(cleaned_df)
            
            successful_files += 1
        except Exception:
            failed_files += 1
            continue

        if len(batch_list) >= BATCH_SIZE:
            master_batch_df = pd.concat(batch_list, ignore_index=True)
            if first_write:
                master_batch_df.to_parquet(output_path, engine=ENGINE, index=False)
                first_write = False
            else:
                master_batch_df.to_parquet(output_path, engine=ENGINE, append=True)
            batch_list = []

    if batch_list:
        master_batch_df = pd.concat(batch_list, ignore_index=True)
        if first_write:
            master_batch_df.to_parquet(output_path, engine=ENGINE, index=False)
        else:
            master_batch_df.to_parquet(output_path, engine=ENGINE, append=True)

    print("\n--- Prototype Run Complete ---")
    print(f"Successfully processed data from {successful_files} files.")
    print(f"Skipped {failed_files} corrupted or invalid files.")
    
    if os.path.exists(output_path):
        final_df = pd.read_parquet(output_path)
        print(f"\n✅ Success! Prototype dataset created at: {output_path}")
        print(f"It contains {len(final_df)} rows.")
    else:
        print("\n❌ Failure. No valid data was found to create the output file.")


if __name__ == "__main__":
    prototype_processing()