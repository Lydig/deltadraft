# download_data.py
import os
import argparse
from datetime import datetime, timedelta
from typing import List, Tuple
from azure.storage.blob import ContainerClient, BlobProperties
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration ---
# The full URL with the SAS token provided by the developer.
# IMPORTANT: This token is a secret and expires. Do not share it publicly.
SAS_URL = ""

# The prefix for the data we want to download within the container.
PROCESSED_DATA_PREFIX = "processed"

# The local directory where files will be saved.
OUTPUT_DIR = "raw_data"
# --- End Configuration ---


def get_blobs_for_timespan(container_client: ContainerClient, months: int) -> List[BlobProperties]:
    """Get blobs from the last N months."""
    all_blobs: List[BlobProperties] = []
    current_date = datetime.now()
    print(f"Searching for blobs from the last {months} months...")
    for month_offset in range(months):
        date = current_date - timedelta(days=30 * month_offset)
        prefix = f"{PROCESSED_DATA_PREFIX}/{date.year}/{date.month:02d}/"
        print(f"  - Checking prefix: {prefix}")
        try:
            month_blobs = container_client.list_blobs(name_starts_with=prefix)
            all_blobs.extend(list(month_blobs))
        except Exception as e:
            print(f"Could not list blobs for prefix {prefix}. This might be expected if data for that month doesn't exist. Error: {e}")
    return all_blobs


def download_single_file(args: Tuple[str, str, BlobProperties]) -> str:
    """Download a single file from Azure Blob Storage using a SAS URL."""
    container_sas_url, output_dir, blob = args
    file_name = os.path.basename(blob.name)
    output_path = os.path.join(output_dir, file_name)

    # Create a new client for each thread to ensure thread safety.
    container_client = ContainerClient.from_container_url(container_sas_url)
    blob_client = container_client.get_blob_client(blob.name)

    with open(output_path, "wb") as file:
        download_stream = blob_client.download_blob()
        file.write(download_stream.readall())

    return file_name


def download_new_parquet_files(months: int) -> None:
    """Download new parquet files from Azure that don't exist locally."""
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Data will be saved in the '{os.path.abspath(OUTPUT_DIR)}' directory.")

    # Initialize Azure client using the SAS URL
    print("Connecting to Azure Blob Storage...")
    container_client = ContainerClient.from_container_url(SAS_URL)

    # Get list of existing local files
    local_files = set(os.listdir(OUTPUT_DIR))

    # Get all blobs from the last N months
    azure_files = get_blobs_for_timespan(container_client, months=months)

    # Filter files that need to be downloaded
    files_to_download = [
        blob for blob in azure_files if os.path.basename(blob.name) not in local_files
    ]

    print(f"\nFound {len(azure_files)} total files in Azure from the last {months} months.")
    print(f"Files already downloaded: {len(azure_files) - len(files_to_download)}")

    if not files_to_download:
        print("No new files to download. Your local dataset is up to date.")
        return
    
    print(f"{len(files_to_download)} new files to download.")

    # Prepare arguments for parallel download
    download_args = [
        (SAS_URL, OUTPUT_DIR, blob) for blob in files_to_download
    ]

    # Use ThreadPoolExecutor for parallel downloads
    max_workers = min(32, (os.cpu_count() or 1) * 4, len(files_to_download))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_blob = {
            executor.submit(download_single_file, args): args[2].name
            for args in download_args
        }

        with tqdm(total=len(files_to_download), desc="Downloading files") as pbar:
            for future in as_completed(future_to_blob):
                try:
                    future.result()
                    pbar.update(1)
                except Exception as e:
                    blob_name = future_to_blob[future]
                    pbar.set_description(f"Error on {os.path.basename(blob_name)}")
                    print(f"\nError downloading {blob_name}: {str(e)}")

    print(f"\nSuccessfully downloaded {len(files_to_download)} new files.")


def main():
    parser = argparse.ArgumentParser(description="Download new parquet files from Azure using a SAS token.")
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="Number of months of data to download (default: 3). More months = more data.",
    )
    args = parser.parse_args()

    download_new_parquet_files(args.months)


if __name__ == "__main__":
    main()