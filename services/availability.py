def get_feature_status(feature, vehicle_id, availability_data):
    matrix = availability_data.get('matrix', {})
    if feature in matrix:
        return matrix[feature].get(vehicle_id, 'NA')
    return 'NA'

def get_available_features(vehicle_id, availability_data):
    matrix = availability_data.get('matrix', {})
    available = []
    
    for feature, vehicles in matrix.items():
        status = vehicles.get(vehicle_id, 'NA')
        if status in ['S', 'O']:
            available.append({
                'feature': feature,
                'status': status
            })
    
    return available

def get_selectable_features(vehicle_id, availability_data):
    matrix = availability_data.get('matrix', {})
    selectable = []
    
    for feature, vehicles in matrix.items():
        status = vehicles.get(vehicle_id, 'NA')
        if status == 'O':
            selectable.append(feature)
    
    return selectable

def validate_feature_selection(feature, vehicle_id, availability_data):
    status = get_feature_status(feature, vehicle_id, availability_data)
    if status == 'S':
        return {'valid': False, 'reason': 'Feature is standard (cannot be deselected)'}
    elif status == 'NA':
        return {'valid': False, 'reason': 'Feature is not available for this vehicle'}
    elif status == 'O':
        return {'valid': True, 'reason': 'Feature is optional'}
    return {'valid': False, 'reason': 'Unknown status'}
