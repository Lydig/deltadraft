# backend/server.py (v3 - With game counts in breakdown)
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import ast

app = Flask(__name__)
CORS(app)

print("Loading all data files into server memory...")
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
BASE_WR_FILE = os.path.join(DATA_DIR, "base_winrates.json")
MATCHUP_WR_FILE = os.path.join(DATA_DIR, "matchup_winrates.json")
VALID_ROLES_FILE = os.path.join(DATA_DIR, "valid_champion_roles.json")
MAPPING_FILE = os.path.join(DATA_DIR, "champion_mapping.json")

with open(MAPPING_FILE, 'r') as f: id_to_name = json.load(f)
with open(VALID_ROLES_FILE, 'r') as f: valid_roles_list = json.load(f)
with open(BASE_WR_FILE, 'r') as f: base_rates_list = json.load(f)
with open(MATCHUP_WR_FILE, 'r') as f: matchup_data_raw = json.load(f)

valid_roles_set = {(item['champion'], item['role']) for item in valid_roles_list}
base_winrates = {(item['champion'], item['role']): item['win_rate'] for item in base_rates_list}
pick_rates = {(item['champion'], item['role']): item['pick_rate'] for item in valid_roles_list}

# --- NEW: Store the full matchup data (not just win_rate) ---
matchup_stats = {}
for str_key, values in matchup_data_raw.items():
    key = ast.literal_eval(str_key)
    p1_name = id_to_name.get(str(key[0])); p2_name = id_to_name.get(str(key[2]))
    if p1_name and p2_name:
        new_key = (p1_name, key[1], p2_name, key[3], key[4])
        matchup_stats[new_key] = values # Store the whole object {wins, total_games, win_rate}
        
print("✅ All data loaded and ready.")

def get_recommendations(my_team, enemy_team, target_role):
    recommendations = []
    champions_to_consider = [item['champion'] for item in valid_roles_list if item['role'] == target_role]
    
    for pick_champ in champions_to_consider:
        pick_combo = (pick_champ, target_role)
        if pick_combo not in base_winrates: continue
        
        base_wr = base_winrates[pick_combo]
        total_delta = 0.0
        delta_breakdown = []

        for team_member, relationship in [(enemy_team, 'enemy'), (my_team, 'teammate')]:
            for role, champ in team_member.items():
                if champ and (champ, role) in valid_roles_set:
                    matchup_key = (pick_champ, target_role, champ, role, relationship)
                    
                    # --- THE FIX ---
                    # Get the full stats object for the matchup
                    stats = matchup_stats.get(matchup_key)
                    if stats:
                        delta = stats['win_rate'] - base_wr
                        games = stats['total_games']
                    else:
                        # If no specific matchup data, delta is 0 based on 0 games
                        delta = 0
                        games = 0
                    
                    total_delta += delta
                    delta_breakdown.append({"source": champ, "delta": delta, "games": games})
        
        recommendations.append({
            "champion": pick_champ, "total_delta": total_delta,
            "base_win_rate": base_wr, "pick_rate": pick_rates.get(pick_combo, 0),
            "breakdown": sorted(delta_breakdown, key=lambda x: x['delta'], reverse=True)
        })
        
    recommendations.sort(key=lambda x: x['total_delta'], reverse=True)
    return recommendations

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    recommendations = get_recommendations(data['my_team'], data['enemy_team'], data['target_role'])
    return jsonify(recommendations)

@app.route('/role_data', methods=['GET'])
def role_data():
    try: return jsonify(valid_roles_list)
    except NameError: return jsonify({"error": "Role data not loaded"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)