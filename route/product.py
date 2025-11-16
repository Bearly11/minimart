from flask_jwt_extended import jwt_required, get_jwt_identity

from app import app, db
from sqlalchemy import text
from flask import request, render_template, flash, redirect, url_for
from werkzeug.utils import secure_filename
import os

UPLOAD_DIR = os.path.join("static/image", "product_image")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_all_products():
    sql = db.session.execute(text('SELECT * FROM product')).fetchall()
    products = [dict(row._mapping) for row in sql]
    return products

def get_product_by_id(product_id):
    sql = db.session.execute(text('SELECT * FROM product WHERE product_id = :id'),
                             {
                                 'id': product_id
                             }).fetchone()

    if sql:
        return dict(sql._mapping)
    return 'not found this id'

def exist_product(name):
    sql = db.session.execute(text('SELECT product_name FROM product WHERE product_name = :name'),
                             {
                                 'name': name
                             }).fetchone()
    if sql:
        return True
    return False

@app.get('/get_all_products')
def get_products():
    return get_all_products()

@app.get('/get_product/<int:product_id>')
def get_product(product_id):
    return get_product_by_id(product_id)

@app.route('/product_list')
@jwt_required()
def products():
    user = get_jwt_identity()
    search = request.args.get('q', '').strip()

    query = """
        SELECT p.product_id, p.image_url, p.product_name, c.category_name, p.price, p.stock
        FROM product p
        JOIN category c ON p.category_id = c.category_id
    """

    params = {}
    if search:
        query += " WHERE LOWER(p.product_name) LIKE LOWER(:search) OR LOWER(c.category_name) LIKE LOWER(:search)"
        params['search'] = f"%{search}%"

    query += " ORDER BY p.product_id DESC"

    lists = db.session.execute(text(query), params).fetchall()
    products = [
        {
            'product_id': item[0],
            'image_url': item[1],
            'product_name': item[2],
            'category_name': item[3],
            'price': item[4],
            'stock': item[5],
        }
        for item in lists
    ]

    return render_template('products/product_list.html', products=products, user=user, q=search)


@app.route('/add_product_form')
@jwt_required()
def add_product_form():
    user= get_jwt_identity()
    categories = db.session.execute(text("SELECT category_name FROM category")).fetchall()
    category_list = [row[0] for row in categories]
    return render_template('products/add_product.html', categories=category_list,user=user)

@app.route('/update_product_form/<int:product_id>')
def update_product_form(product_id):
    product_row = db.session.execute(
        text("""
            SELECT p.product_id, p.product_name, p.category_id, p.price, p.image_url, p.stock
            FROM product p
            WHERE p.product_id = :id
        """), {'id': product_id}
    ).fetchone()

    if not product_row:
        flash('Product not found!', 'danger')
        return redirect(url_for('products'))

    product = dict(product_row._mapping)

    categories = db.session.execute(
        text("SELECT category_id, category_name FROM category")
    ).fetchall()
    categories = [dict(row._mapping) for row in categories]

    return render_template(
        'products/update_product.html',
        product=product,
        categories=categories
    )





@app.post('/create_product')
def create_product():
    if request.method == 'POST':
        product_name = request.form.get('product_name')
        category_name = request.form.get('category_name')
        price = float(request.form.get('price', 0))
        image_url = request.files.get('image_url')
        stock = int(request.form.get('stock', 0))
        if not product_name or not category_name or not price:
            flash('Product name, category, and price are required!', 'danger')
            return redirect(url_for('add_product_form'))
        if exist_product(product_name):
            flash('This product name already exists!', 'warning')
            return redirect(url_for('add_product_form'))

        category_id_row= db.session.execute(text('SELECT category_id FROM category WHERE category_name = :name'),
                                        {
                                            'name': category_name
                                        }).fetchone()
        if not category_id_row:
            flash('Invalid category selected!', 'danger')
            return redirect(url_for('add_product_form'))

        category_id = category_id_row[0]


        image_url_db = None
        if image_url:
            image_url.seek(0, os.SEEK_END)
            file_size = image_url.tell()
            image_url.seek(0)
            if file_size > 5 * 1024 * 1024:
                flash("Image too large! Max size is 5MB.", "danger")
                return redirect(url_for('add_product_form'))
            filename = secure_filename(image_url.filename)
            image_url_db = filename
            image_url.save(os.path.join(UPLOAD_DIR, filename))

        product= text('INSERT INTO product (product_name, category_id, price, image_url, stock) VALUES (:name, :category_id, :price, :image_url, :stock)')
        result=db.session.execute(product, {'name': product_name,
                                            'category_id': category_id,
                                            'price': price,
                                            'image_url': image_url_db,
                                            'stock': stock})

        product_id = result.lastrowid
        db.session.commit()

        flash('Product added successfully!', 'success')
        return redirect(url_for('products'))

@app.post('/update_product/<int:product_id>')
def update_product(product_id):
    if request.method == 'POST':
        data = request.form
        product_name = data.get('product_name')
        category_name = data.get('category_name')
        price = float(data.get('price'))
        image_url = request.files.get('image_url')
        stock = int(data.get('stock', 0))
        category_id_row= db.session.execute(text('SELECT category_id FROM category WHERE category_name = :name'),
                                        {
                                            'name': category_name
                                        }).fetchone()

        if not product_name or not category_name or not price:
            return 'product_name, category_id, price are required', 400
        if price <= 0:
            return 'price must be greater than zero', 400
        if not category_id_row:
            return 'Invalid category selected!', 400
        category_id = category_id_row[0]
        image_url_db = None
        if image_url:
            image_url.seek(0, os.SEEK_END)
            file_size = image_url.tell()
            image_url.seek(0)
            if file_size > 5 * 1024 * 1024:
                flash("Image too large! Max size is 5MB.", "danger")
                return redirect(url_for('update_product_form', product_id=product_id))
            filename = secure_filename(image_url.filename)
            image_url_db=filename
            image_url.save(os.path.join(UPLOAD_DIR, filename))


        product = text('UPDATE product SET product_name = :name, category_id = :category_id, price = :price, image_url = :image_url, stock = :stock WHERE product_id = :id')
        result = db.session.execute(product, {'name': product_name,
                                             'category_id': category_id,
                                                'price': price,
                                                'image_url': image_url_db,
                                                'stock': stock,
                                                'id': product_id})
        db.session.commit()
        if result.rowcount == 0:
            return 'Product not found', 404
        flash('Product update successfully!', 'success')
        return redirect(url_for('products'))

@app.post('/delete_product/<int:product_id>')
def delete_product(product_id):
    product = text('DELETE FROM product WHERE product_id = :id')
    result = db.session.execute(product, {'id': product_id})
    db.session.commit()
    if result.rowcount == 0:
        flash('Product not found!', 'danger')
        return redirect(url_for('products'))
    return redirect(url_for('products'))