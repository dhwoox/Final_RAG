import json
import os
from functools import lru_cache

# Load JSON files from the same directory as this script
base_dir = os.path.dirname(os.path.abspath(__file__))
CATEGORY_MAP_PATH = os.path.join(base_dir, 'category_map.json')
API_INDEX_PATH = os.path.join(base_dir, 'manager_api_index.json')

@lru_cache(maxsize=None)
def _load_json(file_path):
    """Loads a JSON file with caching."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: JSON file not found at {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}")
        return None

def get_categories(query: str) -> str:
    """
    Identifies relevant G-SDK categories from a query and returns them as a JSON list.
    """
    category_data = _load_json(CATEGORY_MAP_PATH)
    if not category_data or 'categories' not in category_data:
        return json.dumps([])

    found_categories = set()
    lower_query = query.lower()

    for category in category_data['categories']:
        for keyword in category.get('keywords', []):
            if keyword.lower() in lower_query:
                found_categories.add(category['name'])
                break
    
    # Ensure essential categories are included for most tests
    if 'user' not in found_categories:
        found_categories.add('user')
    if 'event' not in found_categories:
        found_categories.add('event')

    return json.dumps(sorted(list(found_categories)))

def get_apis_for_categories(categories_json: str) -> str:
    """
    Gets a dictionary of relevant manager APIs for a JSON list of categories.
    """
    try:
        categories = json.loads(categories_json)
        if not isinstance(categories, list):
            return json.dumps({"error": "Input must be a JSON list of strings."})
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON format for categories."})

    api_index = _load_json(API_INDEX_PATH)
    if not api_index:
        return json.dumps({})

    # Return a dictionary mapping each category to its list of APIs
    apis_by_category = {category: [] for category in categories}
    
    for category_name in categories:
        found_apis = set()
        for api_group in api_index.values():
            for method in api_group.get('methods', []):
                if category_name in method.get('categories', []):
                    found_apis.add(method['name'])
        apis_by_category[category_name] = sorted(list(found_apis))
    
    return json.dumps(apis_by_category, indent=2)