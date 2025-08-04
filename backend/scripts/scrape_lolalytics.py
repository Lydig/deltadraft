import asyncio
import httpx
import json
import os
import re
from datetime import datetime
import itertools
from tqdm.asyncio import tqdm_asyncio
from collections import defaultdict

# --- Constants ---
DDRAGON_BASE_URL = "https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/"
DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
LOLALYTICS_BUILD_PAGE_URL = "https://lolalytics.com/lol/{champion_name}/build/"
LOLALYTICS_TEAM_SYNERGY_API_URL = "https://a1.lolalytics.com/mega/"

BASE_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

TIME_PERIODS = ["30", "patch"] 
RANKS = [
    "all", "iron", "bronze", "silver", "gold", "platinum", "emerald", "diamond",
    "master", "grandmaster", "challenger", "gold_plus", "platinum_plus", 
    "emerald_plus", "diamond_plus", "d2_plus", "master_plus", "grandmaster_plus", "1trick"
]
REGION_TO_SCRAPE = "all"

ROLES = ["top", "jungle", "middle", "bottom", "support"]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
}

# --- Utility Functions ---
def to_base36(n):
    if not isinstance(n, int) or n < 0: return '0'
    if n == 0: return '0'
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = ""
    while n > 0:
        n, rem = divmod(n, 36)
        result = chars[rem] + result
    return result

async def get_latest_patch():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(DDRAGON_VERSIONS_URL, headers=HEADERS)
            response.raise_for_status()
            return response.json()[0]
        except Exception as e:
            print(f"An error occurred fetching the latest patch: {e}")
            return None

async def get_champion_list(patch):
    url = f"{DDRAGON_BASE_URL.format(patch=patch)}champion.json"
    async with httpx.AsyncClient() as client:
        try:
            print("Fetching champion list...")
            response = await client.get(url, headers=HEADERS)
            response.raise_for_status()
            data = response.json()['data']
            
            name_to_id = {champ['id']: champ['key'] for champ in data.values()}
            id_to_name = {champ['key']: champ['id'] for champ in data.values()}
            
            if not os.path.exists(BASE_OUTPUT_DIR): os.makedirs(BASE_OUTPUT_DIR)
            mapping_file_path = os.path.join(BASE_OUTPUT_DIR, 'champion_mapping.json')
            with open(mapping_file_path, 'w') as f:
                json.dump(id_to_name, f, indent=4)
            print(f"✅ Saved champion_mapping.json")
            
            return name_to_id, id_to_name
        except Exception as e:
            print(f"An error occurred fetching the champion list: {e}")
            return None, None

def parse_qwik_json(text: str):
    match = re.search(r'<script\s+type="qwik/json"[^>]*>([\s\S]*?)<\/script>', text)
    if not match: return None
    
    try:
        json_data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
        
    objs = json_data.get('objs', [])
    if not objs: return None
    
    def get_obj_by_id(obj_id):
        if isinstance(obj_id, str):
            try:
                index = int(obj_id, 36)
                if 0 <= index < len(objs): return objs[index]
            except (ValueError, TypeError): pass
        return obj_id

    def reconstruct(obj_id):
        obj = get_obj_by_id(obj_id)
        if isinstance(obj, dict):
            return {key: reconstruct(value) for key, value in obj.items()}
        if isinstance(obj, list):
            return [reconstruct(item) for item in obj]
        return obj

    main_data_id = None
    for i, obj in enumerate(objs):
        if isinstance(obj, dict) and 'analysed' in obj and 'enemy' in obj:
            main_data_id = to_base36(i)
            break
            
    if main_data_id is None: return None

    return reconstruct(main_data_id)


