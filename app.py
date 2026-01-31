from flask import Flask
from config import Config
from routes.main_routes import main_bp
from routes.admin_routes import admin_bp
from database import create_recordings_table

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions here if any
    create_recordings_table(Config.DB_PATH)
    create_recordings_table(Config.TRIBAL_DB_PATH)
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
