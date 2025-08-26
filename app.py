import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import stripe
import sqlite3
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Stripe setup (free test keys from dashboard.stripe.com/test/apikeys)
stripe.api_key = 'sk_test_your_test_secret_key'  # Replace with your key

# Simple bad-word filter for kid-friendliness
BAD_WORDS = ['bad', 'word', 'example']
def filter_content(content):
    for word in BAD_WORDS:
        content = re.sub(rf'\b{word}\b', '***', content, flags=re.IGNORECASE)
    return content

# Initialize SQLite database (free)
def init_db():
    conn = sqlite3.connect('edugrok.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT, subscribed BOOLEAN DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, content TEXT, subject TEXT, likes INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('edugrok.db')
    c = conn.cursor()
    c.execute("SELECT p.id, p.content, p.subject, p.likes, u.email FROM posts p JOIN users u ON p.user_id = u.id ORDER BY p.id DESC")
    posts = [(pid, filter_content(content), subject, likes, email) for pid, content, subject, likes, email in c.fetchall()]
    conn.close()
    return render_template('home.html', posts=posts, subscribed=session.get('subscribed', False))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']  # Hash in production (werkzeug.security)
        try:
            conn = sqlite3.connect('edugrok.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Email already in use", 400
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('edugrok.db')
        c = conn.cursor()
        c.execute("SELECT id, subscribed FROM users WHERE email = ? AND password = ?", (email, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['subscribed'] = user[1]
            session['email'] = email
            return redirect(url_for('home'))
        return "Invalid credentials", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/post', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return "Unauthorized", 401
    content = filter_content(request.form['content'])
    subject = request.form['subject']
    conn = sqlite3.connect('edugrok.db')
    c = conn.cursor()
    c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (session['user_id'], content, subject))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/like/<int:post_id>')
def like_post(post_id):
    if 'user_id' not in session:
        return "Unauthorized", 401
    conn = sqlite3.connect('edugrok.db')
    c = conn.cursor()
    c.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        email = session.get('email')
        try:
            customer = stripe.Customer.create(email=email)
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{'price': 'price_your_monthly_plan_id'}],  # Create $5/month plan in Stripe dashboard
            )
            conn = sqlite3.connect('edugrok.db')
            c = conn.cursor()
            c.execute("UPDATE users SET subscribed = 1 WHERE id = ?", (session['user_id'],))
            conn.commit()
            conn.close()
            session['subscribed'] = True
            return redirect(url_for('home'))
        except stripe.error.StripeError as e:
            return jsonify({'error': str(e)}), 400
    return render_template('subscribe.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, 'whsec_your_webhook_secret')  # Replace with webhook secret
        if event['type'] == 'customer.subscription.deleted':
            customer_id = event['data']['object']['customer']
            conn = sqlite3.connect('edugrok.db')
            c = conn.cursor()
            c.execute("UPDATE users SET subscribed = 0 WHERE email = (SELECT email FROM users WHERE id = (SELECT id FROM users WHERE stripe_customer_id = ?))", (customer_id,))
            conn.commit()
            conn.close()
    except ValueError:
        return '', 400
    return '', 200

if __name__ == '__main__':
    app.run(debug=True)