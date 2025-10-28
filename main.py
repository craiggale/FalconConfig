from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import copy

from services.parser import parse_availability_file, parse_pricing_file, parse_tech_file, detect_file_type, extract_market_from_filename
from services.pricing import get_currency_symbol, format_price, calculate_total_price, get_vehicle_base_price, get_feature_price
from services.availability import get_feature_status, get_available_features, get_selectable_features
from services.tech import get_vehicle_specs, get_key_highlights
from services.validators import validate_config
from services.ai_edit import apply_ai_edit, generate_diff

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'data/uploads'

ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'admin123')
CONFIG_FILE = 'data/config.json'

working_config = None

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return None

def save_config(config):
    try:
        if 'metadata' not in config:
            config['metadata'] = {
                'lastUpdated': datetime.utcnow().isoformat() + 'Z',
                'uploadedFiles': [],
                'version': '1.0.0'
            }
        else:
            config['metadata']['lastUpdated'] = datetime.utcnow().isoformat() + 'Z'
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def ensure_metadata(config):
    if 'metadata' not in config:
        config['metadata'] = {
            'lastUpdated': datetime.utcnow().isoformat() + 'Z',
            'uploadedFiles': [],
            'version': '1.0.0'
        }
    
    if 'uploadedFiles' not in config['metadata']:
        config['metadata']['uploadedFiles'] = []
    
    return config

def is_author():
    return session.get('is_author', False)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/author/login', methods=['GET', 'POST'])
def author_login():
    if request.method == 'POST':
        token = request.form.get('token', '')
        if token == ADMIN_TOKEN:
            session['is_author'] = True
            session.permanent = True
            return redirect(url_for('author_dashboard'))
        else:
            return render_template('author_login.html', error='Invalid token')
    
    return render_template('author_login.html')

@app.route('/author/logout')
def author_logout():
    session.pop('is_author', None)
    return redirect(url_for('index'))

@app.route('/author')
def author_dashboard():
    if not is_author():
        return redirect(url_for('author_login'))
    
    config = load_config()
    
    if config:
        config = ensure_metadata(config)
        metadata = config.get('metadata', {})
    else:
        metadata = {}
    
    stats = {}
    if config:
        stats['markets'] = len(config.get('markets', []))
        stats['total_vehicles'] = sum(len(config['availability'].get(m, {}).get('vehicles', [])) for m in config.get('markets', []))
        stats['total_features'] = sum(len(config['availability'].get(m, {}).get('features', [])) for m in config.get('markets', []))
        stats['engines'] = len(config.get('tech', {}).get('engines', []))
    
    return render_template('author.html', metadata=metadata, stats=stats)

@app.route('/api/markets')
def api_markets():
    config = load_config()
    if not config:
        return jsonify({'error': 'Configuration not loaded'}), 500
    
    return jsonify(config.get('markets', []))

@app.route('/api/vehicles')
def api_vehicles():
    market = request.args.get('market', 'UK')
    config = load_config()
    
    if not config:
        return jsonify({'error': 'Configuration not loaded'}), 500
    
    if market not in config.get('availability', {}):
        return jsonify({'error': f'Market {market} not found'}), 404
    
    vehicles = config['availability'][market].get('vehicles', [])
    
    pricing_data = config.get('pricing', {}).get(market, {})
    vehicle_list = []
    
    for vehicle_id in vehicles:
        base_price = get_vehicle_base_price(vehicle_id, pricing_data)
        vehicle_list.append({
            'id': vehicle_id,
            'basePrice': base_price,
            'basePriceFormatted': format_price(base_price, market)
        })
    
    return jsonify(vehicle_list)

@app.route('/api/features')
def api_features():
    market = request.args.get('market', 'UK')
    config = load_config()
    
    if not config:
        return jsonify({'error': 'Configuration not loaded'}), 500
    
    if market not in config.get('availability', {}):
        return jsonify({'error': f'Market {market} not found'}), 404
    
    return jsonify(config['availability'][market].get('features', []))

