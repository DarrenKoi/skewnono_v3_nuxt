import os
import pickle
import random
import math
import struct

def get_measurement_points_from_data_dir(data_dir_path, filename):
    """Get number of measurement points from existing data_dir pickle file"""
    pkl_filename = filename.replace('.csv', '.pkl')
    pkl_path = os.path.join(data_dir_path, pkl_filename)
    
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
            measurement_points = list(data['data_detail'].keys())
            return len(measurement_points)
    except:
        return 5  # Default fallback

def generate_profile_data(grid_size=20):
    """Generate X, Y, Z profile data for heatmap"""
    profile_data = {
        'X': [],
        'Y': [],
        'Z': []
    }
    
    # Create a grid of X, Y coordinates
    for i in range(grid_size):
        for j in range(grid_size):
            x = -50 + (100 * i / (grid_size - 1))
            y = -50 + (100 * j / (grid_size - 1))
            
            # Generate realistic AFM height data (Z) with patterns
            z = (
                10 * math.sin(x/10) * math.cos(y/10) +  # Wave pattern
                5 * math.exp(-((x-10)**2 + (y-10)**2)/100) +  # Peak
                3 * math.exp(-((x+15)**2 + (y-15)**2)/150) +  # Another peak
                random.gauss(0, 1)  # Noise
            )
            
            # Add baseline offset
            z += random.uniform(80, 120)
            
            profile_data['X'].append(round(x, 2))
            profile_data['Y'].append(round(y, 2))
            profile_data['Z'].append(round(z, 2))
    
    return profile_data

def create_simple_ppm_image(width=100, height=100):
    """Create a simple PPM image and convert to basic image file"""
    # Generate simple pattern data
    image_data = []
    
    for y in range(height):
        for x in range(width):
            # Create a gradient-like pattern
            r = int(128 + 50 * math.sin(x/10) * math.cos(y/10)) % 255
            g = int(r + 20) % 255
            b = int(r + 40) % 255
            
            # Ensure values are in valid range
            r = max(0, min(255, r))
            g = max(0, min(255, g)) 
            b = max(0, min(255, b))
            
            image_data.extend([r, g, b])
    
    return image_data, width, height

def create_simple_bmp(image_data, width, height, filepath):
    """Create a simple BMP file that can be viewed as an image"""
    # BMP header (54 bytes)
    file_size = 54 + width * height * 3
    
    # BMP file header (14 bytes)
    bmp_header = bytearray([
        0x42, 0x4D,  # "BM" signature
        file_size & 0xFF, (file_size >> 8) & 0xFF, (file_size >> 16) & 0xFF, (file_size >> 24) & 0xFF,  # File size
        0x00, 0x00, 0x00, 0x00,  # Reserved
        0x36, 0x00, 0x00, 0x00   # Offset to pixel data
    ])
    
    # BMP info header (40 bytes)
    info_header = bytearray([
        0x28, 0x00, 0x00, 0x00,  # Header size
        width & 0xFF, (width >> 8) & 0xFF, (width >> 16) & 0xFF, (width >> 24) & 0xFF,  # Width
        height & 0xFF, (height >> 8) & 0xFF, (height >> 16) & 0xFF, (height >> 24) & 0xFF,  # Height
        0x01, 0x00,  # Planes
        0x18, 0x00,  # Bits per pixel (24)
        0x00, 0x00, 0x00, 0x00,  # Compression
        0x00, 0x00, 0x00, 0x00,  # Image size
        0x13, 0x0B, 0x00, 0x00,  # X pixels per meter
        0x13, 0x0B, 0x00, 0x00,  # Y pixels per meter
        0x00, 0x00, 0x00, 0x00,  # Colors used
        0x00, 0x00, 0x00, 0x00   # Important colors
    ])
    
    with open(filepath, 'wb') as f:
        f.write(bmp_header)
        f.write(info_header)
        
        # BMP stores pixels bottom-to-top, and in BGR format
        for y in range(height - 1, -1, -1):
            for x in range(width):
                idx = (y * width + x) * 3
                # Convert RGB to BGR
                b = image_data[idx + 2]
                g = image_data[idx + 1] 
                r = image_data[idx]
                f.write(bytes([b, g, r]))

def main():
    # Paths
    list_file_path = '/mnt/c/Python_Projects/afm_data_platform/itc-afm-data-platform-pjt-shared/AFM_DB/MAP608/data_dir_list.txt'
    data_dir_path = '/mnt/c/Python_Projects/afm_data_platform/itc-afm-data-platform-pjt-shared/AFM_DB/MAP608/data_dir'
    profile_dir_path = '/mnt/c/Python_Projects/afm_data_platform/itc-afm-data-platform-pjt-shared/AFM_DB/MAP608/profile_dir'
    tiff_dir_path = '/mnt/c/Python_Projects/afm_data_platform/itc-afm-data-platform-pjt-shared/AFM_DB/MAP608/tiff_dir'
    
    # Create directories
    os.makedirs(profile_dir_path, exist_ok=True)
    os.makedirs(tiff_dir_path, exist_ok=True)
    
    # Read all filenames
    with open(list_file_path, 'r') as f:
        filenames = [line.strip() for line in f if line.strip()]
    
    print(f"Generating profile and tiff files for {len(filenames)} entries...")
    
    profile_count = 0
    tiff_count = 0
    
    for i, filename in enumerate(filenames):
        if filename.endswith('.csv'):
            # Get number of measurement points from data_dir
            num_measurement_points = get_measurement_points_from_data_dir(data_dir_path, filename)
            
            # Generate profile files for each measurement point
            base_filename = filename.replace('.csv', '')
            
            for point_num in range(1, num_measurement_points + 1):
                # Profile file: #...#_000X_Height.txt -> saved as pickle
                profile_filename = f"{base_filename}_{point_num:04d}_Height.pkl"
                profile_path = os.path.join(profile_dir_path, profile_filename)
                
                # Generate profile data (X, Y, Z dictionary)
                profile_data = generate_profile_data(grid_size=20)  # 20x20 grid
                
                # Save as pickle
                with open(profile_path, 'wb') as f:
                    pickle.dump(profile_data, f)
                
                profile_count += 1
                
                # Tiff file: same name but with .webp extension
                tiff_filename = f"{base_filename}_{point_num:04d}_Height.webp"
                tiff_path = os.path.join(tiff_dir_path, tiff_filename)
                
                # Generate dummy image (save as BMP but with .webp extension)
                image_data, width, height = create_simple_ppm_image(width=100, height=100)
                create_simple_bmp(image_data, width, height, tiff_path)
                
                tiff_count += 1
            
            if (i + 1) % 20 == 0:
                print(f"Processed {i + 1}/{len(filenames)} files...")
                print(f"  Generated {profile_count} profile files")
                print(f"  Generated {tiff_count} tiff files")
    
    print(f"\nCompleted!")
    print(f"Total profile files generated: {profile_count}")
    print(f"Total tiff files generated: {tiff_count}")
    print(f"Profile files saved in: {profile_dir_path}")
    print(f"Tiff files saved in: {tiff_dir_path}")

if __name__ == "__main__":
    main()