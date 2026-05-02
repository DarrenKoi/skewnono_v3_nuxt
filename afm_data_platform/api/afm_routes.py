"""
AFM Data API Routes
Handles AFM file data retrieval and profile data operations
"""
import pickle
from flask import Blueprint, jsonify, request
from pathlib import Path
from urllib.parse import unquote
from datetime import datetime
from .utils.app_logger_standard import get_activity_logger
from .utils.file_parser import (
    load_afm_file_list, 
    get_pickle_file_path_by_filename,
    get_profile_file_path_by_filename,
)

# Create AFM data blueprint
afm_bp = Blueprint('afm', __name__)

# Get activity logger
activity_logger = get_activity_logger()

def log_afm_access(action, **kwargs):
    """Log AFM data access activities"""
    try:
        # Get user from cookie
        user_id = request.cookies.get('LAST_USER', 'anonymous')
        
        # Log with structured data
        activity_logger.info(f"AFM {action}", extra={
                           'user': user_id,
                           'action': action,
                           'timestamp': datetime.now().isoformat(),
                           **kwargs})
    except Exception:
        # Don't let logging errors break the API
        pass


@afm_bp.route('/afm-files', methods=['GET'])
def get_afm_files():
    """Get parsed AFM file data for a specific tool"""
    try:
        # Get tool parameter from query string, default to MAP608
        tool_name = request.args.get('tool', 'MAP608')
        print(f"=== AFM Files API Called for tool: {tool_name} ===")
        
        # Load and parse the file list for the specified tool
        parsed_data = load_afm_file_list(tool_name)
        
        # Log the access
        log_afm_access(
            action="list_files",
            tool=tool_name,
            files_count=len(parsed_data)
        )
        
        print(f"Returning {len(parsed_data)} measurements to frontend")
        
        # Print sample data for debugging
        if parsed_data:
            print(f"Sample measurement data: {len(parsed_data[0])}")
            # print(f"  First item: {parsed_data[0]}")

        return jsonify({
            'success': True,
            'data': parsed_data,
            'total': len(parsed_data),
            'tool': tool_name,
            'message': f'Successfully loaded {len(parsed_data)} AFM measurements for {tool_name}'
        })
        
    except Exception as e:
        print(f"Error in get_afm_files: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to load AFM file data'
        }), 500


