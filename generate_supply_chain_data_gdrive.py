"""
Synthetic Supply Chain Data Generator with Google Drive Integration
Generates realistic multi-tier supply chain data and uploads to Google Drive
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import io

np.random.seed(42)

# =============================================================================
# CONFIGURATION
# =============================================================================
CONFIG = {
    'n_days': 730,  # 2 years
    'start_date': '2023-01-01',
    'n_suppliers': 30,
    'n_plants': 5,
    'n_dcs': 10,
    'n_stores': 50,
    'n_skus': 200,
    'n_categories': 15,
    'n_carriers': 8,
    # Realism knobs
    'supplier_delay_prob': 0.15,
    'stockout_threshold': 0.1,
    'missing_data_rate': 0.05,
    'duplicate_rate': 0.02,
    # Storage config
    'save_local': False,  # Set True to also save locally
    'local_dir': 'supply_chain_data',
    'gdrive_folder_id': None,  # Set your Google Drive folder ID
}

# =============================================================================
# GOOGLE DRIVE SETUP
# =============================================================================

def setup_gdrive():
    """Authenticate and return Google Drive instance"""
    try:
        from pydrive2.auth import GoogleAuth
        from pydrive2.drive import GoogleDrive
    except ImportError:
        print("Install pydrive2: pip install pydrive2")
        return None
    
    gauth = GoogleAuth()
    
    # Try to load saved credentials
    gauth.LoadCredentialsFile("gdrive_credentials.json")
    
    if gauth.credentials is None:
        # First time: opens browser for auth
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    
    # Save credentials for next time
    gauth.SaveCredentialsFile("gdrive_credentials.json")
    
    return GoogleDrive(gauth)


def create_gdrive_folder(drive, folder_name, parent_id=None):
    """Create a folder in Google Drive, return folder ID"""
    metadata = {
        'title': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_id:
        metadata['parents'] = [{'id': parent_id}]
    
    folder = drive.CreateFile(metadata)
    folder.Upload()
    print(f"Created folder: {folder_name} (ID: {folder['id']})")
    return folder['id']


def upload_df_to_gdrive(drive, df, filename, folder_id):
    """Upload DataFrame as CSV to Google Drive"""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    
    metadata = {'title': filename}
    if folder_id:
        metadata['parents'] = [{'id': folder_id}]
    
    file = drive.CreateFile(metadata)
    file.SetContentString(buffer.getvalue())
    file.Upload()
    return file['id']


# =============================================================================
# MASTER DATA TABLES
# =============================================================================

def generate_suppliers(cfg):
    n = cfg['n_suppliers']
    regions = ['APAC', 'EMEA', 'AMER', 'LATAM']
    
    return pd.DataFrame({
        'supplier_id': [f'SUP_{i:03d}' for i in range(n)],
        'supplier_name': [f'Supplier_{i}' for i in range(n)],
        'region': np.random.choice(regions, n, p=[0.35, 0.25, 0.30, 0.10]),
        'lead_time_days': np.random.randint(7, 60, n),
        'lead_time_std': np.random.randint(1, 10, n),
        'reliability_score': np.round(np.random.beta(8, 2, n), 3),
        'unit_cost_multiplier': np.round(np.random.uniform(0.8, 1.3, n), 2),
        'min_order_qty': np.random.choice([100, 250, 500, 1000], n),
        'payment_terms_days': np.random.choice([30, 45, 60, 90], n),
    })


def generate_products(cfg):
    n = cfg['n_skus']
    categories = [f'CAT_{i:02d}' for i in range(cfg['n_categories'])]
    
    df = pd.DataFrame({
        'sku': [f'SKU_{i:04d}' for i in range(n)],
        'product_name': [f'Product_{i}' for i in range(n)],
        'category': np.random.choice(categories, n),
        'unit_cost': np.round(np.random.lognormal(3, 1, n), 2),
        'unit_weight_kg': np.round(np.random.lognormal(0, 1, n), 2),
        'shelf_life_days': np.random.choice([None, 30, 60, 90, 180, 365], n, 
                                            p=[0.4, 0.1, 0.15, 0.15, 0.1, 0.1]),
        'is_hazardous': np.random.choice([True, False], n, p=[0.05, 0.95]),
        'abc_class': np.random.choice(['A', 'B', 'C'], n, p=[0.2, 0.3, 0.5]),
    })
    df['unit_price'] = np.round(df['unit_cost'] * np.random.uniform(1.3, 2.5, n), 2)
    df['safety_stock_days'] = np.where(df['abc_class'] == 'A', 14, 
                                       np.where(df['abc_class'] == 'B', 21, 30))
    return df


def generate_locations(cfg):
    plants = pd.DataFrame({
        'location_id': [f'PLANT_{i:02d}' for i in range(cfg['n_plants'])],
        'location_type': 'PLANT',
        'location_name': [f'Plant_{i}' for i in range(cfg['n_plants'])],
        'region': np.random.choice(['AMER', 'EMEA', 'APAC'], cfg['n_plants']),
        'capacity_units_per_day': np.random.randint(5000, 20000, cfg['n_plants']),
        'operating_cost_per_day': np.random.randint(10000, 50000, cfg['n_plants']),
    })
    
    dcs = pd.DataFrame({
        'location_id': [f'DC_{i:02d}' for i in range(cfg['n_dcs'])],
        'location_type': 'DC',
        'location_name': [f'DistCenter_{i}' for i in range(cfg['n_dcs'])],
        'region': np.random.choice(['AMER', 'EMEA', 'APAC'], cfg['n_dcs']),
        'capacity_units_per_day': np.random.randint(10000, 50000, cfg['n_dcs']),
        'operating_cost_per_day': np.random.randint(5000, 25000, cfg['n_dcs']),
    })
    
    stores = pd.DataFrame({
        'location_id': [f'STORE_{i:03d}' for i in range(cfg['n_stores'])],
        'location_type': 'STORE',
        'location_name': [f'Store_{i}' for i in range(cfg['n_stores'])],
        'region': np.random.choice(['AMER', 'EMEA', 'APAC'], cfg['n_stores'], 
                                   p=[0.5, 0.3, 0.2]),
        'capacity_units_per_day': np.random.randint(500, 2000, cfg['n_stores']),
        'operating_cost_per_day': np.random.randint(1000, 5000, cfg['n_stores']),
    })
    
    return pd.concat([plants, dcs, stores], ignore_index=True)


def generate_carriers(cfg):
    n = cfg['n_carriers']
    return pd.DataFrame({
        'carrier_id': [f'CARR_{i:02d}' for i in range(n)],
        'carrier_name': [f'Carrier_{i}' for i in range(n)],
        'mode': np.random.choice(['TRUCK', 'RAIL', 'AIR', 'OCEAN'], n, 
                                 p=[0.5, 0.2, 0.15, 0.15]),
        'cost_per_kg_km': np.round(np.random.uniform(0.001, 0.05, n), 4),
        'avg_transit_days': np.random.randint(1, 14, n),
        'on_time_rate': np.round(np.random.beta(9, 1, n), 3),
    })


def generate_supplier_product_mapping(suppliers, products):
    rows = []
    for sku in products['sku']:
        n_suppliers = np.random.randint(1, 4)
        selected = np.random.choice(suppliers['supplier_id'], n_suppliers, replace=False)
        for i, sup in enumerate(selected):
            rows.append({
                'sku': sku,
                'supplier_id': sup,
                'is_primary': i == 0,
                'supplier_sku': f'{sup}_{sku}',
            })
    return pd.DataFrame(rows)


# =============================================================================
# TRANSACTIONAL DATA
# =============================================================================

def generate_demand_and_sales(cfg, products, locations):
    dates = pd.date_range(cfg['start_date'], periods=cfg['n_days'])
    stores = locations[locations['location_type'] == 'STORE']['location_id'].values
    skus = products['sku'].values
    
    grid = pd.MultiIndex.from_product([dates, stores, skus], 
                                       names=['date', 'store_id', 'sku'])
    df = pd.DataFrame(index=grid).reset_index()
    
    abc_map = products.set_index('sku')['abc_class'].to_dict()
    df['abc_class'] = df['sku'].map(abc_map)
    base_demand = {'A': 50, 'B': 20, 'C': 8}
    df['base_demand'] = df['abc_class'].map(base_demand)
    
    df['day_of_year'] = df['date'].dt.dayofyear
    df['day_of_week'] = df['date'].dt.dayofweek
    df['seasonality'] = (
        1 + 0.3 * np.sin(2 * np.pi * df['day_of_year'] / 365) +
        0.1 * np.sin(2 * np.pi * df['day_of_week'] / 7)
    )
    
    holiday_dates = pd.to_datetime(['2023-11-24', '2023-12-25', '2024-11-29', '2024-12-25'])
    df['is_holiday_period'] = df['date'].isin(
        pd.date_range(start=holiday_dates[0] - timedelta(7), end=holiday_dates[0] + timedelta(3)).tolist() +
        pd.date_range(start=holiday_dates[1] - timedelta(7), end=holiday_dates[1]).tolist() +
        pd.date_range(start=holiday_dates[2] - timedelta(7), end=holiday_dates[2] + timedelta(3)).tolist() +
        pd.date_range(start=holiday_dates[3] - timedelta(7), end=holiday_dates[3]).tolist()
    )
    df['holiday_multiplier'] = np.where(df['is_holiday_period'], 
                                        np.random.uniform(1.5, 3.0, len(df)), 1.0)
    
    df['is_promo'] = np.random.random(len(df)) < 0.10
    df['promo_lift'] = np.where(df['is_promo'], np.random.uniform(1.3, 2.0, len(df)), 1.0)
    df['trend'] = 1 + 0.0003 * (df['date'] - df['date'].min()).dt.days
    
    df['demand'] = (
        df['base_demand'] * df['seasonality'] * df['holiday_multiplier'] * 
        df['promo_lift'] * df['trend']
    )
    df['demand'] = np.maximum(0, np.random.poisson(df['demand']))
    
    stockout_mask = np.random.random(len(df)) < cfg['stockout_threshold']
    df['units_sold'] = np.where(
        stockout_mask, 
        (df['demand'] * np.random.uniform(0.3, 0.8, len(df))).astype(int),
        df['demand']
    )
    df['stockout_flag'] = stockout_mask & (df['demand'] > df['units_sold'])
    
    price_map = products.set_index('sku')['unit_price'].to_dict()
    df['unit_price'] = df['sku'].map(price_map)
    df['revenue'] = np.round(df['units_sold'] * df['unit_price'] * 
                             np.where(df['is_promo'], 0.85, 1.0), 2)
    
    cols = ['date', 'store_id', 'sku', 'units_sold', 'demand', 'revenue', 
            'is_promo', 'stockout_flag']
    return df[cols]


def generate_demand_forecasts(sales, products):
    sales['week'] = sales['date'].dt.to_period('W').dt.start_time
    weekly = sales.groupby(['week', 'store_id', 'sku']).agg({
        'units_sold': 'sum', 'demand': 'sum'
    }).reset_index()
    
    abc_map = products.set_index('sku')['abc_class'].to_dict()
    weekly['abc_class'] = weekly['sku'].map(abc_map)
    
    error_std = {'A': 0.12, 'B': 0.18, 'C': 0.25}
    weekly['error_std'] = weekly['abc_class'].map(error_std)
    weekly['forecast_error'] = np.random.normal(0, weekly['error_std'])
    weekly['forecast_qty'] = np.maximum(0, 
        np.round(weekly['demand'] * (1 + weekly['forecast_error'])).astype(int))
    weekly['actual_qty'] = weekly['demand']
    
    cols = ['week', 'store_id', 'sku', 'forecast_qty', 'actual_qty']
    return weekly[cols].rename(columns={'week': 'forecast_date'})


def generate_purchase_orders(cfg, suppliers, products, supplier_product_map, sales):
    monthly_demand = sales.groupby([
        sales['date'].dt.to_period('M').dt.start_time, 'sku'
    ])['demand'].sum().reset_index()
    monthly_demand.columns = ['month', 'sku', 'total_demand']
    
    rows = []
    po_id = 0
    
    for _, row in monthly_demand.iterrows():
        sku = row['sku']
        demand = row['total_demand']
        month = row['month']
        
        supplier_row = supplier_product_map[
            (supplier_product_map['sku'] == sku) & (supplier_product_map['is_primary'])
        ]
        if len(supplier_row) == 0:
            continue
        supplier_id = supplier_row.iloc[0]['supplier_id']
        
        sup_data = suppliers[suppliers['supplier_id'] == supplier_id].iloc[0]
        lead_time = sup_data['lead_time_days']
        reliability = sup_data['reliability_score']
        min_qty = sup_data['min_order_qty']
        
        order_qty = max(min_qty, int(np.ceil(demand * 1.1 / min_qty) * min_qty))
        order_date = month
        expected_date = order_date + timedelta(days=int(lead_time))
        
        if np.random.random() > reliability:
            delay = int(np.random.exponential(lead_time * 0.3))
        else:
            delay = int(np.random.normal(0, sup_data['lead_time_std']))
        actual_date = expected_date + timedelta(days=max(0, delay))
        
        if actual_date <= datetime.now():
            status = 'DELIVERED'
        elif order_date <= datetime.now():
            status = 'IN_TRANSIT'
        else:
            status = 'PLANNED'
        
        rows.append({
            'po_id': f'PO_{po_id:06d}',
            'supplier_id': supplier_id,
            'sku': sku,
            'order_qty': order_qty,
            'unit_cost': float(products[products['sku'] == sku]['unit_cost'].iloc[0] * 
                              sup_data['unit_cost_multiplier']),
            'order_date': order_date,
            'expected_date': expected_date,
            'actual_date': actual_date if status == 'DELIVERED' else None,
            'status': status,
            'delay_days': (actual_date - expected_date).days if status == 'DELIVERED' else None,
        })
        po_id += 1
    
    return pd.DataFrame(rows)


def generate_inventory_snapshots(cfg, products, locations, sales, purchase_orders):
    dates = pd.date_range(cfg['start_date'], periods=cfg['n_days'], freq='W')
    all_locations = locations['location_id'].values
    skus = products['sku'].values
    
    rows = []
    for date in dates:
        for loc in all_locations:
            loc_type = locations[locations['location_id'] == loc]['location_type'].iloc[0]
            
            if loc_type == 'STORE':
                loc_skus = np.random.choice(skus, size=int(len(skus) * 0.6), replace=False)
            else:
                loc_skus = skus
            
            for sku in loc_skus:
                abc = products[products['sku'] == sku]['abc_class'].iloc[0]
                base = {'A': 500, 'B': 200, 'C': 100}[abc]
                
                on_hand = max(0, int(base * np.random.lognormal(0, 0.5)))
                in_transit = max(0, int(base * 0.3 * np.random.random()))
                backorder = int(base * 0.1 * np.random.random()) if np.random.random() < 0.1 else 0
                
                rows.append({
                    'snapshot_date': date,
                    'location_id': loc,
                    'sku': sku,
                    'on_hand_qty': on_hand,
                    'in_transit_qty': in_transit,
                    'backorder_qty': backorder,
                    'inventory_value': on_hand * float(products[products['sku'] == sku]['unit_cost'].iloc[0]),
                })
    
    return pd.DataFrame(rows)


def generate_shipments(cfg, locations, carriers, purchase_orders):
    plants = locations[locations['location_type'] == 'PLANT']['location_id'].values
    dcs = locations[locations['location_type'] == 'DC']['location_id'].values
    stores = locations[locations['location_type'] == 'STORE']['location_id'].values
    carrier_ids = carriers['carrier_id'].values
    
    rows = []
    shipment_id = 0
    
    for _, po in purchase_orders[purchase_orders['status'] == 'DELIVERED'].iterrows():
        carrier = np.random.choice(carrier_ids)
        carrier_data = carriers[carriers['carrier_id'] == carrier].iloc[0]
        
        planned = po['expected_date'] - timedelta(days=carrier_data['avg_transit_days'])
        actual = po['actual_date'] - timedelta(days=carrier_data['avg_transit_days']) if po['actual_date'] else None
        
        rows.append({
            'shipment_id': f'SHIP_{shipment_id:07d}',
            'origin': po['supplier_id'],
            'destination': np.random.choice(plants),
            'carrier_id': carrier,
            'sku': po['sku'],
            'qty': po['order_qty'],
            'weight_kg': po['order_qty'] * np.random.uniform(0.5, 5),
            'planned_ship_date': planned,
            'actual_ship_date': actual,
            'planned_delivery_date': po['expected_date'],
            'actual_delivery_date': po['actual_date'],
            'freight_cost': po['order_qty'] * carrier_data['cost_per_kg_km'] * np.random.uniform(100, 1000),
            'status': 'DELIVERED',
        })
        shipment_id += 1
    
    dates = pd.date_range(cfg['start_date'], periods=cfg['n_days'], freq='W')
    for date in dates:
        for _ in range(np.random.randint(5, 15)):
            carrier = np.random.choice(carrier_ids)
            carrier_data = carriers[carriers['carrier_id'] == carrier].iloc[0]
            transit = carrier_data['avg_transit_days']
            
            rows.append({
                'shipment_id': f'SHIP_{shipment_id:07d}',
                'origin': np.random.choice(plants),
                'destination': np.random.choice(dcs),
                'carrier_id': carrier,
                'sku': None,
                'qty': np.random.randint(1000, 10000),
                'weight_kg': np.random.uniform(500, 5000),
                'planned_ship_date': date,
                'actual_ship_date': date + timedelta(days=np.random.randint(-1, 2)),
                'planned_delivery_date': date + timedelta(days=transit),
                'actual_delivery_date': date + timedelta(days=transit + np.random.randint(-2, 5)),
                'freight_cost': np.random.uniform(500, 5000),
                'status': 'DELIVERED' if date < datetime.now() - timedelta(days=transit) else 'IN_TRANSIT',
            })
            shipment_id += 1
        
        for _ in range(np.random.randint(20, 50)):
            carrier = np.random.choice(carrier_ids)
            carrier_data = carriers[carriers['carrier_id'] == carrier].iloc[0]
            transit = max(1, carrier_data['avg_transit_days'] // 2)
            
            rows.append({
                'shipment_id': f'SHIP_{shipment_id:07d}',
                'origin': np.random.choice(dcs),
                'destination': np.random.choice(stores),
                'carrier_id': carrier,
                'sku': None,
                'qty': np.random.randint(100, 1000),
                'weight_kg': np.random.uniform(50, 500),
                'planned_ship_date': date,
                'actual_ship_date': date + timedelta(days=np.random.randint(0, 2)),
                'planned_delivery_date': date + timedelta(days=transit),
                'actual_delivery_date': date + timedelta(days=transit + np.random.randint(-1, 3)),
                'freight_cost': np.random.uniform(50, 500),
                'status': 'DELIVERED' if date < datetime.now() - timedelta(days=transit) else 'IN_TRANSIT',
            })
            shipment_id += 1
    
    return pd.DataFrame(rows)


def generate_production_orders(cfg, products, locations):
    plants = locations[locations['location_type'] == 'PLANT']['location_id'].values
    skus = products['sku'].values
    dates = pd.date_range(cfg['start_date'], periods=cfg['n_days'])
    
    rows = []
    prod_id = 0
    
    for date in dates:
        for plant in plants:
            n_orders = np.random.randint(5, 15)
            for _ in range(n_orders):
                sku = np.random.choice(skus)
                planned_qty = np.random.randint(100, 2000)
                yield_rate = np.random.beta(20, 1)
                actual_qty = int(planned_qty * yield_rate)
                status = np.random.choice(['COMPLETED', 'IN_PROGRESS', 'PLANNED'], 
                                         p=[0.7, 0.2, 0.1])
                
                rows.append({
                    'production_order_id': f'PROD_{prod_id:07d}',
                    'plant_id': plant,
                    'sku': sku,
                    'planned_qty': planned_qty,
                    'actual_qty': actual_qty if status == 'COMPLETED' else None,
                    'planned_date': date,
                    'completion_date': date if status == 'COMPLETED' else None,
                    'yield_rate': yield_rate if status == 'COMPLETED' else None,
                    'status': status,
                })
                prod_id += 1
    
    return pd.DataFrame(rows)


def inject_data_quality_issues(df, cfg, table_name):
    df = df.copy()
    n = len(df)
    
    if cfg['missing_data_rate'] > 0:
        non_key_cols = [c for c in df.columns if not c.endswith('_id') and c != 'sku' and c != 'date']
        for col in non_key_cols:
            mask = np.random.random(n) < cfg['missing_data_rate']
            df.loc[mask, col] = None
    
    if cfg['duplicate_rate'] > 0 and len(df) > 100:
        n_dups = int(n * cfg['duplicate_rate'])
        dup_indices = np.random.choice(df.index, n_dups, replace=False)
        dups = df.loc[dup_indices].copy()
        df = pd.concat([df, dups], ignore_index=True)
    
    return df


# =============================================================================
# MAIN GENERATION
# =============================================================================

def generate_all_data(gdrive_folder_id=None, save_local=False, local_dir='supply_chain_data'):
    """
    Generate complete dataset and upload to Google Drive
    
    Args:
        gdrive_folder_id: Google Drive folder ID (get from URL). If None, creates new folder.
        save_local: Also save locally
        local_dir: Local directory name
    """
    
    # Setup Google Drive
    print("Authenticating with Google Drive...")
    drive = setup_gdrive()
    if drive is None:
        print("Falling back to local storage only")
        save_local = True
        gdrive_folder_id = None
    
    # Create GDrive folder if needed
    if drive and not gdrive_folder_id:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        gdrive_folder_id = create_gdrive_folder(drive, f'supply_chain_data_{timestamp}')
    
    # Create local dir if needed
    if save_local:
        os.makedirs(local_dir, exist_ok=True)
    
    # Generate data
    print("\nGenerating master data...")
    suppliers = generate_suppliers(CONFIG)
    products = generate_products(CONFIG)
    locations = generate_locations(CONFIG)
    carriers = generate_carriers(CONFIG)
    supplier_product_map = generate_supplier_product_mapping(suppliers, products)
    
    print("Generating sales data (this may take a minute)...")
    sales = generate_demand_and_sales(CONFIG, products, locations)
    
    print("Generating forecasts...")
    forecasts = generate_demand_forecasts(sales, products)
    
    print("Generating purchase orders...")
    purchase_orders = generate_purchase_orders(CONFIG, suppliers, products, 
                                               supplier_product_map, sales)
    
    print("Generating inventory snapshots...")
    inventory = generate_inventory_snapshots(CONFIG, products, locations, 
                                             sales, purchase_orders)
    
    print("Generating shipments...")
    shipments = generate_shipments(CONFIG, locations, carriers, purchase_orders)
    
    print("Generating production orders...")
    production = generate_production_orders(CONFIG, products, locations)
    
    # Inject data quality issues
    print("Injecting data quality issues...")
    purchase_orders = inject_data_quality_issues(purchase_orders, CONFIG, 'purchase_orders')
    shipments = inject_data_quality_issues(shipments, CONFIG, 'shipments')
    inventory = inject_data_quality_issues(inventory, CONFIG, 'inventory')
    
    # Prepare tables
    tables = {
        'suppliers': suppliers,
        'products': products,
        'locations': locations,
        'carriers': carriers,
        'supplier_product_map': supplier_product_map,
        'sales': sales,
        'demand_forecasts': forecasts,
        'purchase_orders': purchase_orders,
        'inventory': inventory,
        'shipments': shipments,
        'production_orders': production,
    }
    
    # Upload to Google Drive
    if drive and gdrive_folder_id:
        print(f"\nUploading to Google Drive...")
        for name, df in tables.items():
            file_id = upload_df_to_gdrive(drive, df, f'{name}.csv', gdrive_folder_id)
            print(f"  ✓ {name}.csv ({len(df):,} rows)")
        print(f"\nGoogle Drive folder: https://drive.google.com/drive/folders/{gdrive_folder_id}")
    
    # Save locally
    if save_local:
        print(f"\nSaving to {local_dir}/...")
        for name, df in tables.items():
            df.to_csv(os.path.join(local_dir, f'{name}.csv'), index=False)
            print(f"  {name}: {len(df):,} rows")
    
    print("\n✅ Done!")
    print(f"  Date range: {CONFIG['start_date']} to {CONFIG['n_days']} days")
    print(f"  {CONFIG['n_suppliers']} suppliers, {CONFIG['n_skus']} SKUs")
    print(f"  {CONFIG['n_plants']} plants, {CONFIG['n_dcs']} DCs, {CONFIG['n_stores']} stores")
    
    return tables


if __name__ == '__main__':
    # Option 1: Auto-create new folder in Drive
    tables = generate_all_data()
    
    # Option 2: Upload to specific folder
    # tables = generate_all_data(gdrive_folder_id='YOUR_FOLDER_ID_HERE')
    
    # Option 3: Also save locally
    # tables = generate_all_data(save_local=True, local_dir='supply_chain_data')
    
    # Option 4: Local only (no Drive)
    # tables = generate_all_data(gdrive_folder_id=None, save_local=True)
