import asyncio
import httpx
import json
import os
import re
from datetime import datetime
import itertools
from tqdm.asyncio import tqdm_asyncio

# --- Constants ---
DDRAGON_BASE_URL = "https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/"
DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
LOLALYTICS_BUILD_PAGE_URL = "https://lolalytics.com/lol/{champion_name}/build/"
LOLALYTICS_TEAM_SYNERGY_API_URL = "https://a1.lolalytics.com/mega/"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
TIER = "platinum_plus"
ROLES = ["top", "jungle", "middle", "bottom", "support"]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
}

# --- Utility Functions ---
def to_base36(n):
    """Converts an integer to its base-36 string representation."""
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
            
            if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
            mapping_file_path = os.path.join(OUTPUT_DIR, 'champion_mapping.json')
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


async def fetch_champion_data(session, patch, champion_name, champion_key, role, semaphore):
    async with semaphore:
        champion_name_url = champion_name.lower().replace("'", "").replace(" ", "")
        if champion_name_url == "monkeyking": champion_name_url = "wukong"

        enemy_data = None
        build_params = {'tier': TIER, 'patch': patch, 'lane': role, 'region': 'all'}
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
        team_params = {'ep': 'build-team', 'v': '1', 'patch': patch, 'c': champion_name_url, 'lane': role, 'tier': TIER, 'queue': 'ranked', 'region': 'all'}
        try:
            await asyncio.sleep(0.05)
            response = await session.get(LOLALYTICS_TEAM_SYNERGY_API_URL, params=team_params, headers=HEADERS, timeout=30)
            if response.status_code == 200: team_data = response.json()
        except Exception:
            pass

        return {"champion_name": champion_name, "champion_key": champion_key, "role": role.upper(), "enemy_data": enemy_data, "team_data": team_data}


def process_scraped_data(results, id_to_name_map):
    print("\nProcessing all scraped data...")
    base_winrates = []
    valid_champion_roles = []
    matchup_stats = {}

    for result in results:
        if not result or not result.get('enemy_data') or not isinstance(result['enemy_data'], dict): continue

        p1_name = result['champion_name']
        p1_role = result['role']
        enemy_data = result['enemy_data']
        team_data = result.get('team_data')

        header = enemy_data.get('header', {})
        games = header.get('n', 0)
        
        if games < 100: continue

        win_rate = header.get('wr', 0) / 100
        pick_rate = header.get('pr', 0) / 100
        
        base_winrates.append({"champion": p1_name, "role": p1_role, "win_rate": win_rate})
        valid_champion_roles.append({"champion": p1_name, "role": p1_role, "pick_rate": pick_rate})

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

    print(f"Processed {len(base_winrates)} valid champion-role combinations.")
    print(f"Processed {len(matchup_stats)} matchup entries.")
    return base_winrates, valid_champion_roles, matchup_stats

def save_data_files(base_wr, valid_roles, matchup_data):
    print("\nSaving final data files...")
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    
    with open(os.path.join(OUTPUT_DIR, 'base_winrates.json'), 'w') as f:
        json.dump(base_wr, f, indent=4)
    print("✅ Saved base_winrates.json")

    with open(os.path.join(OUTPUT_DIR, 'valid_champion_roles.json'), 'w') as f:
        json.dump(valid_roles, f, indent=4)
    print("✅ Saved valid_champion_roles.json")

    with open(os.path.join(OUTPUT_DIR, 'matchup_winrates.json'), 'w') as f:
        json.dump(matchup_data, f, indent=4)
    print("✅ Saved matchup_winrates.json")


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
    scrape_combinations = list(itertools.product(champions_to_scrape, ROLES))
    total_requests = len(scrape_combinations)
    print(f"Preparing to scrape {total_requests} champion-role combinations...")

    semaphore = asyncio.Semaphore(20)
    tasks = []
    async with httpx.AsyncClient() as session:
        for champion_name, role in scrape_combinations:
            champion_key = name_to_id_map[champion_name]
            task = fetch_champion_data(session, latest_patch_api, champion_name, champion_key, role, semaphore)
            tasks.append(task)
        
        results = await tqdm_asyncio.gather(*tasks, desc="Fetching data from LoLalytics")

    valid_results = [r for r in results if r is not None]
    print(f"\nSuccessfully fetched data for {len(valid_results)} of {total_requests} combinations.")

    if not valid_results:
        print("\nNo data was fetched. Cannot process or save files.")
        return

    base_rates, valid_roles, matchup_data = process_scraped_data(valid_results, id_to_name_map)
    save_data_files(base_rates, valid_roles, matchup_data)
    
    end_time = datetime.now()
    print(f"\n✨ Scraping complete. Total time: {end_time - start_time}")


if __name__ == "__main__":
    asyncio.run(main())