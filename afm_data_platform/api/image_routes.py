"""
Image Handling API Routes
Handles image retrieval and serving from different directories
"""
from flask import Blueprint, jsonify, request, send_file, make_response
from pathlib import Path
from urllib.parse import unquote
from .utils.file_parser import get_image_file_path_by_filename
import mimetypes

# Create image handling blueprint
image_bp = Blueprint('image', __name__)


@image_bp.route('/afm-files/image/<path:filename>/<path:decoded_point_number>', methods=['GET'])
def get_profile_image(filename, decoded_point_number):
    """Get profile image from tiff_dir for a specific measurement point"""
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
        
        print(f"\n=== IMAGE API REQUEST ===")
        print(f"Tool: {tool_name}")
        print(f"Filename (encoded): '{filename}'")
        print(f"Filename (decoded): '{decoded_filename}'")
        print(f"Site ID (encoded): '{decoded_point_number}'")
        print(f"Site ID (decoded): '{decoded_point_number}'")
        print(f"Complete site info: {site_info}")
        
        # Find matching image file using the utility function
        image_path = get_image_file_path_by_filename(decoded_filename, decoded_point_number, tool_name, site_info)
        
        if not image_path:
            return jsonify({
                'success': False,
                'error': 'Image file not found',
                'message': f'No image file found for filename: {decoded_filename}, point: {decoded_point_number} in tool {tool_name}',
                'tool': tool_name
            }), 404
        
        # Check if file exists
        if not image_path.exists():
            return jsonify({
                'success': False,
                'error': 'Image file not accessible',
                'message': f'Image file {image_path.name} exists in listing but not accessible',
                'tool': tool_name
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'filename': image_path.name,
                'path': str(image_path),
                'relative_path': f'tiff_dir/{image_path.name}',
                'url': f'/api/afm-files/image-file/{decoded_filename}/{decoded_point_number}?tool={tool_name}'
            },
            'tool': tool_name,
            'message': f'Successfully found image for {decoded_filename}, point {decoded_point_number} from {tool_name}'
        })
        
    except Exception as e:
        print(f"Error in get_profile_image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': f'Failed to find image for {decoded_filename}, point {decoded_point_number}'
        }), 500


@image_bp.route('/afm-files/image-file/<path:filename>/<path:point_number>', methods=['GET'])
def serve_profile_image(filename, point_number):
    """Serve the actual image file (legacy endpoint)"""
    try:
        tool_name = request.args.get('tool', 'MAP608')
        # URL decode the filename and point number
        decoded_filename = unquote(filename)
        decoded_point_number = unquote(point_number)
        
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
        
        print(f"\n=== IMAGE FILE SERVE REQUEST ===")
        print(f"Tool: {tool_name}")
        print(f"Filename (encoded): '{filename}'")
        print(f"Filename (decoded): '{decoded_filename}'")
        print(f"Site ID (encoded): '{point_number}'")
        print(f"Site ID (decoded): '{decoded_point_number}'")
        print(f"Complete site info: {site_info}")
        
        # Find matching image file using the utility function
        image_path = get_image_file_path_by_filename(decoded_filename, decoded_point_number, tool_name, site_info)
        
        if not image_path or not image_path.exists():
            return "Image file not found", 404
        
        return send_file(image_path, mimetype='image/webp')
        
    except Exception as e:
        print(f"Error serving image: {e}")
        return f"Error serving image: {str(e)}", 500


