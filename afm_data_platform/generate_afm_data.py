import os
import pickle
import random
import math
from datetime import datetime, timedelta

def parse_filename(filename):
    """Parse AFM filename to extract components"""
    # Remove .csv extension and split by #
    parts = filename.replace('.csv', '').split('#')
    
    if len(parts) >= 4:
        date = parts[1]
        recipe = parts[2]
        lot_info = parts[3]  # Contains lot_id and potentially date/time info
        slot_measurement = parts[4] if len(parts) > 4 else ""
        
        # Extract lot_id (before underscore or bracket)
        if '[' in lot_info:
            lot_id = lot_info.split('[')[0]
        elif '_' in lot_info:
            lot_id = lot_info.split('_')[0]
        else:
            lot_id = lot_info
            
        # Extract slot and measurement info
        slot = "01"
        measurement = "1"
        if slot_measurement:
            if '_' in slot_measurement:
                slot_parts = slot_measurement.split('_')
                slot = slot_parts[0]
                measurement = slot_parts[1] if len(slot_parts) > 1 else "1"
            else:
                slot = slot_measurement
                
        return {
            'date': date,
            'recipe': recipe,
            'lot_id': lot_id,
            'slot': slot,
            'measurement': measurement
        }
    
    return None

def generate_measurement_info(parsed_info):
    """Generate measurement info section"""
    # Convert date format YYMMDD to datetime
    date_str = parsed_info['date']
    year = 2000 + int(date_str[:2])
    month = int(date_str[2:4])
    day = int(date_str[4:6])
    
    start_time = datetime(year, month, day) + timedelta(
        hours=random.randint(8, 18),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )
    
    return {
        'Lot ID': parsed_info['lot_id'],
        'Recipe ID': parsed_info['recipe'],
        'Carrier ID': f"CAR{random.randint(100, 999)}",
        'Sample ID': f"S{parsed_info['slot']}",
        'Start Time': start_time.strftime("%Y-%m-%d %H:%M:%S"),
        'Tool': 'MAP608',
        'Operator': f"OP{random.randint(1000, 9999)}",
        'Measurement': parsed_info['measurement']
    }

def generate_data_status(num_points):
    """Generate data status section as a DataFrame-like structure"""
    # Initialize lists for each column
    sites = []
    items = []
    left_h_values = []
    right_h_values = []
    ref_h_values = []
    
    # Use the provided number of measurement points
    for i in range(1, num_points + 1):
        site_name = f"{i}_UL"
        
        # Generate base values with variation between points
        # Add positional bias and random variation
        position_bias = (i - 1) * random.uniform(-2, 3)  # Gradual trend across points
        point_variation = random.uniform(-15, 15)  # Random point-to-point variation
        
        left_base = random.uniform(60, 120) + position_bias + point_variation
        right_base = random.uniform(55, 115) + position_bias + point_variation * 0.8
        ref_base = random.uniform(50, 110) + position_bias + point_variation * 0.6
        
        # Add process-dependent characteristics
        process_noise = random.uniform(0.5, 3.0)  # Different noise levels
        measurement_drift = random.uniform(-1.5, 1.5)  # Systematic drift
        
        # For each ITEM (MEAN, STDEV, MIN, MAX, RANGE), add a row
        item_types = ['MEAN', 'STDEV', 'MIN', 'MAX', 'RANGE']
        left_values = [
            round(left_base + measurement_drift, 2),  # MEAN
            round(random.uniform(0.8, 4.5) * process_noise, 2),  # STDEV
            round(left_base - random.uniform(8, 20), 2),  # MIN
            round(left_base + random.uniform(8, 20), 2),  # MAX
            round(random.uniform(15, 35), 2)  # RANGE
        ]
        right_values = [
            round(right_base + measurement_drift * 0.9, 2),  # MEAN
            round(random.uniform(0.9, 4.2) * process_noise, 2),  # STDEV
            round(right_base - random.uniform(7, 18), 2),  # MIN
            round(right_base + random.uniform(7, 18), 2),  # MAX
            round(random.uniform(12, 32), 2)  # RANGE
        ]
        ref_values = [
            round(ref_base + measurement_drift * 0.7, 2),  # MEAN
            round(random.uniform(0.7, 3.8) * process_noise, 2),  # STDEV
            round(ref_base - random.uniform(6, 16), 2),  # MIN
            round(ref_base + random.uniform(6, 16), 2),  # MAX
            round(random.uniform(10, 28), 2)  # RANGE
        ]
        
        # Add 5 rows for this site (one for each ITEM)
        for j, item in enumerate(item_types):
            sites.append(site_name)
            items.append(item)
            left_h_values.append(left_values[j])
            right_h_values.append(right_values[j])
            ref_h_values.append(ref_values[j])
    
    # Return as a DataFrame-like dictionary with lists as columns
    data_status = {
        'Site': sites,
        'ITEM': items,
        'Left_H (nm)': left_h_values,
        'Right_H (nm)': right_h_values,
        'Ref_H (nm)': ref_h_values
    }
    
    return data_status

