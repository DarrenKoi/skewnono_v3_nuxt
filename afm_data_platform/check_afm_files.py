#!/usr/bin/env python3
"""
AFM Data File Checker and Sampler

This script checks and samples files in the AFM data directories:
- data_dir_pickle: Contains measurement data in pickle format
- profile_dir: Contains profile coordinate data (X, Y, Z) in pickle format

Usage:
    python check_afm_files.py [--sample-size N] [--verbose]
"""

import os
import pickle
import random
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any


class AFMFileChecker:
    """Check and sample AFM data files"""
    
    def __init__(self, base_path: str = None):
        """Initialize with base path to AFM data"""
        if base_path is None:
            base_path = "itc-afm-data-platform-pjt-shared/AFM_DB/MAP608"
        
        self.base_path = Path(base_path)
        self.data_dir_pickle = self.base_path / "data_dir_pickle"
        self.profile_dir = self.base_path / "profile_dir"
        
        # Statistics
        self.stats = {
            'data_files': {'total': 0, 'valid': 0, 'errors': []},
            'profile_files': {'total': 0, 'valid': 0, 'errors': []},
            'recipes': {},
            'lots': {},
            'dates': {}
        }
    
    def parse_filename(self, filename: str) -> Dict[str, str]:
        """Parse AFM filename to extract components"""
        # Example: #250609#FSOXCMP_DISHING_9PT#T7HQR42TA_250709#21_1#
        parts = filename.split('#')
        if len(parts) >= 5:
            return {
                'date': parts[1],
                'recipe': parts[2],
                'lot_id': parts[3].split('_')[0] if '_' in parts[3] else parts[3],
                'slot_info': parts[4],
                'full_name': filename
            }
        return {}
    
    def check_data_file(self, filepath: Path) -> Tuple[bool, str]:
        """Check a single data pickle file"""
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            # Validate structure
            required_keys = ['info', 'data_status', 'data_detail']
            for key in required_keys:
                if key not in data:
                    return False, f"Missing required key: {key}"
            
            # Check info structure
            info_keys = ['Lot ID', 'Recipe ID', 'Tool', 'Start Time']
            for key in info_keys:
                if key not in data['info']:
                    return False, f"Missing info key: {key}"
            
            # Count measurement points
            num_points = len(data['data_status'])
            
            return True, f"Valid with {num_points} measurement points"
            
        except Exception as e:
            return False, f"Error reading file: {str(e)}"
    
    def check_profile_file(self, filepath: Path) -> Tuple[bool, str]:
        """Check a single profile pickle file"""
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            # Validate structure
            required_keys = ['X', 'Y', 'Z']
            for key in required_keys:
                if key not in data:
                    return False, f"Missing required key: {key}"
            
            # Check data consistency
            x_len = len(data['X'])
            y_len = len(data['Y'])
            z_len = len(data['Z'])
            
            if x_len != y_len or x_len != z_len:
                return False, f"Inconsistent data lengths: X={x_len}, Y={y_len}, Z={z_len}"
            
            if x_len != 400:  # Expected 20x20 grid
                return False, f"Unexpected data size: {x_len} points (expected 400)"
            
            return True, f"Valid profile with {x_len} points"
            
        except Exception as e:
            return False, f"Error reading file: {str(e)}"
    
    def scan_directory(self, directory: Path, check_func, file_pattern: str = "*.pkl") -> Dict[str, Any]:
        """Scan a directory and check all matching files"""
        results = {'files': [], 'errors': []}
        
        if not directory.exists():
            print(f"Warning: Directory {directory} does not exist")
            return results
        
        files = list(directory.glob(file_pattern))
        print(f"\nScanning {directory.name}: Found {len(files)} files")
        
        for filepath in files:
            filename = filepath.name
            parsed = self.parse_filename(filename)
            
            is_valid, message = check_func(filepath)
            
            file_info = {
                'name': filename,
                'path': str(filepath),
                'valid': is_valid,
                'message': message,
                'parsed': parsed,
                'size': filepath.stat().st_size
            }
            
            results['files'].append(file_info)
            
            if not is_valid:
                results['errors'].append(file_info)
            
            # Update statistics
            if parsed:
                date = parsed.get('date', '')
                recipe = parsed.get('recipe', '')
                lot_id = parsed.get('lot_id', '')
                
                if date:
                    self.stats['dates'][date] = self.stats['dates'].get(date, 0) + 1
                if recipe:
                    self.stats['recipes'][recipe] = self.stats['recipes'].get(recipe, 0) + 1
                if lot_id:
                    self.stats['lots'][lot_id] = self.stats['lots'].get(lot_id, 0) + 1
        
        return results
    
    def sample_files(self, files: List[Dict], sample_size: int = 5) -> List[Dict]:
        """Randomly sample files from the list"""
        if len(files) <= sample_size:
            return files
        return random.sample(files, sample_size)
    
    def check_all(self, sample_size: int = 5, verbose: bool = False):
        """Check all directories and sample files"""
        print("=" * 80)
        print("AFM Data File Checker")
        print("=" * 80)
        print(f"Base path: {self.base_path}")
        print(f"Sample size: {sample_size}")
        
        # Check data_dir_pickle
        print("\n" + "-" * 40)
        print("Checking data_dir_pickle...")
        data_results = self.scan_directory(self.data_dir_pickle, self.check_data_file)
        self.stats['data_files']['total'] = len(data_results['files'])
        self.stats['data_files']['valid'] = sum(1 for f in data_results['files'] if f['valid'])
        self.stats['data_files']['errors'] = data_results['errors']
        
        # Check profile_dir
        print("\n" + "-" * 40)
        print("Checking profile_dir...")
        profile_results = self.scan_directory(self.profile_dir, self.check_profile_file)
        self.stats['profile_files']['total'] = len(profile_results['files'])
        self.stats['profile_files']['valid'] = sum(1 for f in profile_results['files'] if f['valid'])
        self.stats['profile_files']['errors'] = profile_results['errors']
        
        # Print summary statistics
        print("\n" + "=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)
        
        print(f"\nData Files (data_dir_pickle):")
        print(f"  Total: {self.stats['data_files']['total']}")
        print(f"  Valid: {self.stats['data_files']['valid']}")
        print(f"  Errors: {len(self.stats['data_files']['errors'])}")
        
        print(f"\nProfile Files (profile_dir):")
        print(f"  Total: {self.stats['profile_files']['total']}")
        print(f"  Valid: {self.stats['profile_files']['valid']}")
        print(f"  Errors: {len(self.stats['profile_files']['errors'])}")
        
        print(f"\nUnique Recipes: {len(self.stats['recipes'])}")
        for recipe, count in sorted(self.stats['recipes'].items())[:5]:
            print(f"  - {recipe}: {count} files")
        if len(self.stats['recipes']) > 5:
            print(f"  ... and {len(self.stats['recipes']) - 5} more")
        
        print(f"\nUnique Lots: {len(self.stats['lots'])}")
        print(f"Unique Dates: {len(self.stats['dates'])}")
        
        # Sample data files
        print("\n" + "-" * 80)
        print(f"SAMPLE DATA FILES (Random {sample_size})")
        print("-" * 80)
        
        valid_data_files = [f for f in data_results['files'] if f['valid']]
        sampled_data = self.sample_files(valid_data_files, sample_size)
        
        for i, file_info in enumerate(sampled_data, 1):
            print(f"\n{i}. {file_info['name']}")
            print(f"   Size: {file_info['size']:,} bytes")
            print(f"   {file_info['message']}")
            if verbose and file_info['parsed']:
                print(f"   Date: {file_info['parsed']['date']}")
                print(f"   Recipe: {file_info['parsed']['recipe']}")
                print(f"   Lot ID: {file_info['parsed']['lot_id']}")
                print(f"   Slot Info: {file_info['parsed']['slot_info']}")
        
        # Sample profile files
        print("\n" + "-" * 80)
        print(f"SAMPLE PROFILE FILES (Random {sample_size})")
        print("-" * 80)
        
        valid_profile_files = [f for f in profile_results['files'] if f['valid']]
        sampled_profiles = self.sample_files(valid_profile_files, sample_size)
        
        for i, file_info in enumerate(sampled_profiles, 1):
            print(f"\n{i}. {file_info['name']}")
            print(f"   Size: {file_info['size']:,} bytes")
            print(f"   {file_info['message']}")
        
        # Print errors if any
        if self.stats['data_files']['errors'] or self.stats['profile_files']['errors']:
            print("\n" + "-" * 80)
            print("ERRORS FOUND")
            print("-" * 80)
            
            if self.stats['data_files']['errors']:
                print(f"\nData file errors ({len(self.stats['data_files']['errors'])}):")
                for error in self.stats['data_files']['errors'][:3]:
                    print(f"  - {error['name']}: {error['message']}")
                if len(self.stats['data_files']['errors']) > 3:
                    print(f"  ... and {len(self.stats['data_files']['errors']) - 3} more")
            
            if self.stats['profile_files']['errors']:
                print(f"\nProfile file errors ({len(self.stats['profile_files']['errors'])}):")
                for error in self.stats['profile_files']['errors'][:3]:
                    print(f"  - {error['name']}: {error['message']}")
                if len(self.stats['profile_files']['errors']) > 3:
                    print(f"  ... and {len(self.stats['profile_files']['errors']) - 3} more")
    
    def check_file_correlation(self, sample_size: int = 3):
        """Check correlation between data files and their profile files"""
        print("\n" + "=" * 80)
        print("FILE CORRELATION CHECK")
        print("=" * 80)
        
        if not self.data_dir_pickle.exists():
            print("Warning: data_dir_pickle does not exist")
            return
        
        data_files = list(self.data_dir_pickle.glob("*.pkl"))
        sampled = self.sample_files([{'path': f} for f in data_files], sample_size)
        
        for file_dict in sampled:
            data_file = Path(file_dict['path'])
            base_name = data_file.stem
            
            print(f"\nChecking: {data_file.name}")
            
            # Load data file to get measurement points
            try:
                with open(data_file, 'rb') as f:
                    data = pickle.load(f)
                
                num_points = len(data['data_status'])
                print(f"  Measurement points: {num_points}")
                
                # Check for corresponding profile files
                missing_profiles = []
                found_profiles = []
                
                for i in range(1, num_points + 1):
                    profile_name = f"{base_name}_{i:04d}_Height.pkl"
                    profile_path = self.profile_dir / profile_name
                    
                    if profile_path.exists():
                        found_profiles.append(i)
                    else:
                        missing_profiles.append(i)
                
                print(f"  Profile files found: {len(found_profiles)}/{num_points}")
                if missing_profiles:
                    print(f"  Missing profiles: {missing_profiles[:5]}{'...' if len(missing_profiles) > 5 else ''}")
                
            except Exception as e:
                print(f"  Error reading data file: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Check and sample AFM data files')
    parser.add_argument('--sample-size', type=int, default=5,
                        help='Number of files to sample (default: 5)')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed file information')
    parser.add_argument('--check-correlation', action='store_true',
                        help='Check correlation between data and profile files')
    parser.add_argument('--base-path', type=str,
                        help='Base path to AFM data (default: itc-afm-data-platform-pjt-shared/AFM_DB/MAP608)')
    
    args = parser.parse_args()
    
    checker = AFMFileChecker(base_path=args.base_path)
    checker.check_all(sample_size=args.sample_size, verbose=args.verbose)
    
    if args.check_correlation:
        checker.check_file_correlation(sample_size=3)


if __name__ == "__main__":
    main()