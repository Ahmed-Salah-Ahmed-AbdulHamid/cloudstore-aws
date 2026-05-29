import os
import time
import threading
from flask import Flask, request, jsonify, session, make_response
from flask_cors import CORS
import boto3
import pymysql
import uuid
import json
import hashlib
from datetime import datetime
import redis
import pika
import ssl

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ahmed-store-secret-2026')
CORS(app, supports_credentials=True, origins=["*"])

# ─── Serve Frontend ──────────────────────────────────────────
@app.route('/')
def serve_frontend():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(current_dir, 'static')
    file_path = os.path.join(static_dir, 'index.html')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        response = make_response(content)
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response
        
    except FileNotFoundError:
        return "Error: index.html not found in the static folder.", 404

# ─── DB Config ───────────────────────────────────────────────
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'admin'),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', 'ecommerce_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

S3_BUCKET = os.environ.get('S3_BUCKET', 'mystore-s3-images')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
MQ_URL = os.environ.get('MQ_URL', '')

def get_db():
    return pymysql.connect(**DB_CONFIG)

def get_redis():
    try:
        r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True,
                        socket_connect_timeout=2)
        r.ping()
        return r
    except Exception:
        return None

def get_s3():
    return boto3.client('s3', region_name=AWS_REGION)

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def init_db():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('buyer','seller') NOT NULL DEFAULT 'buyer',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            seller_id INT NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            quantity INT NOT NULL DEFAULT 0,
            image_url VARCHAR(500),
            category VARCHAR(100),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_id) REFERENCES users(id)
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            buyer_id INT NOT NULL,
            product_id INT NOT NULL,
            quantity INT NOT NULL,
            total_price DECIMAL(10,2) NOT NULL,
            status ENUM('pending','confirmed','shipped','delivered') DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (buyer_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )""")
    conn.commit()
    conn.close()

# ─── Auth ─────────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'buyer')
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    if role not in ('buyer', 'seller'):
        return jsonify({'error': 'Invalid role'}), 400
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                        (username, hash_password(password), role))
        conn.commit()
        return jsonify({'message': 'Registered successfully'})
    except pymysql.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 409
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s",
                        (username, hash_password(password)))
            user = cur.fetchone()
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['username'] = user['username']
        return jsonify({'id': user['id'], 'username': user['username'], 'role': user['role']})
    finally:
        conn.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/me')
def me():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    return jsonify({'id': session['user_id'], 'username': session['username'], 'role': session['role']})

# ─── Live Status & Benchmark ──────────────────────────────────
@app.route('/api/status', methods=['GET'])
def system_status():
    if session.get('role') != 'seller': return jsonify({'error': 'Unauthorized'}), 403
    status = {'rds': {'ok': False, 'ms': 0}, 'redis': {'ok': False, 'ms': 0}, 'mq': {'ok': False, 'ms': 0}}
    
    # Ping RDS
    try:
        t0 = time.time()
        conn = get_db()
        with conn.cursor() as cur: cur.execute("SELECT 1")
        conn.close()
        status['rds'] = {'ok': True, 'ms': int((time.time() - t0) * 1000)}
    except Exception: pass

    # Ping Redis
    try:
        t0 = time.time()
        r = get_redis()
        if r and r.ping():
            status['redis'] = {'ok': True, 'ms': int((time.time() - t0) * 1000)}
    except Exception: pass

    # Ping MQ
    try:
        if MQ_URL:
            t0 = time.time()
            params = pika.URLParameters(MQ_URL)
            params.ssl_options = pika.SSLOptions(ssl.create_default_context())
            conn = pika.BlockingConnection(params)
            conn.close()
            status['mq'] = {'ok': True, 'ms': int((time.time() - t0) * 1000)}
    except Exception: pass

    return jsonify(status)

@app.route('/api/benchmark', methods=['GET'])
def system_benchmark():
    if session.get('role') != 'seller': return jsonify({'error': 'Unauthorized'}), 403
    rds_ms = redis_ms = 0
    
    # Measure RDS
    try:
        t0 = time.time()
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products")
            cur.fetchall()
        conn.close()
        rds_ms = int((time.time() - t0) * 1000)
    except Exception: rds_ms = -1

    # Measure Redis
    try:
        t0 = time.time()
        r = get_redis()
        if r:
            r.get('products:all')
            redis_ms = int((time.time() - t0) * 1000)
            if redis_ms == 0: redis_ms = 1
    except Exception: redis_ms = -1

    speedup = round(rds_ms / redis_ms, 1) if redis_ms > 0 and rds_ms > 0 else 0
    return jsonify({'rds_ms': rds_ms, 'redis_ms': redis_ms, 'speedup': speedup})

# ─── Products ─────────────────────────────────────────────────
@app.route('/api/products', methods=['GET'])
def get_products():
    cache = get_redis()
    cache_key = 'products:all'
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return jsonify(json.loads(cached))
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.*, u.username as seller_name
                FROM products p JOIN users u ON p.seller_id=u.id
                WHERE p.quantity > 0
                ORDER BY p.created_at DESC
            """)
            products = cur.fetchall()
        for p in products:
            p['price'] = float(p['price'])
            p['created_at'] = str(p['created_at'])
            p['updated_at'] = str(p['updated_at'])
        if cache:
            cache.setex(cache_key, 60, json.dumps(products))
        return jsonify(products)
    finally:
        conn.close()

