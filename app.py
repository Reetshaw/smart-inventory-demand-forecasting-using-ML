import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sqlalchemy import func

from db_config import get_database_uri

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'smart-inventory-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri(basedir)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# ─── ADMIN STATIC CREDENTIALS ────────────────────────────────────────────────
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin'


# ─── MODELS ───────────────────────────────────────────────────────────────────
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    purchases = db.relationship('Purchase', backref='buyer', lazy=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    current_stock = db.Column(db.Integer, default=0)
    reorder_point = db.Column(db.Integer, default=10)
    unit_price = db.Column(db.Float, default=0.0)
    supplier = db.Column(db.String(100))
    description = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    purchases = db.relationship('Purchase', backref='product', lazy=True)

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_point

    @property
    def status(self):
        if self.current_stock == 0:
            return 'out_of_stock'
        elif self.is_low_stock:
            return 'low_stock'
        else:
            return 'in_stock'


class Purchase(db.Model):
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.String(200))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def is_admin():
    return session.get('is_admin', False)


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin', False):
            flash('Admin access required.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def seed_products():
    if Product.query.count() == 0:
        products = [
            Product(name='Rice (Premium Basmati)', category='Grains', sku='RICE001',
                    current_stock=500, reorder_point=50, unit_price=120.0,
                    supplier='Agro Foods Ltd', description='Premium quality basmati rice, 1kg pack'),
            Product(name='Wheat Flour (Atta)', category='Grains', sku='WHT001',
                    current_stock=300, reorder_point=30, unit_price=45.0,
                    supplier='Agro Foods Ltd', description='Fresh milled wheat flour, 5kg pack'),
            Product(name='Cooking Oil (Sunflower)', category='Oils & Fats', sku='OIL001',
                    current_stock=200, reorder_point=20, unit_price=185.0,
                    supplier='Golden Oil Corp', description='Pure refined sunflower oil, 1 litre'),
            Product(name='Sugar', category='Sweeteners', sku='SUG001',
                    current_stock=8, reorder_point=30, unit_price=42.0,
                    supplier='Sweet Mills', description='Refined white sugar, 1kg pack'),
            Product(name='Dal (Toor Dal)', category='Pulses', sku='DAL001',
                    current_stock=150, reorder_point=25, unit_price=155.0,
                    supplier='Pulse Traders', description='Premium toor dal, 1kg pack'),
            Product(name='Tea Powder', category='Beverages', sku='TEA001',
                    current_stock=0, reorder_point=20, unit_price=250.0,
                    supplier='Nilgiri Tea Co', description='Strong Assam tea powder, 500g'),
            Product(name='Salt (Iodised)', category='Condiments', sku='SLT001',
                    current_stock=400, reorder_point=40, unit_price=20.0,
                    supplier='Salt Works', description='Iodised table salt, 1kg pack'),
            Product(name='Turmeric Powder', category='Spices', sku='TRM001',
                    current_stock=80, reorder_point=15, unit_price=95.0,
                    supplier='Spice Garden', description='Pure turmeric powder, 200g pack'),
            Product(name='Red Chilli Powder', category='Spices', sku='CHI001',
                    current_stock=60, reorder_point=15, unit_price=110.0,
                    supplier='Spice Garden', description='Hot red chilli powder, 200g pack'),
            Product(name='Mustard Oil', category='Oils & Fats', sku='OIL002',
                    current_stock=5, reorder_point=20, unit_price=170.0,
                    supplier='Golden Oil Corp', description='Pure kachi ghani mustard oil, 1 litre'),
        ]
        for p in products:
            db.session.add(p)
        db.session.commit()


# ─── LANDING ──────────────────────────────────────────────────────────────────
@app.route('/')
def landing():
    return render_template('landing.html')


# ─── ADMIN AUTH ───────────────────────────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            session['admin_username'] = ADMIN_USERNAME
            flash('Welcome, Admin!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials.', 'danger')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_username', None)
    flash('Admin logged out.', 'info')
    return redirect(url_for('landing'))


# ─── ADMIN DASHBOARD ──────────────────────────────────────────────────────────
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    from forecaster import get_model_metrics
    total_products = Product.query.count()
    total_users = User.query.count()
    total_purchases = Purchase.query.count()
    low_stock = Product.query.filter(Product.current_stock <= Product.reorder_point).count()
    out_of_stock = Product.query.filter(Product.current_stock == 0).count()
    total_revenue = db.session.query(func.sum(Purchase.total_price)).scalar() or 0

    # Recent purchases
    recent_purchases = db.session.query(Purchase, User, Product)\
        .join(User, Purchase.user_id == User.id)\
        .join(Product, Purchase.product_id == Product.id)\
        .order_by(Purchase.purchase_date.desc()).limit(10).all()

    # User purchase summary for chart
    user_purchases = db.session.query(
        User.username,
        func.count(Purchase.id).label('count'),
        func.sum(Purchase.total_price).label('total')
    ).join(Purchase, Purchase.user_id == User.id)\
     .group_by(User.id).all()

    # Category stock chart
    cat_data = db.session.query(
        Product.category,
        func.sum(Product.current_stock).label('total_stock')
    ).group_by(Product.category).all()

    # Purchases by day (last 14 days)
    fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
    daily_purchases = db.session.query(
        func.date(Purchase.purchase_date).label('day'),
        func.count(Purchase.id).label('cnt'),
        func.sum(Purchase.total_price).label('revenue')
    ).filter(Purchase.purchase_date >= fourteen_days_ago)\
     .group_by(func.date(Purchase.purchase_date)).all()

    metrics = get_model_metrics()

    return render_template('admin_dashboard.html',
        total_products=total_products,
        total_users=total_users,
        total_purchases=total_purchases,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        total_revenue=total_revenue,
        recent_purchases=recent_purchases,
        user_purchases=user_purchases,
        cat_data=cat_data,
        daily_purchases=daily_purchases,
        metrics=metrics
    )


# ─── ADMIN INVENTORY MANAGEMENT ───────────────────────────────────────────────
@app.route('/admin/inventory')
@admin_required
def admin_inventory():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    query = Product.query
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    if category:
        query = query.filter_by(category=category)
    products = query.order_by(Product.name).all()
    categories = db.session.query(Product.category).distinct().all()
    return render_template('admin_inventory.html',
        products=products,
        categories=[c[0] for c in categories],
        search=search,
        selected_category=category
    )


@app.route('/admin/product/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        sku = request.form.get('sku', '').strip().upper()
        current_stock = int(request.form.get('current_stock', 0))
        reorder_point = int(request.form.get('reorder_point', 10))
        unit_price = float(request.form.get('unit_price', 0))
        supplier = request.form.get('supplier', '').strip()
        description = request.form.get('description', '').strip()

        if not name or not category or not sku:
            flash('Name, Category and SKU are required.', 'danger')
            return render_template('admin_product_form.html', product=None, action='Add')

        if Product.query.filter_by(sku=sku).first():
            flash('SKU already exists. Please use a unique SKU.', 'danger')
            return render_template('admin_product_form.html', product=None, action='Add')

        p = Product(name=name, category=category, sku=sku,
                    current_stock=current_stock, reorder_point=reorder_point,
                    unit_price=unit_price, supplier=supplier, description=description)
        db.session.add(p)
        db.session.commit()
        flash(f'Product "{name}" added successfully!', 'success')
        return redirect(url_for('admin_inventory'))

    return render_template('admin_product_form.html', product=None, action='Add')


@app.route('/admin/product/edit/<int:pid>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(pid):
    p = Product.query.get_or_404(pid)
    if request.method == 'POST':
        p.name = request.form.get('name', p.name).strip()
        p.category = request.form.get('category', p.category).strip()
        p.sku = request.form.get('sku', p.sku).strip().upper()
        p.current_stock = int(request.form.get('current_stock', p.current_stock))
        p.reorder_point = int(request.form.get('reorder_point', p.reorder_point))
        p.unit_price = float(request.form.get('unit_price', p.unit_price))
        p.supplier = request.form.get('supplier', p.supplier or '').strip()
        p.description = request.form.get('description', p.description or '').strip()
        p.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Product "{p.name}" updated.', 'success')
        return redirect(url_for('admin_inventory'))
    return render_template('admin_product_form.html', product=p, action='Edit')


@app.route('/admin/product/delete/<int:pid>', methods=['POST'])
@admin_required
def admin_delete_product(pid):
    p = Product.query.get_or_404(pid)
    name = p.name
    Purchase.query.filter_by(product_id=pid).delete()
    db.session.delete(p)
    db.session.commit()
    flash(f'Product "{name}" deleted.', 'success')
    return redirect(url_for('admin_inventory'))


# ─── ADMIN: ALL PURCHASES VIEW ────────────────────────────────────────────────
@app.route('/admin/purchases')
@admin_required
def admin_purchases():
    rows = db.session.query(Purchase, User, Product)\
        .join(User, Purchase.user_id == User.id)\
        .join(Product, Purchase.product_id == Product.id)\
        .order_by(Purchase.purchase_date.desc()).all()
    return render_template('admin_purchases.html', rows=rows)


# ─── ADMIN: MODEL METRICS ─────────────────────────────────────────────────────
@app.route('/admin/metrics')
@admin_required
def admin_metrics():
    from forecaster import get_model_metrics
    metrics = get_model_metrics()
    return render_template('admin_metrics.html', metrics=metrics)


# ─── USER AUTH ────────────────────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('user_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('user_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('user_dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('landing'))


# ─── USER DASHBOARD ───────────────────────────────────────────────────────────
@app.route('/user/dashboard')
@login_required
def user_dashboard():
    products = Product.query.filter(Product.current_stock > 0).order_by(Product.name).all()
    recent_purchases = Purchase.query.filter_by(user_id=current_user.id)\
        .order_by(Purchase.purchase_date.desc()).limit(5).all()
    total_spent = db.session.query(func.sum(Purchase.total_price))\
        .filter(Purchase.user_id == current_user.id).scalar() or 0
    total_orders = Purchase.query.filter_by(user_id=current_user.id).count()

    # Category spending chart
    cat_spending = db.session.query(
        Product.category,
        func.sum(Purchase.total_price).label('total')
    ).join(Product, Purchase.product_id == Product.id)\
     .filter(Purchase.user_id == current_user.id)\
     .group_by(Product.category).all()

    return render_template('user_dashboard.html',
        products=products,
        recent_purchases=recent_purchases,
        total_spent=total_spent,
        total_orders=total_orders,
        cat_spending=cat_spending
    )


# ─── USER: SHOP ───────────────────────────────────────────────────────────────
@app.route('/user/shop')
@login_required
def user_shop():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    query = Product.query.filter(Product.current_stock > 0)
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    if category:
        query = query.filter_by(category=category)
    products = query.order_by(Product.name).all()
    categories = db.session.query(Product.category).distinct().all()
    return render_template('user_shop.html',
        products=products,
        categories=[c[0] for c in categories],
        search=search,
        selected_category=category
    )


# ─── USER: PURCHASE ───────────────────────────────────────────────────────────
@app.route('/user/purchase/<int:pid>', methods=['POST'])
@login_required
def user_purchase(pid):
    product = Product.query.get_or_404(pid)
    qty = int(request.form.get('quantity', 1))

    if qty <= 0:
        flash('Quantity must be at least 1.', 'danger')
        return redirect(url_for('user_shop'))
    if product.current_stock < qty:
        flash(f'Not enough stock. Available: {product.current_stock}', 'danger')
        return redirect(url_for('user_shop'))

    total = round(qty * product.unit_price, 2)
    purchase = Purchase(
        user_id=current_user.id,
        product_id=product.id,
        quantity=qty,
        unit_price=product.unit_price,
        total_price=total,
        notes=request.form.get('notes', '')
    )
    product.current_stock -= qty
    product.updated_at = datetime.utcnow()
    db.session.add(purchase)
    db.session.commit()
    flash(f'Purchase successful! {qty}x {product.name} for ₹{total:,.2f}', 'success')
    return redirect(url_for('user_purchase_history'))


# ─── USER: PURCHASE HISTORY ───────────────────────────────────────────────────
@app.route('/user/history')
@login_required
def user_purchase_history():
    purchases = db.session.query(Purchase, Product)\
        .join(Product, Purchase.product_id == Product.id)\
        .filter(Purchase.user_id == current_user.id)\
        .order_by(Purchase.purchase_date.desc()).all()

    total_spent = sum(p.total_price for p, _ in purchases)

    # Monthly spending chart
    monthly = db.session.query(
        func.date_format(Purchase.purchase_date, '%Y-%m').label('month'),
        func.sum(Purchase.total_price).label('total'),
        func.count(Purchase.id).label('orders')
    ).filter(Purchase.user_id == current_user.id)\
     .group_by(func.date_format(Purchase.purchase_date, '%Y-%m'))\
     .order_by('month').all()

    # Category breakdown
    cat_breakdown = db.session.query(
        Product.category,
        func.sum(Purchase.quantity).label('qty'),
        func.sum(Purchase.total_price).label('total')
    ).join(Product, Purchase.product_id == Product.id)\
     .filter(Purchase.user_id == current_user.id)\
     .group_by(Product.category).all()

    return render_template('user_history.html',
        purchases=purchases,
        total_spent=total_spent,
        monthly=monthly,
        cat_breakdown=cat_breakdown
    )


# ─── FORECAST (USER) ──────────────────────────────────────────────────────────
@app.route('/forecast', methods=['GET', 'POST'])
@login_required
def forecast():
    result = None
    error = None
    product_name = ''
    if request.method == 'POST':
        product_name = request.form.get('product_name', '').strip()
        steps = int(request.form.get('steps', 30))
        steps = max(7, min(steps, 90))
        if not product_name:
            error = 'Please enter a product name to forecast.'
        else:
            try:
                from forecaster import forecast_product_by_name
                result = forecast_product_by_name(
                    product_name=product_name,
                    db_session=db.session,
                    Purchase=Purchase,
                    Product=Product,
                    steps=steps
                )
            except Exception as e:
                error = f'Forecasting error: {str(e)}'

    products_list = [p.name for p in Product.query.order_by(Product.name).all()]
    return render_template('forecast.html',
        result=result,
        error=error,
        product_name=product_name,
        products_list=products_list
    )


# ─── CUSTOM JINJA2 FILTERS ───────────────────────────────────────────────────
@app.template_filter('enumerate')
def enumerate_filter(iterable, start=0):
    return list(enumerate(iterable, start=start))

@app.template_filter('max')
def max_filter(iterable):
    lst = list(iterable)
    return max(lst) if lst else 0

@app.template_filter('min')
def min_filter(iterable):
    lst = list(iterable)
    return min(lst) if lst else 0

@app.template_global()
def zip_lists(a, b):
    return zip(a, b)


# ─── FAVICON ─────────────────────────────────────────────────────────────────
@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(app.root_path, 'static', 'favicon.png'),
                     mimetype='image/png')


# ─── INIT DB ──────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    seed_products()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
