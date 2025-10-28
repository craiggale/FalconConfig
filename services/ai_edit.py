import os
import json
import re

def apply_ai_edit_openai(config, instructions):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        system_prompt = """You are a configuration editor for a vehicle configurator system. 
You will receive a JSON configuration and natural language instructions to modify it.
You must return ONLY valid JSON that represents the modified configuration.
Do not include any explanatory text, only the JSON output.

The configuration has this structure:
- markets: list of market codes (UK, EU, US)
- availability: per-market feature availability matrix (S=Standard, O=Optional, NA=Not Available)
- pricing: per-market base prices and feature prices
- tech: technical specifications by engine
- metadata: system metadata

Common edit patterns:
- "set [feature] to [S|O|NA] for [market] [vehicle/trim]" - change availability
- "increase/decrease [price type] by [amount] for [market] [vehicle]" - adjust pricing
- "add/remove [feature]" - modify feature list
- "change [spec] for [engine] to [value]" - update technical specs"""
        
        user_prompt = f"""Current configuration:
{json.dumps(config, indent=2)}

Instructions: {instructions}

Return the modified configuration as valid JSON."""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        result_text = response.choices[0].message.content.strip()
        
        json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group(1)
        elif result_text.startswith('```') and result_text.endswith('```'):
            result_text = result_text[3:-3].strip()
        
        modified_config = json.loads(result_text)
        
        return {
            'success': True,
            'config': modified_config,
            'method': 'openai'
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'method': 'openai'
        }

def apply_ai_edit_stub(config, instructions):
    import copy
    modified_config = copy.deepcopy(config)
    
    instructions_lower = instructions.lower()
    applied_changes = []
    
    set_pattern = r'set\s+(.+?)\s+to\s+(s|o|na)\s+for\s+(uk|eu|us)\s+(.+?)(?:\s|$)'
    set_match = re.search(set_pattern, instructions_lower, re.IGNORECASE)
    
    if set_match:
        feature = set_match.group(1).strip()
        status = set_match.group(2).upper()
        market = set_match.group(3).upper()
        vehicle_pattern = set_match.group(4).strip()
        
        feature_capitalized = feature.title()
        
        if market in modified_config.get('availability', {}):
            avail_data = modified_config['availability'][market]
            matrix = avail_data.get('matrix', {})
            
            matching_features = [f for f in matrix.keys() if feature.lower() in f.lower()]
            if matching_features:
                feature = matching_features[0]
            else:
                feature = feature_capitalized
            
            if feature in matrix:
                for vehicle_id in matrix[feature].keys():
                    if vehicle_pattern in vehicle_id.lower() or 'all' in vehicle_pattern:
                        matrix[feature][vehicle_id] = status
                        applied_changes.append(f"Set '{feature}' to '{status}' for '{vehicle_id}' in {market}")
        
        return {
            'success': True,
            'config': modified_config,
            'changes': applied_changes,
            'method': 'stub'
        }
    
    price_pattern = r'(increase|decrease)\s+(.+?)\s+(?:price|by)\s+.*?(\d+)\s+for\s+(uk|eu|us)\s+(.+?)(?:\s|$)'
    price_match = re.search(price_pattern, instructions_lower, re.IGNORECASE)
    
    if price_match:
        action = price_match.group(1)
        price_type = price_match.group(2).strip()
        amount = float(price_match.group(3))
        market = price_match.group(4).upper()
        vehicle_pattern = price_match.group(5).strip()
        
        if action == 'decrease':
            amount = -amount
        
        if market in modified_config.get('pricing', {}):
            pricing_data = modified_config['pricing'][market]
            
            if 'base' in price_type:
                for vehicle in pricing_data.get('vehicles', []):
                    if vehicle_pattern in vehicle['id'].lower() or 'all' in vehicle_pattern:
                        vehicle['basePrice'] += amount
                        applied_changes.append(f"{action.capitalize()}d base price by {abs(amount)} for '{vehicle['id']}' in {market}")
            
            else:
                feature_prices = pricing_data.get('featurePrices', {})
                for feature, vehicles in feature_prices.items():
                    for vehicle_id, price in vehicles.items():
                        if isinstance(price, (int, float)) and (vehicle_pattern in vehicle_id.lower() or 'all' in vehicle_pattern):
                            vehicles[vehicle_id] += amount
                            applied_changes.append(f"{action.capitalize()}d '{feature}' price by {abs(amount)} for '{vehicle_id}' in {market}")
        
        return {
            'success': True,
            'config': modified_config,
            'changes': applied_changes,
            'method': 'stub'
        }
    
    return {
        'success': False,
        'error': 'Could not parse instructions. Try patterns like: "set [feature] to O for UK [vehicle]" or "increase base price by 500 for US Sport"',
        'method': 'stub',
        'changes': []
    }

def apply_ai_edit(config, instructions):
    if os.getenv('OPENAI_API_KEY'):
        return apply_ai_edit_openai(config, instructions)
    else:
        return apply_ai_edit_stub(config, instructions)

def generate_diff(original, modified):
    diff = []
    
    def compare_dicts(path, orig, mod):
        all_keys = set(list(orig.keys()) + list(mod.keys()))
        for key in all_keys:
            new_path = f"{path}.{key}" if path else key
            
            if key not in orig:
                diff.append(f"+ ADDED {new_path}: {mod[key]}")
            elif key not in mod:
                diff.append(f"- REMOVED {new_path}: {orig[key]}")
            elif orig[key] != mod[key]:
                if isinstance(orig[key], dict) and isinstance(mod[key], dict):
                    compare_dicts(new_path, orig[key], mod[key])
                elif isinstance(orig[key], list) and isinstance(mod[key], list):
                    if orig[key] != mod[key]:
                        diff.append(f"~ MODIFIED {new_path}: {orig[key]} → {mod[key]}")
                else:
                    diff.append(f"~ MODIFIED {new_path}: {orig[key]} → {mod[key]}")
    
    if isinstance(original, dict) and isinstance(modified, dict):
        compare_dicts("", original, modified)
    else:
        diff.append(f"Complete replacement: {original} → {modified}")
    
    return diff