@afm_bp.route('/afm-files/detail/<path:filename>', methods=['GET'])
def get_afm_file_detail(filename):
    """Get detailed AFM measurement data from pickle file for a specific tool"""
    try:
        tool_name = request.args.get('tool', 'MAP608')
        # URL decode the filename
        decoded_filename = unquote(filename)
        print(f"=== AFM Detail API Called for tool: {tool_name}, filename: '{decoded_filename}' ===")
        
        # Find matching pickle file using the utility function
        pickle_path = get_pickle_file_path_by_filename(decoded_filename, tool_name)
        
        if not pickle_path:
            return jsonify({
                'success': False,
                'error': 'Measurement file not found',
                'message': f'No pickle file found for filename: {decoded_filename} in tool {tool_name}',
                'tool': tool_name
            }), 404
        
        # Load pickle file
        print(f"Loading pickle file: {pickle_path}")
        
        with open(pickle_path, 'rb') as f:
            data = pickle.load(f)
        
        # Extract measurement information from 'info' key (dict)
        data_info = data.get('info', {})
        
        # Extract summary data and convert to records using pandas if available
        data_summary = data.get('summary', {})
        if hasattr(data_summary, 'to_dict'):
            # It's a DataFrame
            summary_records = data_summary.to_dict('records')
        elif isinstance(data_summary, dict) and 'Site' in data_summary and 'ITEM' in data_summary:
            # Dict with columnar data - convert to records
            summary_records = []
            num_rows = len(data_summary.get('Site', []))
            for i in range(num_rows):
                record = {}
                for key, values in data_summary.items():
                    if isinstance(values, list) and i < len(values):
                        record[key] = values[i]
                if record:
                    summary_records.append(record)
        elif isinstance(data_summary, list):
            # Already in records format
            summary_records = data_summary
        else:
            summary_records = []
        
        # Extract detailed data and convert to records
        data_detail = data.get('data', {})
        if hasattr(data_detail, 'to_dict'):
            # It's a DataFrame
            detail_records = data_detail.to_dict('records')
        elif isinstance(data_detail, dict):
            # Dict with measurement points as keys
            detail_records = []
            for point_key, point_data in data_detail.items():
                if isinstance(point_data, dict) and any(isinstance(v, list) for v in point_data.values()):
                    # Convert columnar data to records
                    num_rows = max(len(v) for v in point_data.values() if isinstance(v, list))
                    for i in range(num_rows):
                        record = {'measurement_point': point_key}
                        for key, values in point_data.items():
                            if isinstance(values, list) and i < len(values):
                                record[key] = values[i]
                        detail_records.append(record)
        elif isinstance(data_detail, list):
            # Already in records format
            detail_records = data_detail
        else:
            detail_records = []
        
        # Extract available measurement points
        available_points = []
        if isinstance(data_detail, dict):
            # Get measurement points directly from data keys
            available_points = sorted(list(data_detail.keys()))
        elif summary_records:
            # Extract unique sites from summary records
            sites = {record.get('Site') for record in summary_records if 'Site' in record}
            available_points = sorted(list(sites))

        response_data = {
            'success': True,
            'data': {
                'filename': decoded_filename,
                'tool': tool_name,
                'pickle_filename': pickle_path.name,
                'information': data_info,
                'summary': summary_records,
                'data': detail_records,
                'available_points': available_points,
            },
            'message': f'Successfully loaded measurement data for {decoded_filename} from {tool_name}'
        }
        
        # Print sample data for debugging
        print(f"Successfully loaded pickle data:")
        print(f"  - Summary records: {len(summary_records)} items")
        if summary_records:
            print(f"  - Sample summary: {summary_records[0]}")
        print(f"  - Detail records: {len(detail_records)} items") 
        if detail_records:
            print(f"  - Sample detail: {detail_records[0]}")
        print(f"  - Available points: {available_points}")
        
        # Log the detail access
        log_afm_access(
            action="get_detail",
            tool=tool_name,
            filename=decoded_filename,
            pickle_file=pickle_path.name,
            summary_count=len(summary_records),
            detail_count=len(detail_records),
            available_points=available_points
        )
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in get_afm_file_detail: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': f'Failed to load measurement detail for {decoded_filename}'
        }), 500


