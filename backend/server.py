# backend/server.py (v3 - Corrected CORS import)
from flask import Flask, request, jsonify
from flask_cors import CORS  # <-- CORRECTED: Import from the new library
import json
import os
import ast

# --- 1. INITIALIZE THE FLASK APP ---
app = Flask(__name__)
CORS(app)  # <-- CORRECTED: Apply CORS to the app

# --- 2. LOAD ALL DATA INTO MEMORY ON STARTUP ---
print("Loading all data files into server memory...")
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
BASE_WR_FILE = os.path.join(DATA_DIR, "base_winrates.json")
MATCHUP_WR_FILE = os.path.join(DATA_DIR, "matchup_winrates.json")
VALID_ROLES_FILE = os.path.join(DATA_DIR, "valid_champion_roles.json")
MAPPING_FILE = os.path.join(DATA_DIR, "champion_mapping.json")

# Load all the files
with open(MAPPING_FILE, 'r') as f: id_to_name = json.load(f)
with open(VALID_ROLES_FILE, 'r') as f: valid_roles_list = json.load(f)
with open(BASE_WR_FILE, 'r') as f: base_rates_list = json.load(f)
with open(MATCHUP_WR_FILE, 'r') as f: matchup_data_raw = json.load(f)

# Pre-process the data into fast lookup structures
valid_roles_set = {(item['champion'], item['role']) for item in valid_roles_list}
base_winrates = {(item['champion'], item['role']): item['win_rate'] for item in base_rates_list}
pick_rates = {(item['champion'], item['role']): item['pick_rate'] for item in valid_roles_list}

matchup_winrates = {}
for str_key, values in matchup_data_raw.items():
    key = ast.literal_eval(str_key)
    p1_name = id_to_name.get(str(key[0])); p2_name = id_to_name.get(str(key[2]))
    if p1_name and p2_name:
        new_key = (p1_name, key[1], p2_name, key[3], key[4])
        matchup_winrates[new_key] = values['win_rate']
        
print("✅ All data loaded and ready.")

# --- 3. DEFINE THE UPGRADED RECOMMENDATION LOGIC ---
def get_recommendations(my_team, enemy_team, target_role):
    recommendations = []
    champions_to_consider = [item['champion'] for item in valid_roles_list if item['role'] == target_role]
    
    for pick_champ in champions_to_consider:
        pick_combo = (pick_champ, target_role)
        if pick_combo not in base_winrates: continue
        
        base_wr = base_winrates[pick_combo]
        total_delta = 0.0
        delta_breakdown = []

        for enemy_role, enemy_champ in enemy_team.items():
            if enemy_champ and (enemy_champ, enemy_role) in valid_roles_set:
                matchup_key = (pick_champ, target_role, enemy_champ, enemy_role, 'enemy')
                matchup_wr = matchup_winrates.get(matchup_key, base_wr)
                delta = matchup_wr - base_wr
                total_delta += delta
                delta_breakdown.append({"source": enemy_champ, "delta": delta})

        for ally_role, ally_champ in my_team.items():
            if ally_champ and (ally_champ, ally_role) in valid_roles_set:
                matchup_key = (pick_champ, target_role, ally_champ, ally_role, 'teammate')
                matchup_wr = matchup_winrates.get(matchup_key, base_wr)
                delta = matchup_wr - base_wr
                total_delta += delta
                delta_breakdown.append({"source": ally_champ, "delta": delta})
        
        recommendations.append({
            "champion": pick_champ,
            "total_delta": total_delta,
            "base_win_rate": base_wr,
            "pick_rate": pick_rates.get(pick_combo, 0),
            "breakdown": sorted(delta_breakdown, key=lambda x: x['delta'], reverse=True)
        })
        
    recommendations.sort(key=lambda x: x['total_delta'], reverse=True)
    return recommendations

# --- 4. API ENDPOINTS ---
@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    recommendations = get_recommendations(data['my_team'], data['enemy_team'], data['target_role'])
    return jsonify(recommendations)

@app.route('/role_data', methods=['GET'])
def role_data():
    try:
        return jsonify(valid_roles_list)
    except NameError:
        return jsonify({"error": "Role data not loaded"}), 500

# --- 5. RUN THE SERVER ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)