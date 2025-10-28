import pandas as pd
import json
from datetime import datetime
import os

def parse_availability_file(file_path):
    df = pd.read_excel(file_path, engine='openpyxl')
    
    features = df.iloc[:, 0].tolist()
    features = [f for f in features if pd.notna(f) and f != '']
    
    vehicles = df.columns[1:].tolist()
    
    matrix = {}
    for idx, feature in enumerate(features):
        matrix[feature] = {}
        for vehicle in vehicles:
            value = df.iloc[idx][vehicle]
            if pd.notna(value):
                matrix[feature][vehicle] = str(value).strip()
            else:
                matrix[feature][vehicle] = "NA"
    
    return {
        "features": features,
        "vehicles": vehicles,
        "matrix": matrix
    }

def parse_pricing_file(file_path, market):
    df = pd.read_excel(file_path, engine='openpyxl')
    
    vehicles = []
    feature_prices = {}
    
    for col in df.columns[1:]:
        base_price_row = df[df.iloc[:, 0] == 'Base Price']
        if not base_price_row.empty:
            base_price = base_price_row[col].values[0]
            if pd.notna(base_price):
                vehicles.append({
                    "id": col,
                    "basePrice": float(base_price) if isinstance(base_price, (int, float)) else 0
                })
    
    for idx, row in df.iterrows():
        feature_name = row.iloc[0]
        if pd.notna(feature_name) and feature_name != 'Base Price':
            feature_prices[feature_name] = {}
            for col in df.columns[1:]:
                value = row[col]
                if pd.notna(value):
                    try:
                        feature_prices[feature_name][col] = float(value)
                    except:
                        feature_prices[feature_name][col] = "NA"
                else:
                    feature_prices[feature_name][col] = "NA"
    
    return {
        "vehicles": vehicles,
        "featurePrices": feature_prices
    }

def parse_tech_file(file_path):
    df = pd.read_excel(file_path, engine='openpyxl')
    
    engines = df.columns[1:].tolist()
    params = df.iloc[:, 0].tolist()
    params = [p for p in params if pd.notna(p) and p != '']
    
    table = {}
    for idx, param in enumerate(params):
        table[param] = {}
        for engine in engines:
            value = df.iloc[idx][engine]
            if pd.notna(value):
                table[param][engine] = str(value)
            else:
                table[param][engine] = "N/A"
    
    return {
        "engines": engines,
        "params": params,
        "table": table
    }

def detect_file_type(filename):
    filename_lower = filename.lower()
    if 'availability' in filename_lower or 'dummy' in filename_lower:
        return 'availability'
    elif 'pricing' in filename_lower:
        return 'pricing'
    elif 'technical' in filename_lower or 'tech' in filename_lower:
        return 'tech'
    return None

def extract_market_from_filename(filename):
    filename_upper = filename.upper()
    if 'UK' in filename_upper:
        return 'UK'
    elif 'EU' in filename_upper:
        return 'EU'
    elif 'US' in filename_upper or 'USA' in filename_upper:
        return 'US'
    return None
