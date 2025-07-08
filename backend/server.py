# backend/server.py
from flask import Flask, request, jsonify
import json
import os
import ast

# --- 1. INITIALIZE THE FLASK APP ---
app = Flask(__name__)

# --- 2. LOAD ALL DATA INTO MEMORY ON STARTUP ---
print("Loading all data files into server memory...")

# Define paths relative to the script's location
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
BASE_WR_FILE = os.path.join(DATA_DIR, "base_winrates.json")
MATCHUP_WR_FILE = os.path.join(DATA_DIR, "matchup_winrates.json")
VALID_ROLES_FILE = os.path.join(DATA_DIR, "valid_champion_roles.json")
MAPPING_FILE = os.path.join(DATA_DIR, "champion_mapping.json")

# Load all the files
with open(MAPPING_FILE, 'r') as f:
    id_to_name = json.load(f)
with open(VALID_ROLES_FILE, 'r') as f:
    valid_roles_list = json.load(f)
with open(BASE_WR_FILE, 'r') as f:
    base_rates_list = json.load(f)
with open(MATCHUP_WR_FILE, 'r') as f:
    matchup_data_raw = json.load(f)

# Pre-process the data into fast lookup structures
valid_roles_set = {(item['champion'], item['role']) for item in valid_roles_list}
base_winrates = {(item['champion'], item['role']): item['win_rate'] for item in base_rates_list}
matchup_winrates = {}
for str_key, values in matchup_data_raw.items():
    key = ast.literal_eval(str_key)
    p1_name = id_to_name.get(str(key[0]))
    p2_name = id_to_name.get(str(key[2]))
    if p1_name and p2_name:
        new_key = (p1_name, key[1], p2_name, key[3], key[4])
        matchup_winrates[new_key] = values['win_rate']
        
print("✅ All data loaded and ready.")

# --- 3. DEFINE THE RECOMMENDATION LOGIC ---
def get_recommendations(my_team, enemy_team, target_role):
    # This is the exact same logic from our notebook
    recommendations = []
    champions_to_consider = [item['champion'] for item in valid_roles_list if item['role'] == target_role]
    
    for pick_champ in champions_to_consider:
        pick_combo = (pick_champ, target_role)
        if pick_combo not in base_winrates: continue
        base_wr = base_winrates[pick_combo]
        total_delta = 0.0

        for role, champ in enemy_team.items():
            if champ and (champ, role) in valid_roles_set:
                matchup_key = (pick_champ, target_role, champ, role, 'enemy')
                matchup_wr = matchup_winrates.get(matchup_key, base_wr)
                total_delta += (matchup_wr - base_wr)

        for role, champ in my_team.items():
            if champ and (champ, role) in valid_roles_set:
                matchup_key = (pick_champ, target_role, champ, role, 'teammate')
                matchup_wr = matchup_winrates.get(matchup_key, base_wr)
                total_delta += (matchup_wr - base_wr)
        
        recommendations.append({
            "champion": pick_champ, "total_delta": total_delta, "base_win_rate": base_wr
        })
        
    recommendations.sort(key=lambda x: x['total_delta'], reverse=True)
    return recommendations

# --- 4. CREATE THE API ENDPOINT ---
@app.route('/recommend', methods=['POST'])
def recommend():
    # Get the JSON data sent from the frontend
    data = request.get_json()
    
    # Call our logic function with the provided data
    recommendations = get_recommendations(
        data['my_team'],
        data['enemy_team'],
        data['target_role']
    )
    
    # Return the results as JSON
    return jsonify(recommendations)

# --- 5. RUN THE SERVER ---
if __name__ == '__main__':
    # The host='0.0.0.0' makes it accessible from your local network
    app.run(debug=True, host='0.0.0.0', port=5000)