@app.route('/api/availability')
def api_availability():
    market = request.args.get('market', 'UK')
    vehicle_id = request.args.get('vehicle')
    
    config = load_config()
    
    if not config:
        return jsonify({'error': 'Configuration not loaded'}), 500
    
    if market not in config.get('availability', {}):
        return jsonify({'error': f'Market {market} not found'}), 404
    
    avail_data = config['availability'][market]
    
    if vehicle_id:
        features = []
        matrix = avail_data.get('matrix', {})
        for feature, vehicles in matrix.items():
            status = vehicles.get(vehicle_id, 'NA')
            features.append({
                'feature': feature,
                'status': status
            })
        return jsonify({'vehicle': vehicle_id, 'features': features})
    
    return jsonify(avail_data.get('matrix', {}))

@app.route('/api/pricing')
def api_pricing():
    market = request.args.get('market', 'UK')
    vehicle_id = request.args.get('vehicle')
    
    config = load_config()
    
    if not config:
        return jsonify({'error': 'Configuration not loaded'}), 500
    
    if market not in config.get('pricing', {}):
        return jsonify({'error': f'Market {market} not found'}), 404
    
    pricing_data = config['pricing'][market]
    
    if vehicle_id:
        base_price = get_vehicle_base_price(vehicle_id, pricing_data)
        feature_prices = {}
        
        for feature, vehicles in pricing_data.get('featurePrices', {}).items():
            price = vehicles.get(vehicle_id)
            if price != 'NA' and price is not None:
                feature_prices[feature] = {
                    'price': price,
                    'formatted': format_price(price, market)
                }
        
        return jsonify({
            'vehicle': vehicle_id,
            'basePrice': base_price,
            'basePriceFormatted': format_price(base_price, market),
            'featurePrices': feature_prices,
            'currencySymbol': get_currency_symbol(market)
        })
    
    return jsonify(pricing_data)

@app.route('/api/tech')
def api_tech():
    vehicle_id = request.args.get('vehicle')
    
    config = load_config()
    
    if not config:
        return jsonify({'error': 'Configuration not loaded'}), 500
    
    tech_data = config.get('tech', {})
    
    if vehicle_id:
        specs = get_vehicle_specs(vehicle_id, tech_data)
        highlights = get_key_highlights(vehicle_id, tech_data)
        
        return jsonify({
            'vehicle': vehicle_id,
            'specs': specs,
            'highlights': highlights
        })
    
    return jsonify(tech_data)

@app.route('/api/author/upload', methods=['POST'])
def api_author_upload():
    if not is_author():
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': 'Only .xlsx files are allowed'}), 400
    
    try:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)
        
        file_type = detect_file_type(filename)
        
        if not file_type:
            return jsonify({
                'error': 'Could not detect file type',
                'hint': 'Filename should contain: availability/dummy, pricing, or technical/tech'
            }), 400
        
        config = load_config()
        if not config:
            return jsonify({'error': 'Could not load current configuration'}), 500
        
        config = ensure_metadata(config)
        
        logs = []
        warnings = []
        
        if file_type == 'availability':
            market = extract_market_from_filename(filename)
            if not market:
                return jsonify({'error': 'Could not detect market from filename. Include UK, EU, or US in filename.'}), 400
            
            parsed = parse_availability_file(filepath)
            
            if market not in config['availability']:
                config['availability'][market] = {}
            
            config['availability'][market] = parsed
            logs.append(f"Parsed availability data for {market}: {len(parsed['features'])} features, {len(parsed['vehicles'])} vehicles")
        
        elif file_type == 'pricing':
            market = extract_market_from_filename(filename)
            if not market:
                return jsonify({'error': 'Could not detect market from filename. Include UK, EU, or US in filename.'}), 400
            
            parsed = parse_pricing_file(filepath, market)
            
            if market not in config['pricing']:
                config['pricing'][market] = {}
            
            config['pricing'][market] = parsed
            logs.append(f"Parsed pricing data for {market}: {len(parsed['vehicles'])} vehicles, {len(parsed['featurePrices'])} features")
        
        elif file_type == 'tech':
            parsed = parse_tech_file(filepath)
            config['tech'] = parsed
            logs.append(f"Parsed technical data: {len(parsed['engines'])} engines, {len(parsed['params'])} parameters")
        
        validation = validate_config(config)
        
        config['metadata']['uploadedFiles'].append({
            'filename': saved_filename,
            'originalFilename': filename,
            'type': file_type,
            'uploadedAt': datetime.utcnow().isoformat() + 'Z'
        })
        
        if save_config(config):
            return jsonify({
                'success': True,
                'fileType': file_type,
                'logs': logs,
                'validation': validation
            })
        else:
            return jsonify({'error': 'Failed to save configuration'}), 500
    
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/author/ai-edit', methods=['POST'])
def api_author_ai_edit():
    if not is_author():
        return jsonify({'error': 'Unauthorized'}), 401
    
    global working_config
    
    data = request.get_json()
    instructions = data.get('instructions', '')
    
    if not instructions:
        return jsonify({'error': 'No instructions provided'}), 400
    
    config = load_config()
    if not config:
        return jsonify({'error': 'Could not load configuration'}), 500
    
    config = ensure_metadata(config)
    
    result = apply_ai_edit(config, instructions)
    
    if result['success']:
        working_config = result['config']
        
        diff = generate_diff(config, working_config)
        
        return jsonify({
            'success': True,
            'method': result.get('method', 'unknown'),
            'changes': result.get('changes', []),
            'diff': diff,
            'preview': working_config
        })
    else:
        return jsonify({
            'success': False,
            'error': result.get('error', 'Unknown error'),
            'method': result.get('method', 'unknown')
        }), 400

