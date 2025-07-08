# process_full_dataset.py
import pandas as pd
import glob
import os
from tqdm import tqdm

# --- Configuration ---
RAW_DATA_DIR = "raw_data"
OUTPUT_FILE = "master_dataset.parquet"
ENGINE = "fastparquet"
BATCH_SIZE = 200 # Process 200 files before writing to disk
# --- End Configuration ---

def process_data_in_batches():
    """
    Processes all raw data in robust batches to avoid file I/O errors.
    This script processes the FULL dataset.
    """
    script_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(script_dir, '..'))
    raw_data_path = os.path.join(base_dir, RAW_DATA_DIR)
    output_path = os.path.join(base_dir, OUTPUT_FILE)

    # Clean up from any previous failed runs
    if os.path.exists(output_path):
        os.remove(output_path)

    all_files = glob.glob(os.path.join(raw_data_path, "*.parquet"))
    if not all_files:
        print(f"Error: No .parquet files found in '{raw_data_path}'.")
        return

    print(f"--- FULL DATASET PROCESSING ---")
    print(f"Found {len(all_files)} files. Processing in batches of {BATCH_SIZE}.")
    
    batch_list = []
    successful_files = 0
    failed_files = 0
    first_write = True

    for f in tqdm(all_files, desc="Processing files"):
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

        # Check if the batch is full and needs to be written to disk
        if len(batch_list) >= BATCH_SIZE:
            master_batch_df = pd.concat(batch_list, ignore_index=True)
            if first_write:
                master_batch_df.to_parquet(output_path, engine=ENGINE, index=False)
                first_write = False
            else:
                master_batch_df.to_parquet(output_path, engine=ENGINE, append=True)
            batch_list = []

    # Write any remaining data in the last batch
    if batch_list:
        master_batch_df = pd.concat(batch_list, ignore_index=True)
        if first_write:
            master_batch_df.to_parquet(output_path, engine=ENGINE, index=False)
        else:
            master_batch_df.to_parquet(output_path, engine=ENGINE, append=True)

    print("\n--- Processing Complete ---")
    print(f"Successfully processed data from {successful_files} files.")
    print(f"Skipped {failed_files} corrupted or invalid files.")
    
    if os.path.exists(output_path):
        final_df = pd.read_parquet(output_path)
        print(f"\n✅ Success! Master dataset created at: {output_path}")
        print(f"It contains a total of {len(final_df)} rows and {len(final_df.columns)} columns.")
    else:
        print("\n❌ Error: No valid data was found to create the output file.")


if __name__ == "__main__":
    process_data_in_batches()