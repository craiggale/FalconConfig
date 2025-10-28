def validate_config(config):
    warnings = []
    errors = []
    
    markets = config.get('markets', [])
    availability = config.get('availability', {})
    pricing = config.get('pricing', {})
    tech = config.get('tech', {})
    
    for market in markets:
        if market not in availability:
            warnings.append(f"Market '{market}' missing from availability data")
        if market not in pricing:
            warnings.append(f"Market '{market}' missing from pricing data")
    
    for market in markets:
        if market in availability and market in pricing:
            avail_vehicles = set(availability[market].get('vehicles', []))
            price_vehicle_ids = set([v['id'] for v in pricing[market].get('vehicles', [])])
            
            if avail_vehicles != price_vehicle_ids:
                missing_in_pricing = avail_vehicles - price_vehicle_ids
                missing_in_avail = price_vehicle_ids - avail_vehicles
                
                if missing_in_pricing:
                    warnings.append(f"Market '{market}': Vehicles in availability but not pricing: {missing_in_pricing}")
                if missing_in_avail:
                    warnings.append(f"Market '{market}': Vehicles in pricing but not availability: {missing_in_avail}")
            
            avail_features = set(availability[market].get('features', []))
            price_features = set(pricing[market].get('featurePrices', {}).keys())
            
            if avail_features != price_features:
                missing_in_pricing = avail_features - price_features
                missing_in_avail = price_features - avail_features
                
                if missing_in_pricing:
                    warnings.append(f"Market '{market}': Features in availability but not pricing: {missing_in_pricing}")
                if missing_in_avail:
                    warnings.append(f"Market '{market}': Features in pricing but not availability: {missing_in_avail}")
    
    for market in markets:
        if market in pricing:
            vehicles = pricing[market].get('vehicles', [])
            for vehicle in vehicles:
                if 'basePrice' not in vehicle:
                    errors.append(f"Market '{market}': Vehicle '{vehicle.get('id', 'unknown')}' missing basePrice")
                elif not isinstance(vehicle['basePrice'], (int, float)):
                    errors.append(f"Market '{market}': Vehicle '{vehicle.get('id', 'unknown')}' has invalid basePrice")
    
    for market in markets:
        if market in availability and market in pricing:
            matrix = availability[market].get('matrix', {})
            feature_prices = pricing[market].get('featurePrices', {})
            
            for feature, vehicles in matrix.items():
                for vehicle_id, status in vehicles.items():
                    if status == 'S':
                        if feature in feature_prices:
                            price = feature_prices[feature].get(vehicle_id)
                            if price not in [0, 0.0, 'NA', None]:
                                warnings.append(f"Market '{market}': Feature '{feature}' is Standard for '{vehicle_id}' but has price {price}")
                    
                    elif status == 'NA':
                        if feature in feature_prices:
                            price = feature_prices[feature].get(vehicle_id)
                            if price != 'NA' and price is not None:
                                warnings.append(f"Market '{market}': Feature '{feature}' is NA for '{vehicle_id}' but has price {price}")
    
    tech_engines = set(tech.get('engines', []))
    all_vehicles = set()
    for market in markets:
        if market in availability:
            all_vehicles.update(availability[market].get('vehicles', []))
    
    vehicle_engines = set()
    for vehicle in all_vehicles:
        parts = vehicle.split('|')
        if len(parts) >= 2:
            vehicle_engines.add(parts[1].strip())
    
    missing_engines = vehicle_engines - tech_engines
    if missing_engines:
        warnings.append(f"Engines referenced in vehicles but missing from tech data: {missing_engines}")
    
    return {
        'valid': len(errors) == 0,
        'warnings': warnings,
        'errors': errors
    }

def validate_base_price_exists(pricing_data):
    for vehicle in pricing_data.get('vehicles', []):
        if 'basePrice' not in vehicle:
            return False
    return True
