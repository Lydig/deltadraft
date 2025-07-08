# process_data_chunked.py (v4 - Robust single-pass version)
import pandas as pd
import glob
import os
from tqdm import tqdm
import shutil

# --- Configuration ---
RAW_DATA_DIR = "raw_data"
OUTPUT_FILE = "master_dataset.parquet"
ENGINE = "fastparquet"
# --- End Configuration ---

def process_data_robustly():
    """
    Processes all raw data in a memory-efficient, single-pass, robust manner.
    It cleans each file individually and appends to a final dataset, skipping corrupted files.
    """
    script_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(script_dir, '..'))
    raw_data_path = os.path.join(base_dir, RAW_DATA_DIR)
    output_path = os.path.join(base_dir, OUTPUT_FILE)

    # Clean up the final file from any previous failed runs
    if os.path.exists(output_path):
        os.remove(output_path)

    all_files = glob.glob(os.path.join(raw_data_path, "*.parquet"))
    if not all_files:
        print(f"Error: No .parquet files found in '{raw_data_path}'.")
        return

    print(f"Found {len(all_files)} files to process.")
    print(f"Cleaned data will be saved to '{output_path}'.")
    
    successful_files = 0
    failed_files = 0
    
    # Loop through each small file, process it, and append.
    for f in tqdm(all_files, desc="Processing files"):
        try:
            # 1. Read a single raw data file
            df = pd.read_parquet(f)

            # 2. Validate the data structure
            if 'matchId' not in df.columns or 'region' not in df.columns:
                failed_files += 1
                continue # Skip this file

            # 3. Apply the deduplication logic
            df["match_prefix"] = df["matchId"].str.split("_").str[0]
            region_match_mask = df["match_prefix"] == df["region"]
            cleaned_df = df[region_match_mask].drop("match_prefix", axis=1)

            # 4. Append the cleaned data to the master file
            if not cleaned_df.empty:
                # The fastparquet engine's append=True creates the file on the first write.
                cleaned_df.to_parquet(output_path, engine=ENGINE, append=True)
            
            successful_files += 1

        except Exception:
            # Catch any other error, mark as failed, and continue
            failed_files += 1
            continue
            
    print("\n--- Processing Complete ---")
    print(f"Successfully processed {successful_files} files.")
    print(f"Skipped {failed_files} corrupted or invalid files.")
    
    if os.path.exists(output_path):
        print(f"\nFinal, clean dataset is located at: {output_path}")
    else:
        print("\nError: No data was processed successfully. The output file was not created.")

if __name__ == "__main__":
    process_data_robustly()