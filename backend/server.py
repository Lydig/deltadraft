from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import ast
import threading
import boto3

app = Flask(__name__)
CORS(app)

# --- NEW: Production R2 Data Fetching ---
# Read credentials securely from environment variables
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
            matchup_data_raw = json.loads(matchups_obj['Body'].read().decode('utf--8'))

        except Exception as e:
            print(f"⚠️  Failed to fetch data from R2 for {cache_key}: {e}")
            return None

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
            "champion_stats_list": champion_stats_list,
            "valid_roles_set": valid_roles_set,
            "base_winrates": base_winrates,
            "pick_rates": pick_rates,
            "role_frequencies": role_frequencies,
            "matchup_stats": matchup_stats
        }
        
        data_cache[cache_key] = dataset
        print(f"✅ Successfully loaded and cached data for {cache_key}.")
        return dataset

# The rest of the server logic remains the same, but calls get_data_from_r2

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"}), 200

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    time_period = data.get('time_period', 'patch')
    rank = data.get('rank', 'platinum_plus')
    
    dataset = get_data_from_r2(time_period, rank)
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
    
    dataset = get_data_from_r2(time_period, rank)
    if not dataset:
        return jsonify({"error": f"No data available for {time_period}/{rank}"}), 404
        
    return jsonify(dataset['champion_stats_list'])

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
                    games = stats.get('total_games', 0) if stats else 0
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