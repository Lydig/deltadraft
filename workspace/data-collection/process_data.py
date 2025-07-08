# process_data.py
import pandas as pd
import glob
import os
from tqdm import tqdm

# --- Configuration ---
# The directory where the downloaded files are stored.
RAW_DATA_DIR = "raw_data"

# The path for the final, processed file. This will be saved in your main project folder.
OUTPUT_FILE = "master_dataset.parquet"
# --- End Configuration ---

def explore_and_process_data():
    """
    Loads all raw parquet files, explores their structure, deduplicates,
    and saves the result to a single master file.
    """
    # 1. Find all the downloaded .parquet files
    # We need to go up one directory from where the script is located to find the raw_data folder.
    script_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(script_dir, '..'))
    raw_data_path = os.path.join(base_dir, RAW_DATA_DIR)
    output_path = os.path.join(base_dir, OUTPUT_FILE)
    
    all_files = glob.glob(os.path.join(raw_data_path, "*.parquet"))
    if not all_files:
        print(f"Error: No .parquet files found in '{raw_data_path}'.")
        return

    print(f"Found {len(all_files)} files to process in '{raw_data_path}'.")

    # 2. Load all files into a single DataFrame
    df_list = []
    for f in tqdm(all_files, desc="Loading raw files"):
        try:
            df = pd.read_parquet(f)
            df_list.append(df)
        except Exception as e:
            print(f"Could not read file {f}. Skipping. Error: {e}")
    
    if not df_list:
        print("Error: Could not load any data. Aborting.")
        return

    # Combine all individual dataframes into one large one
    master_df = pd.concat(df_list, ignore_index=True)
    
    print("\n--- Initial Data Exploration ---")
    print(f"Total rows loaded: {len(master_df)}")
    print("Columns found in the dataset:")
    print(master_df.columns.tolist())
    print("\nFirst 5 rows of the combined data:")
    print(master_df.head())
    print("\nData types and memory usage:")
    master_df.info(verbose=False, memory_usage="deep")

    # 3. Apply the deduplication logic from the developer
    print("\n--- Applying Deduplication ---")
    initial_rows = len(master_df)
    
    required_cols = ["matchId", "region"]
    if not all(col in master_df.columns for col in required_cols):
        print(f"Error: Missing columns {required_cols} needed for deduplication.")
        print("Cannot perform deduplication. Saving the raw combined file instead.")
    else:
        master_df["match_prefix"] = master_df["matchId"].str.split("_").str[0]
        region_match_mask = master_df["match_prefix"] == master_df["region"]
        master_df = master_df[region_match_mask]
        master_df = master_df.drop("match_prefix", axis=1)
        
        final_rows = len(master_df)
        print(f"Deduplication complete. Removed {initial_rows - final_rows} duplicate rows.")
        print(f"Final total rows: {final_rows}")

    # 4. Save the final, cleaned dataset
    print(f"\n--- Saving Cleaned Dataset ---")
    print(f"Saving the final dataset to '{output_path}'...")
    try:
        master_df.to_parquet(output_path, index=False)
        print(f"\nSuccessfully saved master dataset!")
    except Exception as e:
        print(f"Error saving file: {e}")


if __name__ == "__main__":
    explore_and_process_data()