from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import ast
import threading
import math

app = Flask(__name__)
CORS(app)

# --- Elo-based Rating Conversion Functions (for the new method) ---
def winrate_to_rating(wr):
    if wr <= 0.0 or wr >= 1.0:
        wr = max(0.0001, min(0.9999, wr))
    return -400 * math.log10(1 / wr - 1)

def rating_to_winrate(rating_diff):
    return 1 / (1 + 10**(-rating_diff / 400))

# --- Caching and Data Loading ---
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
            return None

        try:
            with open(os.path.join(data_path, "champion_stats.json"), 'r') as f:
                champion_stats_list = json.load(f)
            with open(os.path.join(data_path, "matchup_winrates.json"), 'r') as f:
                matchup_data_raw = json.load(f)
        except FileNotFoundError:
            return None

        champion_ratings = {}
        for item in champion_stats_list:
            combo = (item['champion'], item['role'].upper())
            champion_ratings[combo] = {
                "rating": winrate_to_rating(item['win_rate']),
                "win_rate": item['win_rate'],
                "pick_rate": item['pick_rate'],
                "role_frequency": item['role_frequency']
            }
        
        matchup_stats = {ast.literal_eval(k): v for k, v in matchup_data_raw.items()}

        dataset = {
            "champion_stats_list": champion_stats_list,
            "champion_ratings": champion_ratings,
            "matchup_stats": matchup_stats
        }
        
        data_cache[cache_key] = dataset
        print(f"✅ Successfully loaded and cached data for {cache_key}.")
        return dataset

# --- Recommendation Logic ---
def get_recommendations(my_team, enemy_team, target_role, dataset, sort_by, assume_balanced):
    recommendations = []
    champion_stats_list = dataset['champion_stats_list']
    champion_ratings = dataset['champion_ratings']
    matchup_stats = dataset['matchup_stats']

    champions_to_consider = [item['champion'] for item in champion_stats_list if item['role'].upper() == target_role]
    
    for pick_champ in champions_to_consider:
        pick_combo = (pick_champ, target_role)
        if pick_combo not in champion_ratings: continue

        base_wr = champion_ratings[pick_combo]['win_rate']
        
        if assume_balanced:
            # --- METHOD 1: "Simple Bonus" (Your original, trusted method) ---
            total_delta = 0.0
            for team_member, relationship in [(enemy_team, 'enemy'), (my_team, 'teammate')]:
                for role, champ in team_member.items():
                    if champ:
                        matchup_key = (pick_champ, target_role, champ, role, relationship)
                        stats = matchup_stats.get(matchup_key)
                        # The delta is the raw performance boost, ignoring base win rates
                        delta = (stats['win_rate'] - base_wr) if stats else 0
                        total_delta += delta
            
            expected_wr = base_wr + total_delta

        else:
            # --- METHOD 2: "Performance Review" (New Elo-based method) ---
            total_rating = champion_ratings[pick_combo]['rating']
            
            for team_member, relationship in [(my_team, 'teammate'), (enemy_team, 'enemy')]:
                for role, champ in team_member.items():
                    if champ:
                        partner_combo = (champ, role)
                        if partner_combo in champion_ratings:
                            matchup_key = (pick_champ, target_role, champ, role, relationship)
                            matchup_data = matchup_stats.get(matchup_key)
                            if matchup_data:
                                pick_rating = champion_ratings[pick_combo]['rating']
                                partner_rating = champion_ratings[partner_combo]['rating']
                                
                                if relationship == 'teammate':
                                    expected_wr = rating_to_winrate(pick_rating + partner_rating)
                                else: # enemy
                                    expected_wr = rating_to_winrate(pick_rating - partner_rating)
                                
                                actual_wr = matchup_data['win_rate']
                                performance_delta = actual_wr - expected_wr
                                rating_adjustment = winrate_to_rating(0.5 + performance_delta)
                                total_rating += rating_adjustment

            expected_wr = rating_to_winrate(total_rating)

        recommendations.append({
            "champion": pick_champ,
            "expected_win_rate": expected_wr,
            "base_win_rate": base_wr,
            "pick_rate": champion_ratings[pick_combo]['pick_rate'],
            "role_frequency": champion_ratings[pick_combo]['role_frequency'],
        })
        
    recommendations.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
    return recommendations

# --- API Endpoints ---
@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"}), 200

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    time_period = data.get('time_period', 'patch')
    rank = data.get('rank', 'platinum_plus')
    assume_balanced = data.get('assume_balanced', False) # New parameter
    
    dataset = get_data_for_filters(time_period, rank)
    if not dataset:
        return jsonify({"error": f"No data available for {time_period}/{rank}"}), 404

    sort_by = data.get('sort_by', 'expected_win_rate')
    recommendations = get_recommendations(data['my_team'], data['enemy_team'], data['target_role'], dataset, sort_by, assume_balanced)
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)