@app.route('/api/seller/products', methods=['GET'])
def seller_products():
    if session.get('role') != 'seller':
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products WHERE seller_id=%s ORDER BY created_at DESC",
                        (session['user_id'],))
            products = cur.fetchall()
        for p in products:
            p['price'] = float(p['price'])
            p['created_at'] = str(p['created_at'])
            p['updated_at'] = str(p['updated_at'])
        return jsonify(products)
    finally:
        conn.close()

@app.route('/api/products', methods=['POST'])
def add_product():
    if session.get('role') != 'seller':
        return jsonify({'error': 'Unauthorized'}), 403
    name = request.form.get('name', '').strip()
    price = request.form.get('price')
    quantity = request.form.get('quantity')
    description = request.form.get('description', '')
    category = request.form.get('category', 'General')
    if not name or not price or not quantity:
        return jsonify({'error': 'Name, price, and quantity are required'}), 400
    
    image_url = None
    if 'image' in request.files:
        f = request.files['image']
        if f.filename:
            ext = f.filename.rsplit('.', 1)[-1].lower()
            key = f"products/{uuid.uuid4()}.{ext}"
            s3 = get_s3()
            s3.upload_fileobj(f, S3_BUCKET, key, ExtraArgs={'ContentType': f.content_type})
            image_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
            
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO products (seller_id, name, description, price, quantity, image_url, category)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (session['user_id'], name, description, float(price), int(quantity), image_url, category))
            product_id = cur.lastrowid
        conn.commit()
        
        cache = get_redis()
        if cache:
            cache.delete('products:all')
            
        notify_mq({'event': 'product_added', 'product_id': product_id, 'name': name})
        
        return jsonify({'message': 'Product added successfully', 'id': product_id}), 201
    finally:
        conn.close()

@app.route('/api/products/<int:pid>', methods=['PUT'])
def update_product(pid):
    if session.get('role') != 'seller':
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products WHERE id=%s AND seller_id=%s", (pid, session['user_id']))
            if not cur.fetchone():
                return jsonify({'error': 'Product not found'}), 404
        data = request.form if request.form else request.json
        name = data.get('name')
        price = data.get('price')
        quantity = data.get('quantity')
        description = data.get('description')
        category = data.get('category')
        fields, vals = [], []
        if name: fields.append('name=%s'); vals.append(name)
        if price: fields.append('price=%s'); vals.append(float(price))
        if quantity is not None: fields.append('quantity=%s'); vals.append(int(quantity))
        if description: fields.append('description=%s'); vals.append(description)
        if category: fields.append('category=%s'); vals.append(category)
        if 'image' in request.files:
            f = request.files['image']
            if f.filename:
                ext = f.filename.rsplit('.', 1)[-1].lower()
                key = f"products/{uuid.uuid4()}.{ext}"
                s3 = get_s3()
                s3.upload_fileobj(f, S3_BUCKET, key, ExtraArgs={'ContentType': f.content_type})
                image_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
                fields.append('image_url=%s'); vals.append(image_url)
        if fields:
            vals.append(pid)
            with conn.cursor() as cur:
                cur.execute(f"UPDATE products SET {','.join(fields)} WHERE id=%s", vals)
            conn.commit()
        cache = get_redis()
        if cache:
            cache.delete('products:all')
        return jsonify({'message': 'Updated successfully'})
    finally:
        conn.close()

