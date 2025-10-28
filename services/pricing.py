def get_currency_symbol(market):
    symbols = {
        'UK': '£',
        'EU': '€',
        'US': '$'
    }
    return symbols.get(market, '$')

def format_price(price, market):
    symbol = get_currency_symbol(market)
    if isinstance(price, (int, float)):
        return f"{symbol}{price:,.2f}"
    return f"{symbol}0.00"

def calculate_total_price(base_price, selected_features, feature_prices):
    total = base_price
    options_total = 0
    
    for feature in selected_features:
        if feature in feature_prices:
            price = feature_prices[feature]
            if isinstance(price, (int, float)):
                options_total += price
    
    total = base_price + options_total
    return {
        'basePrice': base_price,
        'optionsPrice': options_total,
        'totalPrice': total
    }

def get_vehicle_base_price(vehicle_id, pricing_data):
    for vehicle in pricing_data.get('vehicles', []):
        if vehicle['id'] == vehicle_id:
            return vehicle.get('basePrice', 0)
    return 0

def get_feature_price(feature, vehicle_id, pricing_data):
    feature_prices = pricing_data.get('featurePrices', {})
    if feature in feature_prices:
        price = feature_prices[feature].get(vehicle_id, 'NA')
        if price == 'NA':
            return None
        return price
    return None
