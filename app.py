from flask import Flask
from config import Config
from routes.main_routes import main_bp
from routes.admin_routes import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions here if any
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
