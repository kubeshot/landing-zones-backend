from .bootstrap import bootstrap_bp
from .validation import validation_bp

def register_routes(app):
    app.register_blueprint(bootstrap_bp)
    app.register_blueprint(validation_bp)
