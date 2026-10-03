from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def hello():
    return jsonify({"message": "Hello from Flask running in Docker!", "status": "success"})

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    # This block is useful for local development
    # In production, this app will be served by Gunicorn
    app.run(host='0.0.0.0', port=5000, debug=True)
