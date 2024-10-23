import os
from api.app import app

if __name__ == "__main__":
    # Get the environment (default to 'development')
    env = os.getenv('ENV', 'development')

    if env == 'production':
        # In production, use HTTPS with SSL certificates
        app.run(host='0.0.0.0', port=443, ssl_context=(
            '/etc/letsencrypt/live/yourdomain.com/fullchain.pem',
            '/etc/letsencrypt/live/yourdomain.com/privkey.pem'
        ))
    else:
        # In development, use HTTP
        app.run(host='0.0.0.0', port=5001, debug=True)
