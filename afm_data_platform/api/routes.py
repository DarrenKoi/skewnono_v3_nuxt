"""
AFM Data Platform API Routes
Main router that registers all blueprints for modular API organization
"""
from flask import Blueprint, jsonify

# Import all blueprints
from .activity_routes import activity_bp
from .afm_routes import afm_bp
from .image_routes import image_bp

# Create main API blueprint
api_bp = Blueprint('api', __name__)

# Health Check Route (keep in main router)
@api_bp.route('/health', methods=['GET'])
def health():
    """API health check"""
    return jsonify({'status': 'API is healthy', 'service': 'AFM Data Platform API'})


# Function to register all blueprints with the Flask app
def register_blueprints(app):
    """
    Register all API blueprints with the Flask application
    
    Args:
        app: Flask application instance
    """
    # Register main API blueprint (contains health check)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register specialized blueprints with /api prefix
    app.register_blueprint(activity_bp, url_prefix='/api')  # User activity routes
    app.register_blueprint(afm_bp, url_prefix='/api')       # AFM data routes  
    app.register_blueprint(image_bp, url_prefix='/api')     # Image handling routes
    
    print("✅ All API blueprints registered successfully:")
    print("   - /api/health (Health check)")
    print("   - /api/user-activities, /api/my-activities (Activity tracking)")
    print("   - /api/afm-files/* (AFM data operations)")
    print("   - /api/afm-files/image* (Image handling)")