def generate_data_detail(num_points):
    """Generate detailed measurement data for each point"""
    data_detail = {}
    
    # Use the provided number of measurement points
    for i in range(1, num_points + 1):
        site_name = f"{i}_UL"
        
        # Number of measurement points for this location
        num_measurements = random.randint(20, 50)
        
        # Generate Site coordinates (X, Y) for this site
        site_x = round(random.uniform(-5000, 5000), 1)
        site_y = round(random.uniform(-5000, 5000), 1)
        
        point_data = {
            'Site ID': [site_name] * num_measurements,  # Same Site ID for all measurements in this site
            'Site X': [site_x] * num_measurements,  # Same Site X coordinate
            'Site Y': [site_y] * num_measurements,  # Same Site Y coordinate
            'Point No': list(range(1, num_measurements + 1)),
            'X (um)': [round(random.uniform(-1000, 1000), 1) for _ in range(num_measurements)],
            'Y (um)': [round(random.uniform(-1000, 1000), 1) for _ in range(num_measurements)],
            'Method ID': [random.randint(1, 5) for _ in range(num_measurements)],
            'State': [random.choice(['OK', 'NG', 'WARN']) for _ in range(num_measurements)],
            'Valid': [random.choice([True, False]) for _ in range(num_measurements)],
            'Left_H (nm)': [round(random.uniform(40, 160), 2) for _ in range(num_measurements)],
            'Left_H_Valid': [random.choice([True, False]) for _ in range(num_measurements)],
            'Right_H (nm)': [round(random.uniform(35, 155), 2) for _ in range(num_measurements)],
            'Right_H_Valid': [random.choice([True, False]) for _ in range(num_measurements)],
            'Ref_H (nm)': [round(random.uniform(30, 150), 2) for _ in range(num_measurements)],
            'Ref_H_Valid': [random.choice([True, False]) for _ in range(num_measurements)],
            'Pick Up Count': [random.randint(1, 10) for _ in range(num_measurements)],
            'Sample Count': [random.randint(1, 5) for _ in range(num_measurements)],
            'Approach Count': [random.randint(1, 3) for _ in range(num_measurements)],
            'Mileage': [round(random.uniform(0, 100), 1) for _ in range(num_measurements)]
        }
        
        data_detail[site_name] = point_data
    
    return data_detail

