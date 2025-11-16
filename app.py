from email.policy import default

from flask import Flask, render_template, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask import request, redirect, url_for, jsonify, flash
from sqlalchemy import text
from datetime import timedelta, datetime
from flask import g
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt,set_access_cookies, set_refresh_cookies,unset_jwt_cookies

)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os




app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'

app.secret_key = os.urandom(24)
app.config["JWT_SECRET_KEY"] = "c98ae040d2665719da6a1a13170a699f" # put in ENV in production
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]  # store tokens in cookies
app.config["JWT_COOKIE_SECURE"] = False  # set True in production (HTTPS only)
app.config["JWT_COOKIE_SAMESITE"] = "Lax"
app.config["JWT_COOKIE_CSRF_PROTECT"] = False
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=7)

jwt = JWTManager(app)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

REVOKED_JTIS = set()


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    token = TokenBlocklist.query.filter_by(jti=jti).first()
    return token is not None



class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    address = db.Column(db.String(200), nullable=True)
    user_image = db.Column(db.String(200), nullable=True)

class Category(db.Model):
    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(80), unique=True, nullable=False)

class Product(db.Model):
    product_id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(80), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.category_id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(200), nullable=False)
    stock = db.Column(db.Integer,default=0, nullable=False)

class Sales(db.Model):
    sales_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sale_date = db.Column(db.DateTime, nullable=False)
    total_amount = db.Column(db.Float,default=0.0, nullable=False)

class SaleItem(db.Model):
    sale_item_id = db.Column(db.Integer, primary_key=True)
    sales_id = db.Column(db.Integer, db.ForeignKey('sales.sales_id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.product_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)

class TokenBlocklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False)


def ensure_user_exists():
    username = get_jwt_identity()

    sql = text("SELECT id FROM user WHERE username = :username")
    user = db.session.execute(sql, {"username": username}).fetchone()

    if not user:
        flash("Your account has been removed. Please log in again.", "danger")
        resp = redirect(url_for("login_page"))
        unset_jwt_cookies(resp)
        return resp

    return None

@app.before_request
@jwt_required(optional=True)
def auto_logout_deleted_user():
    if request.endpoint in ('login_page', 'do_login', 'static'):
        return

    username = get_jwt_identity()
    if not username:
        return

    sql = text("SELECT id FROM user WHERE username = :username")
    user = db.session.execute(sql, {"username": username}).fetchone()

    if not user:
        resp = redirect(url_for("login_page"))
        unset_jwt_cookies(resp)
        flash("Your account was deleted. Please contact admin.", "warning")
        return resp


@jwt.unauthorized_loader
def missing_jwt_callback(error):
    """Handle missing or invalid access token."""
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify(msg="Missing or invalid access token"), 401
    flash("Please log in first.", "warning")
    return redirect(url_for("login_page"))

@jwt.invalid_token_loader
def invalid_token_callback(error):
    """Handle invalid JWT token."""
    flash("Session invalid or corrupted. Please log in again.", "warning")
    return redirect(url_for("login_page"))

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    """Handle expired access token."""
    flash("Your session has expired. Please log in again.", "warning")
    return redirect(url_for("login_page"))







@app.get('/login')
def login_page():

    return render_template('login.html')


@app.post('/do_login')
def login():
    resp = redirect(url_for('home'))


    unset_jwt_cookies(resp)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')


        name=text("SELECT * FROM user WHERE username=:username")
        name_result=db.session.execute(name, {'username': username}).fetchone()
        if name_result and check_password_hash(name_result.password, password):

            access_token = create_access_token(identity=username)
            refresh_token = create_refresh_token(identity=username)

            resp = redirect(url_for('home'))
            set_access_cookies(resp, access_token)
            set_refresh_cookies(resp, refresh_token)

            flash(f'Welcome, {username}!', 'success')
            return resp


        else:
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login_page'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        em =text("SELECT * FROM user WHERE email=:email")
        em_result=db.session.execute(em, {'email': email}).fetchone()
        if em_result:
            flash('Email already registered!', 'warning')
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)
        new_user = User(username=username, password=password_hash, email=email)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login_page'))
    return render_template('register.html')

@app.get('/')
@app.get('/home')
@jwt_required(optional=True)
def home():
    user= get_jwt_identity()
    return render_template('home.html', user=user)

@app.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)

    resp = jsonify(msg="Token refreshed")
    set_access_cookies(resp, access_token)
    return resp, 200

@app.route("/logout",methods=["GET", "POST"])
@jwt_required()  # revoke current access token
def logout():
    jti = get_jwt()["jti"]
    db.session.add(TokenBlocklist(jti=jti, created_at=datetime.utcnow()))
    db.session.commit()
    if request.is_json:
        return jsonify({"msg": "Access token revoked"}), 200
    else:
        reps= redirect(url_for('home'))
        unset_jwt_cookies(reps)
        return reps


import route

if __name__ == '__main__':
    app.run()