async def fetch_champion_data(session, patch_version, time_period, rank, region, champion_name, role, semaphore):
    async with semaphore:
        champion_name_url = champion_name.lower().replace("'", "").replace(" ", "")
        if champion_name_url == "monkeyking": champion_name_url = "wukong"

        patch_param = patch_version if time_period == 'patch' else time_period

        enemy_data = None
        build_params = {'tier': rank, 'patch': patch_param, 'lane': role, 'region': region}
        build_url = LOLALYTICS_BUILD_PAGE_URL.format(champion_name=champion_name_url)
        try:
            await asyncio.sleep(0.05)
            response = await session.get(build_url, params=build_params, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                enemy_data = parse_qwik_json(response.text)
        except Exception:
            pass

        if not enemy_data:
            return None

        team_data = None
        team_params = {'ep': 'build-team', 'v': '1', 'patch': patch_param, 'c': champion_name_url, 'lane': role, 'tier': rank, 'queue': 'ranked', 'region': region}
        try:
            await asyncio.sleep(0.05)
            response = await session.get(LOLALYTICS_TEAM_SYNERGY_API_URL, params=team_params, headers=HEADERS, timeout=30)
            if response.status_code == 200: team_data = response.json()
        except Exception:
            pass

        return {"champion_name": champion_name, "role": role.upper(), "enemy_data": enemy_data, "team_data": team_data}

def process_and_save_dataset(results, id_to_name_map, time_period, rank, region):
    time_period_dir = f"days_{time_period}" if time_period.isdigit() else time_period
    output_dir = os.path.join(BASE_OUTPUT_DIR, time_period_dir, rank, region)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # --- MODIFIED: Major logic change to calculate role frequency ---
    
    # 1. Group all scraped data by champion
    champion_roles_data = defaultdict(list)
    matchup_stats = {}

    for result in results:
        if not result or not result.get('enemy_data') or not isinstance(result['enemy_data'], dict): continue

        p1_name = result['champion_name']
        p1_role = result['role']
        enemy_data = result['enemy_data']
        team_data = result.get('team_data')

        win_rate = enemy_data.get('header', {}).get('wr', 0) / 100
        pick_rate = enemy_data.get('header', {}).get('pr', 0) / 100
        
        champion_roles_data[p1_name].append({
            "role": p1_role,
            "win_rate": win_rate,
            "pick_rate": pick_rate
        })

        # Matchup data processing remains the same
        enemy_matchups = enemy_data.get('enemy', {})
        for p2_role_str, matchups in enemy_matchups.items():
            if not isinstance(matchups, list): continue
            for matchup in matchups:
                if not isinstance(matchup, list) or len(matchup) < 6: continue
                p2_key, wr, _, _, _, n_games = matchup
                p2_name = id_to_name_map.get(str(p2_key))
                if not p2_name: continue
                
                key_tuple = (p1_name, p1_role, p2_name, p2_role_str.upper(), 'enemy')
                matchup_stats[str(key_tuple)] = {"win_rate": wr / 100, "total_games": n_games}

        if team_data and 'team' in team_data:
            synergies = team_data.get('team', {})
            for p2_role_str, matchups in synergies.items():
                if not isinstance(matchups, list): continue
                for matchup in matchups:
                    if not isinstance(matchup, list) or len(matchup) < 6: continue
                    p2_key, wr, _, _, _, n_games = matchup
                    p2_name = id_to_name_map.get(str(p2_key))
                    if not p2_name: continue
                    
                    key_tuple = (p1_name, p1_role, p2_name, p2_role_str.upper(), 'teammate')
                    matchup_stats[str(key_tuple)] = {"win_rate": wr / 100, "total_games": n_games}

    # 2. Calculate role frequency and build the final list
    final_champion_stats = []
    for champion, roles in champion_roles_data.items():
        total_pick_rate = sum(role_data['pick_rate'] for role_data in roles)
        
        for role_data in roles:
            role_frequency = (role_data['pick_rate'] / total_pick_rate) if total_pick_rate > 0 else 0
            final_champion_stats.append({
                "champion": champion,
                "role": role_data['role'],
                "win_rate": role_data['win_rate'],
                "pick_rate": role_data['pick_rate'],
                "role_frequency": role_frequency
            })

    # 3. Save the new consolidated files
    with open(os.path.join(output_dir, 'champion_stats.json'), 'w') as f: json.dump(final_champion_stats, f, indent=4)
    with open(os.path.join(output_dir, 'matchup_winrates.json'), 'w') as f: json.dump(matchup_stats, f, indent=4)

    return len(final_champion_stats)

async def main():
    start_time = datetime.now()
    print(f"Starting LoLalytics data scraper at {start_time.strftime('%Y-%m-%d %H:%M:%S')}...")
    
    latest_patch_full = await get_latest_patch()
    if not latest_patch_full:
        print("Could not retrieve latest patch. Exiting.")
        return
    
    patch_parts = latest_patch_full.split('.')
    latest_patch_api = f"{patch_parts[0]}.{patch_parts[1]}"
    print(f"Latest patch found: {latest_patch_full} (Using {latest_patch_api} for API)")

    name_to_id_map, id_to_name_map = await get_champion_list(latest_patch_full)
    if not name_to_id_map:
        print("Could not retrieve champion list. Exiting.")
        return

    champions_to_scrape = list(name_to_id_map.keys())
    
    filter_combinations = list(itertools.product(TIME_PERIODS, RANKS))
    
    for time_period, rank in filter_combinations:
        print(f"\n--- Scraping for: Time={time_period}, Rank={rank}, Region={REGION_TO_SCRAPE} ---")
        
        scrape_combinations = list(itertools.product(champions_to_scrape, ROLES))
        
        semaphore = asyncio.Semaphore(20)
        tasks = []
        async with httpx.AsyncClient() as session:
            for champion_name, role in scrape_combinations:
                task = fetch_champion_data(session, latest_patch_api, time_period, rank, REGION_TO_SCRAPE, champion_name, role, semaphore)
                tasks.append(task)
            
            results = await tqdm_asyncio.gather(*tasks, desc=f"Fetching {time_period}/{rank}")

        valid_results = [r for r in results if r is not None]
        print(f"Successfully fetched data for {len(valid_results)} of {len(scrape_combinations)} combinations.")

        if not valid_results:
            print("No data fetched for this combination, skipping.")
            continue

        num_roles = process_and_save_dataset(valid_results, id_to_name_map, time_period, rank, REGION_TO_SCRAPE)
        print(f"✅ Saved dataset for {time_period}/{rank}/{REGION_TO_SCRAPE} with {num_roles} valid roles.")

    end_time = datetime.now()
    print(f"\n✨ Full scraping complete. Total time: {end_time - start_time}")


if __name__ == "__main__":
    asyncio.run(main())