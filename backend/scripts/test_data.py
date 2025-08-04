import json
import os
import ast

def run_test():
    """
    Loads the newly generated data and runs a single recommendation test case.
    """
    print("--- Starting Data Sanity Check ---")
    
    # --- 1. Load Data (Copied from server.py) ---
    print("Loading all new data files into memory...")
    DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
    BASE_WR_FILE = os.path.join(DATA_DIR, "base_winrates.json")
    MATCHUP_WR_FILE = os.path.join(DATA_DIR, "matchup_winrates.json")
    VALID_ROLES_FILE = os.path.join(DATA_DIR, "valid_champion_roles.json")
    MAPPING_FILE = os.path.join(DATA_DIR, "champion_mapping.json")

    try:
        with open(MAPPING_FILE, 'r') as f: id_to_name = json.load(f)
        with open(VALID_ROLES_FILE, 'r') as f: valid_roles_list = json.load(f)
        with open(BASE_WR_FILE, 'r') as f: base_rates_list = json.load(f)
        with open(MATCHUP_WR_FILE, 'r') as f: matchup_data_raw = json.load(f)
    except FileNotFoundError as e:
        print(f"❌ ERROR: Could not find a required data file: {e}. Make sure the scraper ran successfully.")
        return

    valid_roles_set = {(item['champion'], item['role']) for item in valid_roles_list}
    base_winrates = {(item['champion'], item['role']): item['win_rate'] for item in base_rates_list}
    pick_rates = {(item['champion'], item['role']): item['pick_rate'] for item in valid_roles_list}

    matchup_stats = {}
    # This logic correctly handles the string-tuple keys from our new scraper.
    for str_key, values in matchup_data_raw.items():
        # The key from our new data is already in the correct tuple format as a string
        # e.g. "('Aatrox', 'TOP', 'Jax', 'TOP', 'enemy')"
        # We use ast.literal_eval to safely convert it back to a tuple.
        key = ast.literal_eval(str_key)
        matchup_stats[key] = values
        
    print("✅ All data loaded successfully.")

    # --- 2. Define Test Case ---
    my_team = {
        'TOP': None,
        'JUNGLE': 'Hecarim',
        'MIDDLE': None,
        'BOTTOM': None,
        'UTILITY': None,
    }
    enemy_team = {
        'TOP': 'Aatrox',
        'JUNGLE': None,
        'MIDDLE': 'Ahri',
        'BOTTOM': None,
        'UTILITY': None,
    }
    target_role = 'TOP'

    print("\n--- Running Test Scenario ---")
    print(f"My Team: {my_team}")
    print(f"Enemy Team: {enemy_team}")
    print(f"Target Role: {target_role}")
    
    # --- 3. Get Recommendations (Copied from server.py) ---
    recommendations = []
    champions_to_consider = [item['champion'] for item in valid_roles_list if item['role'] == target_role]
    
    for pick_champ in champions_to_consider:
        pick_combo = (pick_champ, target_role)
        if pick_combo not in base_winrates: continue
        
        base_wr = base_winrates[pick_combo]
        total_delta = 0.0

        for team_member, relationship in [(enemy_team, 'enemy'), (my_team, 'teammate')]:
            for role, champ in team_member.items():
                if champ and (champ, role) in valid_roles_set:
                    # Reconstruct the key exactly as it is in the matchup_stats dictionary
                    matchup_key = (pick_champ, target_role, champ, role, relationship)
                    stats = matchup_stats.get(matchup_key)
                    delta = (stats['win_rate'] - base_wr) if stats else 0
                    total_delta += delta
        
        expected_wr = base_wr + total_delta
        recommendations.append({
            "champion": pick_champ, "total_delta": total_delta,
            "base_win_rate": base_wr, "expected_win_rate": expected_wr,
        })
        
    recommendations.sort(key=lambda x: x['total_delta'], reverse=True)

    # --- 4. Print Results ---
    print("\n--- Top 10 Recommendations ---")
    for i, rec in enumerate(recommendations[:10]):
        delta_str = f"{rec['total_delta']:+.2%}"
        base_wr_str = f"{rec['base_win_rate']:.2%}"
        exp_wr_str = f"{rec['expected_win_rate']:.2%}"
        print(f"{i+1:>2}. {rec['champion']:<15} | Expected WR: {exp_wr_str:<10} | Base WR: {base_wr_str:<10} | Delta: {delta_str}")

if __name__ == '__main__':
    run_test()