#!/usr/bin/env python3
"""
Flask server for Render deployment
Provides health check endpoint and keeps service alive
"""

from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def health():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy',
        'service': 'Emily Social Publisher MVP',
        'mvp_specs': '100 users × 5 posts',
        'capacity': '500 posts',
        'concurrent': '21 posts simultaneous',
        'platforms': ['Facebook', 'Instagram', 'LinkedIn', 'YouTube'],
        'version': '1.0.0'
    })

@app.route('/status')
def status():
    """Detailed status endpoint"""
    return jsonify({
        'service': 'Emily Social Publisher MVP',
        'status': 'running',
        'uptime': 'active',
        'mvp_ready': True
    })

if __name__ == '__main__':
    print('🚀 Emily Social Publisher MVP - Starting...')
    print('📊 MVP Specs: 100 users × 5 posts = 500 posts capacity')
    print('⚡ Concurrent publishing: 21 posts simultaneous')
    print('🌐 Platforms: Facebook, Instagram, LinkedIn, YouTube')
    print('🔌 Web service binding to port 10000...')

    # Get port from environment (Render provides PORT, default to 10000)
    port = int(os.environ.get('PORT', 10000))

    app.run(host='0.0.0.0', port=port, debug=False)
