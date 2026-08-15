import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from src.models.user import db
from src.routes.user import user_bp
from src.routes.extraction import extraction_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB upload cap, matches the UI

# Enable CORS for all routes
CORS(app)

app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(extraction_bp, url_prefix='/api')


@app.errorhandler(413)
def file_too_large(_e):
    # Without this, Flask's default 413 is an HTML page, which breaks the
    # frontend's response.json() call on oversized uploads.
    return jsonify({"error": "File exceeds the 10MB limit"}), 413

# uncomment if you need to use database
_db_dir = os.path.join(os.path.dirname(__file__), 'database')
os.makedirs(_db_dir, exist_ok=True)  # SQLite can't create the file if this folder is missing (e.g. fresh clone/deploy where it wasn't tracked by git)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(_db_dir, 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        # Harmless race: with multiple gunicorn workers booting at once,
        # more than one can try to CREATE TABLE at the same moment - the
        # loser just needs to know the table now exists, not crash.
        print(f"db.create_all() skipped (likely already applied by another worker): {e}")

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
