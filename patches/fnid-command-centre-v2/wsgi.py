"""
FNID Command Centre v2.0 - WSGI Entry Point
Production Gunicorn Configuration
"""
from src.fnid_portal import create_app

app = create_app('production')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