# Note: This endpoint is currently not used by the frontend
# Keeping it for potential future use
@image_bp.route('/afm-files/images/<image_type>', methods=['GET'])
def get_images_by_type(image_type):
    """Get list of images from specific directory type (profile, tiff, align, tip, capture)"""
    try:
        tool_name = request.args.get('tool', 'MAP608')
        
        # Define base directory for the tool
        base_dir = Path(f"itc-afm-data-platform-pjt-shared/AFM_DB/{tool_name}")
        
        # Map image types to directory names
        dir_mapping = {
            'profile': 'profile_dir',
            'tiff': 'tiff_dir',
            'align': 'align_dir',
            'tip': 'tip_dir',
            'capture': 'capture_dir'
        }
        
        if image_type not in dir_mapping:
            return jsonify({
                'success': False,
                'error': 'Invalid image type',
                'message': f'Image type must be one of: {list(dir_mapping.keys())}'
            }), 400
        
        # For now, just return empty list since frontend doesn't use this
        return jsonify({
            'success': True,
            'data': {
                'images': [],
                'type': image_type
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@image_bp.route('/afm-files/image-file/<path:filename>/<path:point_id>/<image_type>/<image_name>', methods=['GET'])
def serve_image_by_type(filename, point_id, image_type, image_name):
    """Serve image file from specific directory type"""
    try:
        tool_name = request.args.get('tool', 'MAP608')
        
        # URL decode image name (filename and point_id are handled by Flask)
        decoded_image_name = unquote(image_name)
        
        # Map image types to directory names
        dir_mapping = {
            'profile': 'profile_dir',
            'tiff': 'tiff_dir',
            'align': 'align_dir',
            'tip': 'tip_dir',
            'capture': 'capture_dir'
        }
        
        if image_type not in dir_mapping:
            return "Invalid image type", 400
        
        # Build image path directly - no existence check needed
        image_path = Path(f"itc-afm-data-platform-pjt-shared/AFM_DB/{tool_name}/{dir_mapping[image_type]}/{decoded_image_name}")
        
        # Determine mimetype based on extension
        ext = image_path.suffix.lower()
        mimetype_mapping = {
            '.webp': 'image/webp',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff'
        }
        
        mimetype = mimetype_mapping.get(ext, 'application/octet-stream')
        
        # Let send_file handle the 404 if file doesn't exist
        return send_file(image_path, mimetype=mimetype)
        
    except Exception as e:
        return f"Error serving image: {str(e)}", 500


@image_bp.route('/afm-files/download-raw-image/<path:filename>/<path:point_number>', methods=['GET'])
def download_raw_image(filename, point_number):
    """Download the raw image file with proper Content-Disposition header"""
    try:
        tool_name = request.args.get('tool', 'MAP608')
        # URL decode the filename and point number
        decoded_filename = unquote(filename)
        decoded_point_number = unquote(point_number)
        
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
        
        print(f"\n=== RAW IMAGE DOWNLOAD REQUEST ===")
        print(f"Tool: {tool_name}")
        print(f"Filename (decoded): '{decoded_filename}'")
        print(f"Point number (decoded): '{decoded_point_number}'")
        print(f"Site info: {site_info}")
        
        # Find matching image file using the utility function
        image_path = get_image_file_path_by_filename(decoded_filename, decoded_point_number, tool_name, site_info)
        
        if not image_path or not image_path.exists():
            return jsonify({
                'success': False,
                'error': 'Image file not found',
                'message': f'No image found for {decoded_filename}, point {decoded_point_number}'
            }), 404
        
        # Get the file extension and determine mimetype
        ext = image_path.suffix.lower()
        
        # Set appropriate mimetype
        if ext == '.webp':
            # If the file is WebP, we'll serve it as is
            # You can change this to convert to TIFF if needed
            mimetype = 'image/webp'
            download_ext = '.webp'
        else:
            # For any other format, use mimetypes
            mimetype = mimetypes.guess_type(str(image_path))[0] or 'application/octet-stream'
            download_ext = ext
        
        # Create a download-friendly filename
        # Remove special characters from the AFM filename
        safe_filename = decoded_filename.replace('#', '_').replace('/', '_')
        download_filename = f"{safe_filename}_point_{decoded_point_number}{download_ext}"
        
        # Create response with file
        response = make_response(send_file(
            image_path, 
            mimetype=mimetype,
            as_attachment=True,
            download_name=download_filename
        ))
        
        # Add Content-Disposition header for download
        response.headers['Content-Disposition'] = f'attachment; filename="{download_filename}"'
        
        return response
        
    except Exception as e:
        print(f"Error downloading raw image: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to download image'
        }), 500