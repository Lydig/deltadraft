from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import ast
import threading
import math
import boto3

app = Flask(__name__)
CORS(app)

# --- Elo-based Rating Conversion Functions ---
def winrate_to_rating(wr):
    if wr <= 0.0 or wr >= 1.0:
        wr = max(0.0001, min(0.9999, wr))
    return -400 * math.log10(1 / wr - 1)

def rating_to_winrate(rating_diff):
    return 1 / (1 + 10**(-rating_diff / 400))

# --- Caching and R2 Data Loading ---
CLOUDFLARE_ACCOUNT_ID = os.environ.get('CLOUDFLARE_ACCOUNT_ID')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = "deltadraft-data"

s3_client = None
if all([CLOUDFLARE_ACCOUNT_ID, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY]):
    s3_client = boto3.client(
        's3',
        endpoint_url=f'https://{CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name='auto',
    )
    print("✅ S3 client initialized for R2.")
else:
    print("⚠️  Missing R2 environment variables. Server will not be able to fetch data.")

data_cache = {}
cache_lock = threading.Lock()

def get_data_from_r2(time_period, rank):
    time_period_dir = f"days_{time_period}" if time_period.isdigit() else time_period
    region = 'all'
    cache_key = (time_period, rank, region)
    
    if cache_key in data_cache:
        return data_cache[cache_key]

    with cache_lock:
        if cache_key in data_cache:
            return data_cache[cache_key]

        if not s3_client:
            print("❌ S3 client not available. Cannot fetch data.")
            return None

        print(f"Cache miss for {cache_key}. Fetching from R2...")
        
        try:
            stats_key = f"{time_period_dir}/{rank}/{region}/champion_stats.json"
            stats_obj = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=stats_key)
            champion_stats_list = json.loads(stats_obj['Body'].read().decode('utf-8'))

            matchups_key = f"{time_period_dir}/{rank}/{region}/matchup_winrates.json"
            matchups_obj = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=matchups_key)
            # --- FIX: Corrected typo from utf--8 to utf-8 ---
            matchup_data_raw = json.loads(matchups_obj['Body'].read().decode('utf-8'))

        except Exception as e:
            print(f"⚠️  Failed to fetch data from R2 for {cache_key}: {e}")
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

# --- Core Logic Functions ---
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
            total_delta = 0.0
            for team_member, relationship in [(enemy_team, 'enemy'), (my_team, 'teammate')]:
                for role, champ in team_member.items():
                    if champ:
                        matchup_key = (pick_champ, target_role, champ, role, relationship)
                        stats = matchup_stats.get(matchup_key)
                        delta = (stats['win_rate'] - base_wr) if stats else 0
                        total_delta += delta
            expected_wr = base_wr + total_delta
        else:
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
                                    expected_wr_calc = rating_to_winrate(pick_rating + partner_rating)
                                else: # enemy
                                    expected_wr_calc = rating_to_winrate(pick_rating - partner_rating)
                                
                                actual_wr = matchup_data['win_rate']
                                performance_delta = actual_wr - expected_wr_calc
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

def get_champion_analysis(pick_champ, pick_role, my_team, enemy_team, dataset, assume_balanced):
    champion_ratings = dataset['champion_ratings']
    matchup_stats = dataset['matchup_stats']
    
    pick_combo = (pick_champ, pick_role)
    if pick_combo not in champion_ratings:
        return None

    base_wr = champion_ratings[pick_combo]['win_rate']
    total_delta = 0.0

    for team_member, relationship in [(enemy_team, 'enemy'), (my_team, 'teammate')]:
        for role, champ in team_member.items():
            if relationship == 'teammate' and champ == pick_champ: continue
            if champ:
                matchup_key = (pick_champ, pick_role, champ, role, relationship)
                stats = matchup_stats.get(matchup_key)
                delta = (stats['win_rate'] - base_wr) if stats else 0
                total_delta += delta

    return {
        "champion": pick_champ, "role": pick_role, "total_delta": total_delta,
        "base_win_rate": base_wr,
        "pick_rate": champion_ratings[pick_combo]['pick_rate'],
    }

# --- API Endpoints ---
@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"}), 200

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    time_period = data.get('time_period', 'patch')
    rank = data.get('rank', 'platinum_plus')
    assume_balanced = data.get('assume_balanced', False)
    
    dataset = get_data_from_r2(time_period, rank)
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
    
    dataset = get_data_from_r2(time_period, rank)
    if not dataset:
        return jsonify({"error": f"No data available for {time_period}/{rank}"}), 404
        
    return jsonify(dataset['champion_stats_list'])

@app.route('/analyze_draft', methods=['POST'])
def analyze_draft():
    data = request.get_json()
    time_period = data.get('time_period', 'patch')
    rank = data.get('rank', 'platinum_plus')
    assume_balanced = data.get('assume_balanced', False)
    
    dataset = get_data_from_r2(time_period, rank)
    if not dataset:
        return jsonify({"error": f"No data available for {time_period}/{rank}"}), 404

    blue_team = data.get('blue_team', {})
    red_team = data.get('red_team', {})
    
    blue_picks_analysis = []
    red_picks_analysis = []

    for role, champ in blue_team.items():
        if champ:
            analysis = get_champion_analysis(champ, role, blue_team, red_team, dataset, assume_balanced)
            if analysis: blue_picks_analysis.append(analysis)
    
    for role, champ in red_team.items():
        if champ:
            analysis = get_champion_analysis(champ, role, red_team, blue_team, dataset, assume_balanced)
            if analysis: red_picks_analysis.append(analysis)

    blue_total_delta = sum(p['total_delta'] for p in blue_picks_analysis)
    red_total_delta = sum(p['total_delta'] for p in red_picks_analysis)

    return jsonify({
        "blue": {"picks": blue_picks_analysis, "total_delta": blue_total_delta},
        "red": {"picks": red_picks_analysis, "total_delta": red_total_delta}
    })

# Note: Ban recommender is omitted as it was not part of the final feature set.
# Adding it back would require implementing its logic with the new data structures.

# This is required for Vercel to treat this file as the entry point
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)