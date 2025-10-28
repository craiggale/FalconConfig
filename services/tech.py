def extract_engine_from_vehicle(vehicle_id):
    parts = vehicle_id.split('|')
    if len(parts) >= 2:
        return parts[1].strip()
    return None

def get_engine_specs(engine, tech_data):
    table = tech_data.get('table', {})
    specs = {}
    
    for param, engines in table.items():
        if engine in engines:
            specs[param] = engines[engine]
    
    return specs

def get_vehicle_specs(vehicle_id, tech_data):
    engine = extract_engine_from_vehicle(vehicle_id)
    if not engine:
        return {}
    
    return get_engine_specs(engine, tech_data)

def convert_speed_to_mph(kmh):
    try:
        return float(kmh) * 0.621371
    except:
        return None

def convert_weight_to_lb(kg):
    try:
        return float(kg) * 2.20462
    except:
        return None

def get_key_highlights(vehicle_id, tech_data):
    specs = get_vehicle_specs(vehicle_id, tech_data)
    highlights = []
    
    key_params = ['Top Speed (km/h)', '0-100 km/h (s)', 'Power (hp)', 'CO2 Emissions (g/km)']
    
    for param in key_params:
        if param in specs and specs[param] != 'N/A':
            highlights.append({
                'parameter': param,
                'value': specs[param]
            })
    
    return highlights