@app.route('/api/products/<int:pid>', methods=['DELETE'])
def delete_product(pid):
    if session.get('role') != 'seller':
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products WHERE id=%s AND seller_id=%s", (pid, session['user_id']))
        conn.commit()
        cache = get_redis()
        if cache:
            cache.delete('products:all')
        return jsonify({'message': 'Deleted successfully'})
    finally:
        conn.close()

# ─── Orders ───────────────────────────────────────────────────
@app.route('/api/orders', methods=['POST'])
def place_order():
    if session.get('role') != 'buyer':
        return jsonify({'error': 'Only buyers can place orders'}), 403
    data = request.json
    product_id = data.get('product_id')
    qty = int(data.get('quantity', 1))
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products WHERE id=%s", (product_id,))
            product = cur.fetchone()
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            if product['quantity'] < qty:
                return jsonify({'error': f"Only {product['quantity']} available"}), 400
            total = float(product['price']) * qty
            cur.execute("""
                INSERT INTO orders (buyer_id, product_id, quantity, total_price)
                VALUES (%s,%s,%s,%s)
            """, (session['user_id'], product_id, qty, total))
            cur.execute("UPDATE products SET quantity=quantity-%s WHERE id=%s", (qty, product_id))
            order_id = cur.lastrowid
        conn.commit()
        cache = get_redis()
        if cache:
            cache.delete('products:all')
            
        notify_mq({'event': 'order_placed', 'order_id': order_id, 'product': product['name']})
        return jsonify({'message': 'Order placed successfully', 'order_id': order_id, 'total': total}), 201
    finally:
        conn.close()

@app.route('/api/orders/my', methods=['GET'])
def my_orders():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT o.*, p.name as product_name, p.image_url
                FROM orders o JOIN products p ON o.product_id=p.id
                WHERE o.buyer_id=%s ORDER BY o.created_at DESC
            """, (session['user_id'],))
            orders = cur.fetchall()
        for o in orders:
            o['total_price'] = float(o['total_price'])
            o['created_at'] = str(o['created_at'])
        return jsonify(orders)
    finally:
        conn.close()

@app.route('/api/seller/orders', methods=['GET'])
def seller_orders():
    if session.get('role') != 'seller':
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT o.*, p.name as product_name, u.username as buyer_name
                FROM orders o
                JOIN products p ON o.product_id=p.id
                JOIN users u ON o.buyer_id=u.id
                WHERE p.seller_id=%s ORDER BY o.created_at DESC
            """, (session['user_id'],))
            orders = cur.fetchall()
        for o in orders:
            o['total_price'] = float(o['total_price'])
            o['created_at'] = str(o['created_at'])
        return jsonify(orders)
    finally:
        conn.close()

# ─── Stats for seller ─────────────────────────────────────────
@app.route('/api/seller/stats')
def seller_stats():
    if session.get('role') != 'seller':
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt, SUM(quantity) as total_stock FROM products WHERE seller_id=%s",
                        (session['user_id'],))
            prod = cur.fetchone()
            cur.execute("""
                SELECT COUNT(*) as orders, COALESCE(SUM(o.total_price),0) as revenue
                FROM orders o JOIN products p ON o.product_id=p.id
                WHERE p.seller_id=%s
            """, (session['user_id'],))
            sales = cur.fetchone()
        return jsonify({
            'total_products': prod['cnt'],
            'total_stock': prod['total_stock'] or 0,
            'total_orders': sales['orders'],
            'revenue': float(sales['revenue'])
        })
    finally:
        conn.close()

# ─── MQ Notify (Optimized with Background Threading) ────────────
def notify_mq(message):
    if not MQ_URL:
        return
    
    def task():
        try:
            params = pika.URLParameters(MQ_URL)
            params.ssl_options = pika.SSLOptions(ssl.create_default_context())
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.queue_declare(queue='store_events', durable=True)
            ch.basic_publish(exchange='', routing_key='store_events',
                             body=json.dumps(message))
            conn.close()
        except Exception as e:
            print(f"MQ Background Task Error: {e}")

    # Start the task in the background so it doesn't block the API response
    threading.Thread(target=task).start()

if __name__ == '__main__':
    try:
        init_db()
    except Exception as e:
        print(f"DB init warning: {e}")
    app.run(host='0.0.0.0', port=5000, debug=False)