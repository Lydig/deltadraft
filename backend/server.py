# backend/server.py (v7 - Reverted to file-based)
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

        for team_member, relationship in [(enemy_team, 'enemy'), (my_team, 'teammate')]:
            for role, champ in team_member.items():
                if champ and (champ, role) in valid_roles_set:
                    matchup_key = (pick_champ, target_role, champ, role, relationship)
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

    for team_member, relationship in [(enemy_team, 'enemy'), (my_team, 'teammate')]:
        for role, champ in team_member.items():
            if relationship == 'teammate' and champ == pick_champ:
                continue
            if champ and (champ, role) in valid_roles_set:
                matchup_key = (pick_champ, pick_role, champ, role, relationship)
                stats = matchup_stats.get(matchup_key)
                delta = (stats['win_rate'] - base_wr) if stats else 0
                games = stats['total_games'] if stats else 0
                total_delta += delta
                delta_breakdown.append({"source": champ, "delta": delta, "games": games})

    return {
        "champion": pick_champ, "role": pick_role, "total_delta": total_delta,
        "base_win_rate": base_wr, "pick_rate": pick_rates.get(pick_combo, 0),
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

    blue_total_delta = sum(p['total_delta'] for p in blue_picks_analysis)
    red_total_delta = sum(p['total_delta'] for p in red_picks_analysis)

    return jsonify({
        "blue": {"picks": blue_picks_analysis, "total_delta": blue_total_delta},
        "red": {"picks": red_picks_analysis, "total_delta": red_total_delta}
    })

@app.route('/ban_recommendations', methods=['POST'])
def ban_recommendations():
    data = request.get_json()
    my_role = data.get('my_role')
    my_picks = data.get('my_picks', [])
    current_allies = data.get('current_allies', {})
    consider_teammates = data.get('consider_teammates', False)

    ban_scores = {}

    for ban_candidate in valid_roles_list:
        ban_champ = ban_candidate['champion']
        ban_role = ban_candidate['role']
        
        if ban_champ in my_picks: continue

        if ban_champ not in ban_scores:
            ban_scores[ban_champ] = {"score": 0, "breakdown": {}}

        for my_pick_champ in my_picks:
            my_pick_combo = (my_pick_champ, my_role)
            if my_pick_combo not in base_winrates: continue
            my_base_wr = base_winrates[my_pick_combo]

            enemy_key = (my_pick_champ, my_role, ban_champ, ban_role, 'enemy')
            enemy_stats = matchup_stats.get(enemy_key)
            if enemy_stats:
                delta = enemy_stats['win_rate'] - my_base_wr
                if delta < 0:
                    if my_pick_champ not in ban_scores[ban_champ]["breakdown"]:
                        ban_scores[ban_champ]["breakdown"][my_pick_champ] = 0
                    ban_scores[ban_champ]["breakdown"][my_pick_champ] += delta
                    ban_scores[ban_champ]["score"] += delta

            ally_key = (my_pick_champ, my_role, ban_champ, ban_role, 'teammate')
            ally_stats = matchup_stats.get(ally_key)
            if ally_stats:
                delta = ally_stats['win_rate'] - my_base_wr
                if delta < 0:
                    if my_pick_champ not in ban_scores[ban_champ]["breakdown"]:
                        ban_scores[ban_champ]["breakdown"][my_pick_champ] = 0
                    ban_scores[ban_champ]["breakdown"][my_pick_champ] += delta
                    ban_scores[ban_champ]["score"] += delta

        if consider_teammates:
            for ally_role, ally_champ in current_allies.items():
                if not ally_champ: continue
                ally_combo = (ally_champ, ally_role)
                if ally_combo not in base_winrates: continue
                ally_base_wr = base_winrates[ally_combo]

                enemy_key_for_ally = (ally_champ, ally_role, ban_champ, ban_role, 'enemy')
                enemy_stats_for_ally = matchup_stats.get(enemy_key_for_ally)
                if enemy_stats_for_ally:
                    delta = enemy_stats_for_ally['win_rate'] - ally_base_wr
                    if delta < 0:
                        if ally_champ not in ban_scores[ban_champ]["breakdown"]:
                            ban_scores[ban_champ]["breakdown"][ally_champ] = 0
                        ban_scores[ban_champ]["breakdown"][ally_champ] += delta
                        ban_scores[ban_champ]["score"] += delta

    final_bans = []
    for champ, data in ban_scores.items():
        if data["score"] < 0:
            sorted_breakdown = sorted(data["breakdown"].items(), key=lambda item: item[1])
            final_bans.append({
                "champion": champ,
                "score": data["score"],
                "breakdown": [{"source": src, "detriment": val} for src, val in sorted_breakdown]
            })

    final_bans.sort(key=lambda item: item["score"])
    
    return jsonify(final_bans)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)