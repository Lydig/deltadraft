# create_champion_mapping.py
import requests
import json
import os

# --- Configuration ---
# The final, local filename for our mapping. It will be saved in the main project directory.
OUTPUT_FILE = "champion_mapping.json"
# ---

def create_mapping_file():
    """
    Fetches the official champion data, applies our manual patches,
    and saves the result to a local JSON file.
    """
    # 1. Fetch the official data from Riot
    try:
        print("Fetching latest champion data from Riot's Data Dragon...")
        ddragon_url = "https://ddragon.leagueoflegends.com/cdn/14.13.1/data/en_US/champion.json"
        response = requests.get(ddragon_url)
        response.raise_for_status()
        champion_data = response.json()['data']
        print("Official data fetched successfully.")
    except requests.exceptions.RequestException as e:
        print(f"FATAL: Could not fetch champion data from Riot. Cannot create mapping. Error: {e}")
        return

    # 2. Create the base id -> name mapping
    # We will store the IDs as strings, as this is standard practice for JSON keys.
    id_to_name = {details['key']: name for name, details in champion_data.items()}
    
    # 3. Apply our manual patches for the special IDs found in our dataset
    print("Applying manual patches for Ambessa, Mel, and Aurora...")
    id_to_name['799'] = 'Ambessa'
    id_to_name['800'] = 'Mel'
    id_to_name['893'] = 'Aurora'
    
    # 4. Save the final dictionary to a JSON file
    script_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(script_dir, '..'))
    output_path = os.path.join(base_dir, OUTPUT_FILE)
    
    print(f"Saving final mapping to: {output_path}")
    with open(output_path, 'w') as f:
        # indent=4 makes the JSON file nicely formatted and human-readable
        json.dump(id_to_name, f, indent=4)
        
    print("\n✅ Success! The 'champion_mapping.json' file has been created.")
    print(f"It contains {len(id_to_name)} total champion mappings.")


if __name__ == "__main__":
    create_mapping_file()