def generate_profile_data():
    """Generate profile data (X, Y, Z coordinates) for a 20x20 grid"""
    # Create a 20x20 grid
    grid_size = 20
    total_points = grid_size * grid_size  # 400 points
    
    # Generate X and Y coordinates for a regular grid
    x_coords = []
    y_coords = []
    
    # Grid spacing
    x_spacing = 10.0  # micrometers
    y_spacing = 10.0  # micrometers
    
    for i in range(grid_size):
        for j in range(grid_size):
            x_coords.append(round(j * x_spacing, 1))
            y_coords.append(round(i * y_spacing, 1))
    
    # Generate Z values (height) with some pattern
    # Create a surface with some features
    z_base = random.uniform(50, 100)
    z_coords = []
    
    for i in range(grid_size):
        for j in range(grid_size):
            # Add some patterns: gradients, peaks, and noise
            x_norm = j / grid_size
            y_norm = i / grid_size
            
            # Gradient component
            gradient = 20 * (x_norm + y_norm) / 2
            
            # Peak/valley component
            peak_x, peak_y = 0.5, 0.5
            distance = ((x_norm - peak_x)**2 + (y_norm - peak_y)**2)**0.5
            peak_height = 30 * math.exp(-distance * 5)
            
            # Random noise
            noise = random.uniform(-5, 5)
            
            z = z_base + gradient + peak_height + noise
            z_coords.append(round(z, 2))
    
    return {
        'X': x_coords,
        'Y': y_coords,
        'Z': z_coords
    }

def generate_profile_image_data(profile_data):
    """Generate profile image data as a binary placeholder"""
    # Create a simple BMP file structure (100x100, 24-bit)
    width, height = 100, 100
    
    # Get Z values and normalize to 0-255 range
    z_values = profile_data['Z']
    z_min = min(z_values)
    z_max = max(z_values)
    
    if z_max > z_min:
        z_normalized = [int((z - z_min) / (z_max - z_min) * 255) for z in z_values]
    else:
        z_normalized = [128] * len(z_values)
    
    # Create a simple BMP header (54 bytes)
    file_size = 54 + (width * height * 3)  # Header + pixel data
    bmp_header = bytearray(54)
    
    # BMP file header (14 bytes)
    bmp_header[0:2] = b'BM'  # Signature
    bmp_header[2:6] = file_size.to_bytes(4, 'little')  # File size
    bmp_header[10:14] = (54).to_bytes(4, 'little')  # Offset to pixel data
    
    # DIB header (40 bytes)
    bmp_header[14:18] = (40).to_bytes(4, 'little')  # DIB header size
    bmp_header[18:22] = width.to_bytes(4, 'little')  # Width
    bmp_header[22:26] = height.to_bytes(4, 'little')  # Height
    bmp_header[26:28] = (1).to_bytes(2, 'little')  # Planes
    bmp_header[28:30] = (24).to_bytes(2, 'little')  # Bits per pixel
    
    # Generate pixel data (BGR format, bottom-up)
    pixel_data = bytearray()
    
    for y in range(height):
        for x in range(width):
            # Map to 20x20 grid
            grid_x = int(x * 20 / width)
            grid_y = int(y * 20 / height)
            grid_idx = grid_y * 20 + grid_x
            
            if grid_idx < len(z_normalized):
                value = z_normalized[grid_idx]
            else:
                value = 128
            
            # Create color gradient (BGR format)
            if value < 128:
                # Blue to cyan gradient
                b = 255
                g = int(value * 2)
                r = 0
            else:
                # Cyan to red gradient
                b = 255 - int((value - 128) * 2)
                g = 255 - int((value - 128) * 2)
                r = int((value - 128) * 2)
            
            pixel_data.extend([b, g, r])  # BGR order
    
    return bmp_header + pixel_data

def generate_afm_data_file(filename, with_site_id=True):
    """Generate complete AFM data structure for a given filename"""
    parsed_info = parse_filename(filename)
    if not parsed_info:
        return None
    
    # Generate consistent number of measurement points (5-10)
    num_points = random.randint(5, 10)
    
    # Generate all three data sections with consistent point count
    info = generate_measurement_info(parsed_info)
    data_status = generate_data_status(num_points)
    data_detail = generate_data_detail(num_points)
    
    return {
        'info': info,
        'data_status': data_status,
        'data_detail': data_detail,
        'num_points': num_points,
        'with_site_id': with_site_id
    }

