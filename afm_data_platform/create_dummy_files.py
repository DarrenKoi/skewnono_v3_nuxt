"""
Script to create dummy directories and files for AFM data visualization
This creates sample files in each directory type to demonstrate file availability indicators
"""

import os
from pathlib import Path
import pickle
import numpy as np
from PIL import Image
import io

def create_dummy_directories(tool_name='MAP608'):
    """Create all required directories for AFM data"""
    base_path = Path('itc-afm-data-platform-pjt-shared') / 'AFM_DB' / tool_name
    
    directories = [
        'profile_dir',
        'data_dir_pickle',
        'tiff_dir',
        'align_dir',
        'tip_dir'
    ]
    
    for dir_name in directories:
        dir_path = base_path / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {dir_path}")
    
    return base_path


def get_sample_filenames(base_path, tool_name='MAP608'):
    """Get a few sample filenames from data_dir_list.txt"""
    data_list_path = base_path / 'data_dir_list.txt'
    sample_files = []
    
    if data_list_path.exists():
        with open(data_list_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Get first 5 non-empty lines
            for line in lines:
                line = line.strip()
                if line and len(sample_files) < 5:
                    sample_files.append(line)
    
    print(f"📄 Found {len(sample_files)} sample filenames")
    return sample_files


def create_dummy_profile_data(base_path, filename):
    """Create dummy profile data (X, Y, Z coordinates)"""
    filename_no_ext = filename.replace('.csv', '').replace('.pkl', '')
    
    # Create profile data for different points
    points = ['1_UL', '2_UR', '3_LL', '4_LR', '5_C']
    
    for point in points:
        # Generate dummy X, Y, Z data
        x = np.linspace(0, 100, 500)
        y = np.linspace(0, 100, 500)
        z = np.sin(x/10) * np.cos(y/10) * 50 + np.random.normal(0, 5, 500)
        
        profile_data = {
            'x': x.tolist(),
            'y': y.tolist(),
            'z': z.tolist(),
            'metadata': {
                'point': point,
                'scan_size': '100x100',
                'resolution': '500x500'
            }
        }
        
        # Create filename with pattern
        profile_filename = f"{filename_no_ext}#_{point}_0001_Height.pkl"
        profile_path = base_path / 'profile_dir' / profile_filename
        
        with open(profile_path, 'wb') as f:
            pickle.dump(profile_data, f)
        
        print(f"  📊 Created profile: {profile_filename}")


def create_dummy_measurement_data(base_path, filename):
    """Create dummy measurement data pickle file"""
    filename_no_ext = filename.replace('.csv', '').replace('.pkl', '')
    
    # Create dummy measurement data
    measurement_data = {
        'information': {
            'Tool': 'MAP608',
            'Recipe': 'DUMMY_RECIPE',
            'Lot_ID': 'TEST_LOT',
            'Slot': '01',
            'Date': '2024-12-01',
            'Time': '12:00:00'
        },
        'summary': {
            'Site': ['1_UL', '2_UR', '3_LL', '4_LR', '5_C'],
            'MEAN': [50.2, 51.3, 49.8, 50.5, 50.0],
            'STD': [2.1, 2.3, 1.9, 2.2, 2.0],
            'MAX': [55.5, 56.8, 54.2, 55.9, 55.1],
            'MIN': [45.1, 46.2, 44.9, 45.3, 45.0]
        },
        'data': [
            {'Site': '1_UL', 'X': 10, 'Y': 10, 'Z': 50.2},
            {'Site': '2_UR', 'X': 90, 'Y': 10, 'Z': 51.3},
            {'Site': '3_LL', 'X': 10, 'Y': 90, 'Z': 49.8},
            {'Site': '4_LR', 'X': 90, 'Y': 90, 'Z': 50.5},
            {'Site': '5_C', 'X': 50, 'Y': 50, 'Z': 50.0}
        ],
        'available_points': ['1_UL', '2_UR', '3_LL', '4_LR', '5_C']
    }
    
    data_filename = f"{filename_no_ext}.pkl"
    data_path = base_path / 'data_dir_pickle' / data_filename
    
    with open(data_path, 'wb') as f:
        pickle.dump(measurement_data, f)
    
    print(f"  💾 Created data: {data_filename}")


def create_dummy_image(base_path, filename, image_type='tiff'):
    """Create dummy image files"""
    filename_no_ext = filename.replace('.csv', '').replace('.pkl', '')
    
    # Create images for different points
    points = ['1_UL', '2_UR', '3_LL', '4_LR', '5_C']
    
    for point in points:
        # Create a simple gradient image
        width, height = 512, 512
        image = Image.new('RGB', (width, height))
        
        # Create gradient pattern
        for x in range(width):
            for y in range(height):
                # Create different patterns for different image types
                if image_type == 'tiff':
                    # Circular gradient for tiff (height map visualization)
                    dist = ((x - width/2)**2 + (y - height/2)**2)**0.5
                    value = int(255 * (1 - dist / (width/2)))
                    value = max(0, min(255, value))
                    image.putpixel((x, y), (value, value, value))
                elif image_type == 'align':
                    # Grid pattern for alignment
                    if x % 50 == 0 or y % 50 == 0:
                        image.putpixel((x, y), (255, 0, 0))
                    else:
                        image.putpixel((x, y), (200, 200, 200))
                elif image_type == 'tip':
                    # Radial pattern for tip
                    angle = np.arctan2(y - height/2, x - width/2)
                    value = int(127 + 127 * np.sin(angle * 8))
                    image.putpixel((x, y), (value, 100, 255 - value))
        
        # Save image based on type
        if image_type == 'tiff':
            # Save as webp for tiff_dir (as specified in the code)
            image_filename = f"{filename_no_ext}#_{point}_0001_Height.webp"
            image_path = base_path / 'tiff_dir' / image_filename
            image.save(image_path, 'WEBP', quality=90)
            print(f"  🖼️  Created image: {image_filename}")
            
        elif image_type == 'align':
            image_filename = f"{filename_no_ext}#_{point}_alignment.png"
            image_path = base_path / 'align_dir' / image_filename
            image.save(image_path, 'PNG')
            print(f"  📐 Created align: {image_filename}")
            
        elif image_type == 'tip':
            image_filename = f"{filename_no_ext}#_{point}_tip.tiff"
            image_path = base_path / 'tip_dir' / image_filename
            image.save(image_path, 'TIFF')
            print(f"  📍 Created tip: {image_filename}")


def create_dummy_files_for_measurements(tool_name='MAP608'):
    """Main function to create dummy files for sample measurements"""
    print(f"\n🚀 Creating dummy files for tool: {tool_name}")
    
    # Create directories
    base_path = create_dummy_directories(tool_name)
    
    # Get sample filenames
    sample_files = get_sample_filenames(base_path, tool_name)
    
    if not sample_files:
        print("⚠️  No sample files found in data_dir_list.txt")
        # Create some default sample files
        sample_files = [
            "#241201#TEST_RECIPE#TEST_LOT_241201#01_1#.csv",
            "#241201#TEST_RECIPE#TEST_LOT_241201#02_1#.csv",
            "#241201#DEMO_RECIPE#DEMO_LOT_241201#01_standard#.csv"
        ]
    
    # Create dummy files for each sample
    for i, filename in enumerate(sample_files):
        print(f"\n📁 Processing file {i+1}/{len(sample_files)}: {filename}")
        
        try:
            # Create different types of files based on index to show variety
            if i == 0:
                # First file: all data types
                create_dummy_profile_data(base_path, filename)
                create_dummy_measurement_data(base_path, filename)
                create_dummy_image(base_path, filename, 'tiff')
                create_dummy_image(base_path, filename, 'align')
                create_dummy_image(base_path, filename, 'tip')
            elif i == 1:
                # Second file: only profile and measurement data
                create_dummy_profile_data(base_path, filename)
                create_dummy_measurement_data(base_path, filename)
            elif i == 2:
                # Third file: only measurement data and images
                create_dummy_measurement_data(base_path, filename)
                create_dummy_image(base_path, filename, 'tiff')
            else:
                # Rest: only measurement data
                create_dummy_measurement_data(base_path, filename)
                
        except Exception as e:
            print(f"  ❌ Error processing {filename}: {e}")
            continue
    
    print(f"\n✅ Dummy file creation completed for {tool_name}!")
    print("\nFile availability summary:")
    print("- File 1: ✓ Profile, ✓ Data, ✓ Image, ✓ Align, ✓ Tip")
    print("- File 2: ✓ Profile, ✓ Data, ✗ Image, ✗ Align, ✗ Tip")
    print("- File 3: ✗ Profile, ✓ Data, ✓ Image, ✗ Align, ✗ Tip")
    print("- Others: ✗ Profile, ✓ Data, ✗ Image, ✗ Align, ✗ Tip")


if __name__ == "__main__":
    create_dummy_files_for_measurements('MAP608')
    
    # Also create directories for MAPC01 (empty for now)
    print("\n🚀 Creating empty directories for MAPC01...")
    create_dummy_directories('MAPC01')
    print("✅ Created empty directories for MAPC01")