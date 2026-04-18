import numpy as np
import joblib
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'demand_forecast_model.pkl')

_cached_model = None


def load_model():
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model not found. Please train the model first.")
    data = joblib.load(MODEL_PATH)
    _cached_model = data
    return data


def get_model_metrics():
    try:
        data = load_model()
        return data['metrics']
    except Exception as e:
        return {'error': str(e)}


def forecast_product_by_name(product_name, db_session, Purchase, Product, steps=30, base_price=None):
    """Forecast demand for a product identified by name (fuzzy match)."""
    from sqlalchemy import func
    product = None
    products_all = Product.query.all()
    name_lower = product_name.lower().strip()
    for p in products_all:
        if name_lower in p.name.lower() or p.name.lower() in name_lower:
            product = p
            break
    if product is None:
        # Use pure ML forecast with baseline history
        sales_history = []
        price_used = base_price or 500.0
        prod_name = product_name
    else:
        purchases = Purchase.query.filter_by(product_id=product.id).order_by(Purchase.purchase_date.asc()).all()
        sales_history = [p.quantity for p in purchases]
        price_used = product.unit_price
        prod_name = product.name

    forecasts, metrics = forecast_demand(sales_history, steps=steps)

    price_forecasts = [round(qty * price_used, 2) for qty in forecasts]

    return {
        'product_name': prod_name,
        'product_found': product is not None,
        'forecasts': forecasts,
        'price_forecasts': price_forecasts,
        'unit_price': price_used,
        'sales_history': sales_history[-30:] if len(sales_history) > 30 else sales_history,
        'metrics': metrics
    }


def forecast_demand(product_sales_history, steps=30):
    data = load_model()
    model = data['regressor']
    metrics = data['metrics']

    history = list(product_sales_history)
    if len(history) < 30:
        avg = float(np.mean(history)) if history else 52.0
        noise = np.random.uniform(-5, 5, 30 - len(history))
        history = list(avg + noise) + history

    forecasts = []
    for step in range(steps):
        current_idx = len(history)
        lag_1 = history[-1]
        lag_7 = history[-7] if len(history) >= 7 else np.mean(history)
        lag_30 = history[-30] if len(history) >= 30 else np.mean(history)
        w7 = history[-7:] if len(history) >= 7 else history
        w30 = history[-30:] if len(history) >= 30 else history
        rolling_mean_7 = float(np.mean(w7))
        rolling_mean_30 = float(np.mean(w30))
        rolling_std_7 = float(np.std(w7)) if len(w7) > 1 else 0.0
        day_of_week = current_idx % 7
        week_of_month = (current_idx // 7) % 4
        month_cycle = (current_idx // 30) % 12
        trend = current_idx

        features = np.array([[
            current_idx, lag_1, lag_7, lag_30,
            rolling_mean_7, rolling_mean_30, rolling_std_7,
            day_of_week, week_of_month, month_cycle, trend
        ]])
        pred = float(model.predict(features)[0])
        noise = np.random.uniform(-2, 2)
        pred = max(0, round(pred + noise, 2))
        forecasts.append(pred)
        history.append(pred)

    return forecasts, metrics
