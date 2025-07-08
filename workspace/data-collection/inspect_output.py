# inspect_output.py (v2 - Lists all columns)
import pandas as pd
import os

# --- Configuration ---
FILE_TO_INSPECT = "prototype_dataset.parquet"
# --- End Configuration ---

def inspect_dataframe():
    """Loads a parquet file and prints its structure, a sample of its data,
    and a complete list of all its columns."""
    script_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(script_dir, '..'))
    file_path = os.path.join(base_dir, FILE_TO_INSPECT)

    if not os.path.exists(file_path):
        print(f"Error: The file '{file_path}' does not exist.")
        return

    print(f"--- Inspecting: {FILE_TO_INSPECT} ---")
    df = pd.read_parquet(file_path)

    print("\n[1] Dataframe Info (Columns, Data Types, Memory Usage):")
    # Using 'display.max_columns' to show a wider sample in the info summary
    with pd.option_context('display.max_columns', 10):
        df.info()

    print("\n[2] First 5 Rows of Data:")
    # Using 'display.max_columns' to show more columns in the head() output
    with pd.option_context('display.max_columns', 15):
        print(df.head())

    # --- NEW SECTION TO LIST ALL COLUMNS ---
    print(f"\n[3] Full List of All {len(df.columns)} Columns:")
    all_columns = df.columns.tolist()
    for column_name in all_columns:
        print(f"  - {column_name}")
    # --- END OF NEW SECTION ---

    print(f"\nInspection complete. The dataframe has {len(df.columns)} columns and {len(df)} rows.")


if __name__ == "__main__":
    inspect_dataframe()