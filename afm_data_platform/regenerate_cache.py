"""
Script to regenerate the AFM file cache with file availability information
Run this after creating dummy files to update the cache
"""

import sys
from pathlib import Path

# Add the api/utils directory to Python path
sys.path.append(str(Path(__file__).parent))

from api.utils.file_parser import parse_and_cache_afm_data

def regenerate_cache_for_all_tools():
    """Regenerate cache for all available tools"""
    tools = ['MAP608', 'MAPC01']
    
    for tool in tools:
        print(f"\n{'='*60}")
        print(f"Regenerating cache for {tool}")
        print(f"{'='*60}")
        
        # Delete existing cache file
        cache_path = Path('itc-afm-data-platform-pjt-shared') / 'AFM_DB' / tool / 'data_dir_list_parsed.pkl'
        if cache_path.exists():
            cache_path.unlink()
            print(f"Deleted old cache: {cache_path}")
        
        # Regenerate cache
        success = parse_and_cache_afm_data(tool)
        
        if success:
            print(f"Successfully regenerated cache for {tool}")
        else:
            print(f"Failed to regenerate cache for {tool}")
    
    print("\nCache regeneration complete!")


if __name__ == "__main__":
    regenerate_cache_for_all_tools()