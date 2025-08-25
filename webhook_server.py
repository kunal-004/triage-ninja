import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from flask import Flask, request, jsonify
import hmac
import hashlib
import json

from config import GITHUB_WEBHOOK_SECRET, FLASK_PORT
from agent import process_webhook, get_agent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

webhook_stats = {
    'total_received': 0,
    'issues_triaged': 0,
    'last_webhook': None,
    'errors': 0
}

def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        logger.warning("GitHub webhook secret not configured - accepting all webhooks!")
        return True
    
    if not signature_header:
        return False
    
    hash_object = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode('utf-8'),
        payload_body,
        hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)

@app.route('/')
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Support-Triage Ninja',
        'version': '1.0.0',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/stats')
def get_stats():
    return jsonify({
        'stats': webhook_stats,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    webhook_stats['total_received'] += 1
    webhook_stats['last_webhook'] = datetime.now(timezone.utc).isoformat()
    
    try:
        payload_body = request.get_data()
        signature_header = request.headers.get('X-Hub-Signature-256', '')
        event_type = request.headers.get('X-GitHub-Event', '')
        
        if not verify_webhook_signature(payload_body, signature_header):
            logger.warning("Invalid webhook signature")
            webhook_stats['errors'] += 1
            return jsonify({'error': 'Invalid signature'}), 401
        
        try:
            payload = json.loads(payload_body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload: {e}")
            webhook_stats['errors'] += 1
            return jsonify({'error': 'Invalid JSON payload'}), 400
        
        if event_type != 'issues':
            logger.info(f"Ignoring non-issue event: {event_type}")
            return jsonify({'message': f'Ignored event type: {event_type}'}), 200
        
        action = payload.get('action', 'unknown')
        issue = payload.get('issue', {})
        repo = payload.get('repository', {})
        
        logger.info(f"Received {event_type} webhook: {action} for issue #{issue.get('number')} in {repo.get('full_name')}")
        
        # Only process 'opened' issues
        if action != 'opened':
            logger.info(f"Ignoring issue action: {action}")
            return jsonify({'message': f'Ignored action: {action}'}), 200
        
        # Process with triage agent synchronously 
        # (Flask with async is complex - keeping simple for reliability)
        def run_async_processing():
            """Run the async processing in a proper event loop."""
            try:
                # Use asyncio.run for cleaner async handling
                result = asyncio.run(process_webhook(payload))
                if result.get('success'):
                    webhook_stats['issues_triaged'] += 1
                    logger.info(f"Successfully triaged issue #{issue.get('number')}")
                else:
                    webhook_stats['errors'] += 1
                    logger.error(f"Failed to triage issue #{issue.get('number')}: {result.get('error', 'Unknown error')}")
                return result
            except Exception as e:
                webhook_stats['errors'] += 1
                logger.error(f"💥 Unexpected error processing webhook: {e}")
                import traceback
                traceback.print_exc()
                return {'success': False, 'error': str(e)}
        
        result = run_async_processing()
        
        # Return response
        if result.get('success'):
            return jsonify({
                'message': 'Issue triage initiated successfully',
                'issue_number': issue.get('number'),
                'repository': repo.get('full_name'),
                'result': result
            }), 200
        else:
            return jsonify({
                'message': 'Issue triage failed',
                'issue_number': issue.get('number'),
                'repository': repo.get('full_name'),
                'error': result.get('error', 'Unknown error')
            }), 500
            
    except Exception as e:
        webhook_stats['errors'] += 1
        logger.error(f"💥 Webhook handler error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

def create_app():
    """Create and configure the Flask application."""
    
    # Initialize logging
    if not app.debug:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    return app

async def startup():
    """Initialize the agent before starting the server."""
    logger.info("Initializing Support-Triage Ninja webhook server...")
    
    agent = get_agent()
    # Agent initializes automatically in constructor, no need for separate initialize() call
    success = True
    if not success:
        logger.error("Failed to initialize agent - server may not work properly")
        return False
    
    logger.info("Webhook server ready to receive GitHub events!")
    return True

if __name__ == '__main__':
    # Initialize agent
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        initialized = loop.run_until_complete(startup())
        if not initialized:
            logger.error("Failed to initialize - exiting")
            exit(1)
    finally:
        loop.close()
    
    # Start Flask server
    logger.info(f"🌐 Starting webhook server on port {FLASK_PORT}")
    app.run(
        host='0.0.0.0',
        port=FLASK_PORT,
        debug=False,  # Set to True for development
        threaded=True
    )
