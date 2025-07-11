# backend/server.py (v5 - With Total Delta in Analysis)
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

matchup_stats = {}
for str_key, values in matchup_data_raw.items():
    key = ast.literal_eval(str_key)
    p1_name = id_to_name.get(str(key[0])); p2_name = id_to_name.get(str(key[2]))
    if p1_name and p2_name:
        new_key = (p1_name, key[1], p2_name, key[3], key[4])
        matchup_stats[new_key] = values
        
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

        # Calculate delta vs enemies
        for role, champ in enemy_team.items():
            if champ and (champ, role) in valid_roles_set:
                matchup_key = (pick_champ, target_role, champ, role, 'enemy')
                stats = matchup_stats.get(matchup_key)
                delta = (stats['win_rate'] - base_wr) if stats else 0
                games = stats['total_games'] if stats else 0
                total_delta += delta
                delta_breakdown.append({"source": champ, "delta": delta, "games": games})

        # Calculate delta with teammates
        for role, champ in my_team.items():
            if champ and (champ, role) in valid_roles_set:
                matchup_key = (pick_champ, target_role, champ, role, 'teammate')
                stats = matchup_stats.get(matchup_key)
                delta = (stats['win_rate'] - base_wr) if stats else 0
                games = stats['total_games'] if stats else 0
                total_delta += delta
                delta_breakdown.append({"source": champ, "delta": delta, "games": games})
        
        recommendations.append({
            "champion": pick_champ, "total_delta": total_delta,
            "base_win_rate": base_wr, "pick_rate": pick_rates.get(pick_combo, 0),
            "breakdown": sorted(delta_breakdown, key=lambda x: x['delta'], reverse=True)
        })
        
    recommendations.sort(key=lambda x: x['total_delta'], reverse=True)
    return recommendations

def get_champion_analysis(pick_champ, pick_role, my_team, enemy_team):
    pick_combo = (pick_champ, pick_role)
    if pick_combo not in base_winrates:
        return None

    base_wr = base_winrates[pick_combo]
    total_delta = 0.0
    delta_breakdown = []

    # Calculate delta vs enemies
    for role, champ in enemy_team.items():
        if champ and (champ, role) in valid_roles_set:
            matchup_key = (pick_champ, pick_role, champ, role, 'enemy')
            stats = matchup_stats.get(matchup_key)
            delta = (stats['win_rate'] - base_wr) if stats else 0
            games = stats['total_games'] if stats else 0
            total_delta += delta
            delta_breakdown.append({"source": champ, "delta": delta, "games": games})

    # Calculate delta with teammates (excluding self)
    for role, champ in my_team.items():
        if champ and champ != pick_champ and (champ, role) in valid_roles_set:
            matchup_key = (pick_champ, pick_role, champ, role, 'teammate')
            stats = matchup_stats.get(matchup_key)
            delta = (stats['win_rate'] - base_wr) if stats else 0
            games = stats['total_games'] if stats else 0
            total_delta += delta
            delta_breakdown.append({"source": champ, "delta": delta, "games": games})

    return {
        "champion": pick_champ,
        "role": pick_role,
        "total_delta": total_delta,
        "base_win_rate": base_wr,
        "pick_rate": pick_rates.get(pick_combo, 0),
        "breakdown": sorted(delta_breakdown, key=lambda x: x['delta'], reverse=True)
    }

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    recommendations = get_recommendations(data['my_team'], data['enemy_team'], data['target_role'])
    return jsonify(recommendations)

@app.route('/role_data', methods=['GET'])
def role_data():
    try: return jsonify(valid_roles_list)
    except NameError: return jsonify({"error": "Role data not loaded"}), 500

@app.route('/analyze_draft', methods=['POST'])
def analyze_draft():
    data = request.get_json()
    blue_team = data.get('blue_team', {})
    red_team = data.get('red_team', {})
    
    blue_picks_analysis = []
    red_picks_analysis = []

    for role, champ in blue_team.items():
        if champ:
            analysis = get_champion_analysis(champ, role, blue_team, red_team)
            if analysis: blue_picks_analysis.append(analysis)
    
    for role, champ in red_team.items():
        if champ:
            analysis = get_champion_analysis(champ, role, red_team, blue_team)
            if analysis: red_picks_analysis.append(analysis)

    # --- NEW: Calculate total delta for each team ---
    blue_total_delta = sum(p['total_delta'] for p in blue_picks_analysis)
    red_total_delta = sum(p['total_delta'] for p in red_picks_analysis)

    return jsonify({
        "blue": {
            "picks": blue_picks_analysis,
            "total_delta": blue_total_delta
        },
        "red": {
            "picks": red_picks_analysis,
            "total_delta": red_total_delta
        }
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)