# inspect_data.py
import pandas as pd
import glob
import os

RAW_DATA_DIR = "raw_data"

def find_and_inspect_first_good_file():
    """
    Finds the first valid parquet file and prints its key columns.
    """
    script_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(script_dir, '..'))
    raw_data_path = os.path.join(base_dir, RAW_DATA_DIR)
    
    all_files = glob.glob(os.path.join(raw_data_path, "*.parquet"))
    
    print("Searching for the first valid file to inspect...")
    for f in all_files:
        try:
            df = pd.read_parquet(f)
            # Check if it has the necessary columns
            if 'matchId' in df.columns and 'region' in df.columns:
                print(f"\nSuccess! Found a valid file: {os.path.basename(f)}")
                print("\nLet's inspect the 'matchId' and 'region' columns to understand the deduplication issue.")
                print("------------------------------------------------------------------")
                
                # Create the match_prefix column to see what it looks like
                df['match_prefix'] = df['matchId'].str.split('_').str[0]
                
                # Print the first 10 rows of the relevant columns
                print(df[['matchId', 'region', 'match_prefix']].head(10))
                print("------------------------------------------------------------------")
                
                # Check if the developer's logic would keep ANY rows
                is_match = df['match_prefix'] == df['region']
                print(f"\nDoes the logic 'match_prefix == region' work for this file?")
                print(f"Answer: {is_match.any()}")

                return # Stop after the first good file
        except:
            # Ignore corrupted files
            continue
            
    print("Could not find any valid files to inspect after searching all files.")


if __name__ == "__main__":
    find_and_inspect_first_good_file()