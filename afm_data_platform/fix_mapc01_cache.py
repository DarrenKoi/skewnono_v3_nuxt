#!/usr/bin/env python3
"""
Fix MAPC01 cache file format
"""
import sys
from pathlib import Path
import pickle
from datetime import datetime

# Add api directory to path
sys.path.append('api')

def fix_mapc01_cache():
    """Fix MAPC01 cache file format"""
    try:
        print("Fixing MAPC01 cache file format...")
        
        # Import with the modified path
        from utils.file_parser import load_afm_file_list_live
        
        tool_name = 'MAPC01'
        
        # Parse the data using the live parsing function
        measurements = load_afm_file_list_live(tool_name)
        
        if not measurements:
            print(f"No measurements found for {tool_name}")
            return False
            
        print(f"Found {len(measurements)} measurements")
        
        # Prepare cache data structure with the correct format
        cache_data = {
            'measurements': measurements,
            'metadata': {
                'tool_name': tool_name,
                'total_files_processed': len(measurements),
                'generated_at': datetime.now().isoformat(),
                'includes_file_availability': True
            }
        }
        
        # Save to cache file
        cache_path = Path('itc-afm-data-platform-pjt-shared') / 'AFM_DB' / tool_name / 'data_dir_list_parsed.pkl'
        
        # Ensure directory exists
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(cache_path, 'wb') as f:
            pickle.dump(cache_data, f)
            
        print(f"Successfully cached {len(measurements)} measurements to {cache_path}")
        print(f"Cache file size: {cache_path.stat().st_size / 1024:.2f} KB")
        
        # Verify the fix
        with open(cache_path, 'rb') as f:
            verify_data = pickle.load(f)
        
        if isinstance(verify_data, dict) and 'measurements' in verify_data:
            print("Cache file format verified - it's now a dict with 'measurements' key")
            print(f"Number of measurements in cache: {len(verify_data['measurements'])}")
        else:
            print("ERROR: Cache file format is still incorrect!")
            return False
        
        return True
        
    except Exception as e:
        print(f"Error fixing MAPC01 cache: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # First, let's fix the Unicode issues in file_parser.py temporarily
    import os
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    success = fix_mapc01_cache()
    if success:
        print("\nMAPC01 cache fix completed successfully!")
        print("The frontend should now be able to load MAPC01 data.")
    else:
        print("\nMAPC01 cache fix failed!")
        sys.exit(1)