@afm_bp.route('/afm-files/profile/<path:filename>/<path:decoded_point_number>', methods=['GET'])
def get_profile_data(filename, decoded_point_number):
    """Get profile data (x,y,z) from profile_dir for a specific measurement point"""
    try:
        tool_name = request.args.get('tool', 'MAP608')
        # URL decode the filename and point number
        decoded_filename = unquote(filename)
        decoded_point_number = unquote(decoded_point_number)
        
        # Extract site information from query parameters
        site_info = {
            'site_id': request.args.get('site_id'),     # Keep as string
            'site_x': request.args.get('site_x'),       # Keep as string
            'site_y': request.args.get('site_y'),       # Keep as string
            'point_no': request.args.get('point_no')    # Will convert to int
        }
        
        # Only convert point_no to integer (for 4-digit formatting)
        if site_info['point_no']:
            try:
                site_info['point_no'] = int(site_info['point_no'])
            except ValueError:
                site_info['point_no'] = None
        
        print(f"\n=== PROFILE API REQUEST ===")
        print(f"Tool: {tool_name}")
        print(f"Filename (encoded): '{filename}'")
        print(f"Filename (decoded): '{decoded_filename}'")
        print(f"Site ID (encoded): '{decoded_point_number}'")
        print(f"Site ID (decoded): '{decoded_point_number}'")
        print(f"Complete site info: {site_info}")
        
        # Find matching profile file using the utility function
        profile_path = get_profile_file_path_by_filename(decoded_filename, decoded_point_number, tool_name, site_info)
        
        if not profile_path:
            return jsonify({
                'success': False,
                'error': 'Profile file not found',
                'message': f'No profile file found for filename: {decoded_filename}, point: {decoded_point_number} in tool {tool_name}',
                'tool': tool_name
            }), 404
        
        # Check if file exists
        if not profile_path.exists():
            return jsonify({
                'success': False,
                'error': 'Profile file not accessible',
                'message': f'Profile file {profile_path.name} exists in listing but not accessible',
                'tool': tool_name
            }), 404
        
        # Load profile data from pickle file
        try:
            with open(profile_path, 'rb') as f:
                profile_data = pickle.load(f)
            
            print(f"Profile data type: {type(profile_data)}")
            print(f"Profile data structure: {profile_data if isinstance(profile_data, dict) and len(str(profile_data)) < 500 else 'Too large to display'}")
            
            # Handle different profile data formats
            if isinstance(profile_data, list):
                # Already in the expected format
                final_profile_data = profile_data
            elif isinstance(profile_data, dict):
                # If it's a dict, try to extract relevant data
                if 'data' in profile_data:
                    final_profile_data = profile_data['data']
                elif 'profile' in profile_data:
                    final_profile_data = profile_data['profile']
                elif 'coordinates' in profile_data:
                    final_profile_data = profile_data['coordinates']
                else:
                    # Try to convert dict to list format
                    # Check if it has x, y, z keys (both lowercase and uppercase)
                    x_key = None
                    y_key = None
                    z_key = None
                    
                    # Find the coordinate keys (case-insensitive)
                    for key in profile_data.keys():
                        if key.lower() == 'x':
                            x_key = key
                        elif key.lower() == 'y':
                            y_key = key
                        elif key.lower() == 'z':
                            z_key = key
                    
                    if x_key and y_key and z_key:
                        print(f"Found coordinate keys: X='{x_key}', Y='{y_key}', Z='{z_key}'")
                        
                        # Convert columnar data to list of dicts
                        x_vals = profile_data[x_key] if isinstance(profile_data[x_key], list) else [profile_data[x_key]]
                        y_vals = profile_data[y_key] if isinstance(profile_data[y_key], list) else [profile_data[y_key]]
                        z_vals = profile_data[z_key] if isinstance(profile_data[z_key], list) else [profile_data[z_key]]
                        
                        print(f"Coordinate data lengths: X={len(x_vals)}, Y={len(y_vals)}, Z={len(z_vals)}")

                        final_profile_data = []
                        for i in range(min(len(x_vals), len(y_vals), len(z_vals))):
                            final_profile_data.append({
                                'x': x_vals[i],
                                'y': y_vals[i], 
                                'z': z_vals[i]
                            })
                        
                        print(f"Converted {len(final_profile_data)} coordinate points to list format")
                    else:
                        print(f"Unknown dict structure. Keys: {list(profile_data.keys())}")
                        print(f"Looking for coordinate keys (case-insensitive): x_key={x_key}, y_key={y_key}, z_key={z_key}")
                        return jsonify({
                            'success': False,
                            'error': 'Unsupported profile data format',
                            'message': f'Profile data is a dict but doesn\'t have expected coordinate structure. Keys: {list(profile_data.keys())}',
                            'tool': tool_name
                        }), 400
            else:
                return jsonify({
                    'success': False,
                    'error': 'Invalid profile data format',
                    'message': f'Profile data should be a list or dict, got {type(profile_data)}',
                    'tool': tool_name
                }), 400
            
            # Ensure final data is a list
            if not isinstance(final_profile_data, list):
                return jsonify({
                    'success': False,
                    'error': 'Failed to convert profile data to list',
                    'message': f'Converted profile data is not a list, got {type(final_profile_data)}',
                    'tool': tool_name
                }), 400
            
            print(f"Successfully loaded {len(final_profile_data)} profile data points")
            if final_profile_data:
                print(f"Sample profile data point: {final_profile_data[0]}")
            
            return jsonify({
                'success': True,
                'data': final_profile_data,
                'count': len(final_profile_data),
                'tool': tool_name,
                'message': f'Successfully loaded profile data for {decoded_filename}, point {decoded_point_number} from {tool_name}'
            })
            
        except Exception as e:
            print(f"Error loading profile pickle file: {e}")
            return jsonify({
                'success': False,
                'error': 'Failed to load profile data',
                'message': f'Error reading profile file: {str(e)}',
                'tool': tool_name
            }), 500
        
    except Exception as e:
        print(f"Error in get_profile_data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': f'Failed to get profile data for {decoded_filename}, point {decoded_point_number}'
        }), 500