@app.route('/api/author/save', methods=['POST'])
def api_author_save():
    if not is_author():
        return jsonify({'error': 'Unauthorized'}), 401
    
    global working_config
    
    if working_config:
        working_config = ensure_metadata(working_config)
        
        validation = validate_config(working_config)
        if not validation['valid']:
            return jsonify({
                'error': 'Configuration validation failed',
                'errors': validation['errors'],
                'warnings': validation['warnings']
            }), 400
        
        if save_config(working_config):
            working_config = None
            return jsonify({
                'success': True,
                'message': 'Configuration saved successfully',
                'warnings': validation['warnings']
            })
        else:
            return jsonify({'error': 'Failed to save configuration'}), 500
    else:
        return jsonify({'error': 'No working configuration to save'}), 400

@app.route('/api/author/discard', methods=['POST'])
def api_author_discard():
    if not is_author():
        return jsonify({'error': 'Unauthorized'}), 401
    
    global working_config
    working_config = None
    
    return jsonify({'success': True, 'message': 'Working configuration discarded'})

@app.route('/api/author/status')
def api_author_status():
    if not is_author():
        return jsonify({'error': 'Unauthorized'}), 401
    
    config = load_config()
    if not config:
        return jsonify({'error': 'Configuration not loaded'}), 500
    
    config = ensure_metadata(config)
    metadata = config.get('metadata', {})
    
    stats = {
        'markets': {},
        'engines': len(config.get('tech', {}).get('engines', [])),
        'techParams': len(config.get('tech', {}).get('params', []))
    }
    
    for market in config.get('markets', []):
        stats['markets'][market] = {
            'vehicles': len(config['availability'].get(market, {}).get('vehicles', [])),
            'features': len(config['availability'].get(market, {}).get('features', []))
        }
    
    validation = validate_config(config)
    
    return jsonify({
        'metadata': metadata,
        'stats': stats,
        'validation': validation
    })

@app.route('/api')
def api_index():
    endpoints = {
        'Public Endpoints': {
            'GET /api/markets': 'Get list of available markets',
            'GET /api/vehicles?market=UK': 'Get vehicles for a market',
            'GET /api/features?market=UK': 'Get features for a market',
            'GET /api/availability?market=UK&vehicle=...': 'Get availability matrix',
            'GET /api/pricing?market=UK&vehicle=...': 'Get pricing information',
            'GET /api/tech?vehicle=...': 'Get technical specifications'
        },
        'Author Endpoints (requires authentication)': {
            'POST /api/author/upload': 'Upload Excel file',
            'POST /api/author/ai-edit': 'Apply AI-powered edits',
            'POST /api/author/save': 'Save working configuration',
            'POST /api/author/discard': 'Discard working configuration',
            'GET /api/author/status': 'Get data status and validation'
        }
    }
    
    return render_template('api_docs.html', endpoints=endpoints)

@app.template_filter('format_datetime')
def format_datetime(value):
    if not value:
        return 'Never'
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except:
        return value

if __name__ == '__main__':
    os.makedirs('data/uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
