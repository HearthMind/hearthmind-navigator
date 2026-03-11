"""
Navigator v2 — Mission Control Style
HearthMind LLC
"""

import sys
import os
from pathlib import Path
from flask import Flask

# Make src/ importable
SRC_DIR = Path(__file__).parent
sys.path.insert(0, str(SRC_DIR))

def create_app():
    app = Flask(__name__,
                template_folder=str(SRC_DIR.parent / 'templates'),
                static_folder=str(SRC_DIR.parent / 'static'))

    # Pre-load programs at startup
    from data_loader import load_programs
    load_programs()

    import routes_v2
    app.register_blueprint(routes_v2.bp)
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    print(f"[Navigator v2] Running on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