def main():
    # Read the file list
    base_path = '/mnt/c/Python_Projects/afm_data_platform/itc-afm-data-platform-pjt-shared/AFM_DB/MAP608'
    list_file_path = os.path.join(base_path, 'data_dir_list.txt')
    data_dir_path = os.path.join(base_path, 'data_dir_pickle')
    profile_dir_path = os.path.join(base_path, 'profile_dir')
    tiff_dir_path = os.path.join(base_path, 'tiff_dir')
    
    # Create directories if they don't exist
    os.makedirs(data_dir_path, exist_ok=True)
    os.makedirs(profile_dir_path, exist_ok=True)
    os.makedirs(tiff_dir_path, exist_ok=True)
    
    # Read all filenames
    with open(list_file_path, 'r') as f:
        filenames = [line.strip() for line in f if line.strip()]
    
    print(f"Generating AFM data for {len(filenames)} files...")
    print(f"  - Data files in: {data_dir_path}")
    print(f"  - Profile files in: {profile_dir_path}")
    print(f"  - Image files in: {tiff_dir_path}")
    
    # Decide if we're using Site ID (randomly for variation)
    with_site_id = random.choice([True, False])
    print(f"  - Using Site ID in filenames: {with_site_id}")
    
    for i, filename in enumerate(filenames):
        if filename.endswith('.csv'):
            # Base filename without extension
            base_filename = filename.replace('.csv', '')
            
            # Generate pickle filename for data
            pkl_filename = base_filename + '.pkl'
            pkl_path = os.path.join(data_dir_path, pkl_filename)
            
            # Generate data
            afm_data = generate_afm_data_file(filename, with_site_id)
            
            if afm_data:
                # Extract the actual data (without metadata) - using Flask expected keys
                data_to_save = {
                    'info': afm_data['info'],
                    'summary': afm_data['data_status'],    # data_status -> summary
                    'data': afm_data['data_detail']        # data_detail -> data
                }
                
                # Save main data file
                with open(pkl_path, 'wb') as f:
                    pickle.dump(data_to_save, f)
                
                # Generate profile and image files for each site
                num_points = afm_data['num_points']
                sites = list(afm_data['data_detail'].keys())  # Get site names like "1_UL", "2_UL", etc.
                
                for site_idx, site_name in enumerate(sites):
                    # Get measurements for this site
                    site_detail = afm_data['data_detail'][site_name]
                    num_measurements = len(site_detail['Point No'])
                    
                    # Generate profile and image files for some measurements (not all)
                    # Typically generate 3-5 profile files per site
                    num_profiles = min(random.randint(3, 5), num_measurements)
                    selected_points = random.sample(range(1, num_measurements + 1), num_profiles)
                    
                    for point_no in selected_points:
                        # Generate profile data
                        profile_data = generate_profile_data()
                        
                        # Create filename based on whether we have Site ID
                        if with_site_id:
                            # Format: base_filename + "_" + site_name + "_" + point_no + "_Height"
                            profile_filename = f"{base_filename}_{site_name}_{point_no:04d}_Height.pkl"
                            image_filename = f"{base_filename}_{site_name}_{point_no:04d}_Height.webp"
                        else:
                            # Format: base_filename + "_" + point_no + "_Height"
                            # For files without site ID, use global point numbering
                            global_point_no = (site_idx * 100) + point_no  # Ensure unique numbering
                            profile_filename = f"{base_filename}_{global_point_no:04d}_Height.pkl"
                            image_filename = f"{base_filename}_{global_point_no:04d}_Height.webp"
                        
                        # Save profile data
                        profile_path = os.path.join(profile_dir_path, profile_filename)
                        with open(profile_path, 'wb') as f:
                            pickle.dump(profile_data, f)
                        
                        # Generate and save image
                        image_data = generate_profile_image_data(profile_data)
                        image_path = os.path.join(tiff_dir_path, image_filename)
                        # Save as BMP format but with .webp extension (as per original behavior)
                        with open(image_path, 'wb') as f:
                            f.write(image_data)
                
                if (i + 1) % 10 == 0:
                    print(f"Generated {i + 1}/{len(filenames)} file sets...")
    
    print(f"\nSuccessfully generated data for {len(filenames)} AFM files:")
    print(f"  - {len(filenames)} data files in {data_dir_path}")
    print(f"  - Profile and image files in respective directories")

if __name__ == "__main__":
    main()