import os
import logging
from flask import Flask, jsonify, redirect, url_for
from flask_login import LoginManager, current_user

from config import Config
from models import db, User, Conversation

# Blueprints
from routes.auth import auth_bp
from routes.main import main_bp
from routes.api import api_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        handlers=[
            logging.FileHandler('app.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Войдите, чтобы продолжить'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # Context processor for sidebar
    @app.context_processor
    def inject_user_data():
        if current_user.is_authenticated:
            recent = Conversation.query.filter_by(user_id=current_user.id, is_archived=False).order_by(Conversation.updated_at.desc()).limit(5).all()
        else:
            recent = []
        return dict(recent_conversations=recent)

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        if '/api/' in str(e) or 'api' in str(e):
            # crude check
            pass
        # json for api routes
        from flask import request
        if request.path.startswith('/api/'):
            return jsonify({'error': 'not found'}), 404
        return redirect(url_for('main.dashboard'))

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Server error")
        from flask import request
        if request.path.startswith('/api/'):
            return jsonify({'error': 'server error'}), 500
        return "Server error", 500

    # Init DB
    with app.app_context():
        db.create_all()
        # seed
        from seed import seed_data
        try:
            seed_data()
        except Exception as ex:
            app.logger.warning(f"Seed skipped: {ex}")

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
