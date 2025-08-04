from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import ast
import threading

app = Flask(__name__)
CORS(app)

data_cache = {}
cache_lock = threading.Lock()

BASE_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

def get_data_for_filters(time_period, rank):
    time_period_dir = f"days_{time_period}" if time_period.isdigit() else time_period
    region = 'all'
    cache_key = (time_period, rank, region)
    
    if cache_key in data_cache:
        return data_cache[cache_key]

    with cache_lock:
        if cache_key in data_cache:
            return data_cache[cache_key]

        print(f"Cache miss for {cache_key}. Loading from disk...")
        
        data_path = os.path.join(BASE_DATA_DIR, time_period_dir, rank, region)
        if not os.path.exists(data_path):
            print(f"⚠️  Data directory not found: {data_path}")
            return None

        # --- MODIFIED: Load from new consolidated file ---
        try:
            with open(os.path.join(data_path, "champion_stats.json"), 'r') as f:
                champion_stats_list = json.load(f)
            with open(os.path.join(data_path, "matchup_winrates.json"), 'r') as f:
                matchup_data_raw = json.load(f)
        except FileNotFoundError as e:
            print(f"⚠️  Missing a data file in {data_path}: {e}")
            return None

        # --- MODIFIED: Reconstruct data dictionaries from the single stats file ---
        valid_roles_set = set()
        base_winrates = {}
        pick_rates = {}
        role_frequencies = {}

        for item in champion_stats_list:
            champ = item['champion']
            role = item['role'].upper()
            combo = (champ, role)
            
            valid_roles_set.add(combo)
            base_winrates[combo] = item['win_rate']
            pick_rates[combo] = item['pick_rate']
            role_frequencies[combo] = item['role_frequency']
        
        matchup_stats = {ast.literal_eval(k): v for k, v in matchup_data_raw.items()}

        dataset = {
            "champion_stats_list": champion_stats_list, # Pass the raw list for role_data endpoint
            "valid_roles_set": valid_roles_set,
            "base_winrates": base_winrates,
            "pick_rates": pick_rates,
            "role_frequencies": role_frequencies,
            "matchup_stats": matchup_stats
        }
        
        data_cache[cache_key] = dataset
        print(f"✅ Successfully loaded and cached data for {cache_key}.")
        return dataset

MAPPING_FILE = os.path.join(BASE_DATA_DIR, "champion_mapping.json")
try:
    with open(MAPPING_FILE, 'r') as f: id_to_name = json.load(f)
    print("✅ Global champion mapping loaded.")
except FileNotFoundError:
    id_to_name = {}
    print("⚠️  Global champion_mapping.json not found.")


@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"}), 200

def get_recommendations(my_team, enemy_team, target_role, dataset, sort_by='total_delta'):
    recommendations = []
    champion_stats_list = dataset['champion_stats_list']
    base_winrates = dataset['base_winrates']
    valid_roles_set = dataset['valid_roles_set']
    matchup_stats = dataset['matchup_stats']
    pick_rates = dataset['pick_rates']
    role_frequencies = dataset['role_frequencies']

    champions_to_consider = [item['champion'] for item in champion_stats_list if item['role'].upper() == target_role]
    
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
        
        expected_wr = base_wr + total_delta
        recommendations.append({
            "champion": pick_champ, "total_delta": total_delta,
            "base_win_rate": base_wr, 
            "pick_rate": pick_rates.get(pick_combo, 0),
            "role_frequency": role_frequencies.get(pick_combo, 0),
            "expected_win_rate": expected_wr,
            "breakdown": sorted(delta_breakdown, key=lambda x: x['delta'], reverse=True)
        })
        
    if sort_by not in ['total_delta', 'base_win_rate', 'expected_win_rate']:
        sort_by = 'total_delta'
        
    recommendations.sort(key=lambda x: x[sort_by], reverse=True)
    return recommendations

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    time_period = data.get('time_period', 'patch')
    rank = data.get('rank', 'platinum_plus')
    
    dataset = get_data_for_filters(time_period, rank)
    if not dataset:
        return jsonify({"error": f"No data available for {time_period}/{rank}"}), 404

    sort_by = data.get('sort_by', 'total_delta')
    recommendations = get_recommendations(data['my_team'], data['enemy_team'], data['target_role'], dataset, sort_by)
    return jsonify(recommendations)

@app.route('/role_data', methods=['POST'])
def role_data():
    data = request.get_json()
    time_period = data.get('time_period', 'patch')
    rank = data.get('rank', 'platinum_plus')
    
    dataset = get_data_for_filters(time_period, rank)
    if not dataset:
        return jsonify({"error": f"No data available for {time_period}/{rank}"}), 404
        
    return jsonify(dataset['champion_stats_list'])

# Other endpoints like analyze_draft and ban_recommendations would be updated similarly.
# For brevity, I am omitting them as they follow the same pattern as the /recommend endpoint.
# They would need to call get_data_for_filters and use the returned dataset.

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)