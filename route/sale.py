
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import text
from flask import request, jsonify, render_template, flash, redirect, url_for
from datetime import datetime
from app import app, db


def get_sale_item_id(sale_item_id):
    sql = db.session.execute(
        text("SELECT * FROM sale_item WHERE sale_item_id = :id"),
        {'id': sale_item_id}
    ).fetchone()
    if sql:
        return dict(sql._mapping)
    return 'not fond this id'

def get_all_saleItems():
    sql = db.session.execute(text('SELECT * FROM sale_item')).fetchall()
    sale_items = [dict(row._mapping) for row in sql]
    return sale_items

def get_all_sales():
    sql = db.session.execute(text('SELECT * FROM sales')).fetchall()
    sales = [dict(row._mapping) for row in sql]
    return sales

def get_sale_by_id(sales_id):
    sql = db.session.execute(
        text('SELECT * FROM sales WHERE sales_id = :id'),
        {'id': sales_id}
    ).fetchone()

    if sql:
        return dict(sql._mapping)
    return 'not found this id'



@app.route('/sales_form')
@jwt_required()
def sales():
    user=get_jwt_identity()
    list=db.session.execute(text('SELECT * FROM sales')).fetchall()
    sales =[]
    for row in list:
        sale={
            'sales_id': row[0],
            'user_id': row[1],
            'sale_date': row[2],
            'total_amount': row[3]
        }
        sales.append(sale)
    return render_template('sale/sales.html', sales=sales, user=user)

@app.get('/create_sale_form')
@jwt_required()
def create_sale_form():
    user=get_jwt_identity()
    name = db.session.execute(text('select product_name from product')).fetchall()

    return render_template('sale/create_sale.html',name=name, user=user)
@app.post('/create_sale')
@jwt_required()
def create_sale():
    username = get_jwt_identity()
    if not username:
        flash('Authentication required to create a sale.', 'danger')
        return redirect(url_for('login_page'))
    # Get user_id from username
    user = db.session.execute(
        text("SELECT id FROM user WHERE username=:username"),
        {'username': username}
    ).fetchone()

    if not user:
        flash('User not found!', 'danger')
        return redirect(url_for('login_page'))

    user_id = user.id
    sale_date = datetime.now()


    product_name = request.form.getlist('product_name[]')
    product_ids = []
    for name in product_name:
        product = db.session.execute(
            text("SELECT product_id FROM product WHERE product_name = :name"),
            {'name': name}
        ).fetchone()
        if product:
            product_ids.append(product.product_id)
        else:
            flash('Product {} not found!'.format(name), 'danger')
            return redirect(url_for('create_sale_form'))
    quantities = request.form.getlist('quantity[]')
    items = [{'product_id': int(pid), 'quantity': int(qty)} for pid, qty in zip(product_ids, quantities)]

    if not items:
        flash('At least one sale item is required!', 'danger')
        return redirect(url_for('create_sale_form'))

    try:
        # Create sale
        result = db.session.execute(
            text("INSERT INTO sales (user_id, sale_date, total_amount) VALUES (:user_id, :sale_date, 0.0)"),
            {'user_id': user_id, 'sale_date': sale_date}
        )
        sales_id = result.lastrowid

        total_amount = 0.0

        for item in items:
            pid = item['product_id']
            qty = item['quantity']

            # Get product price
            product = db.session.execute(
                text("SELECT price, stock FROM product WHERE product_id = :pid"),
                {'pid': pid}
            ).fetchone()

            if not product:
                flash('Product not found!', 'danger')
                return redirect(url_for('create_sale_form'))

            if product.stock < qty:
                flash('Insufficient stock for product ID {}'.format(pid), 'danger')
                return redirect(url_for('create_sale_form'))

            unit_price = product.price
            total_amount += unit_price * qty

            # Insert into sale_item
            db.session.execute(
                text("INSERT INTO sale_item (sales_id, product_id, quantity, unit_price) "
                     "VALUES (:sales_id, :product_id, :quantity, :unit_price)"),
                {'sales_id': sales_id, 'product_id': pid, 'quantity': qty, 'unit_price': unit_price}
            )

            # Reduce stock
            db.session.execute(
                text("UPDATE product SET stock = stock - :qty WHERE product_id = :pid"),
                {'qty': qty, 'pid': pid}
            )

        # Update total_amount
        db.session.execute(
            text("UPDATE sales SET total_amount = :total WHERE sales_id = :sid"),
            {'total': total_amount, 'sid': sales_id}
        )

        db.session.commit()
        flash('Sale created successfully!', 'success')
        return redirect(url_for('sales'))

    except Exception as e:
        db.session.rollback()
        flash('Error creating sale: {}'.format(str(e)), 'danger')
        return redirect(url_for('create_sale_form'))

@app.route('/sale_details/<int:sales_id>', methods=['GET', 'POST'])
@jwt_required()
def sale_details(sales_id):

    user = get_jwt_identity()

    # Get sale info
    sale_row = db.session.execute(
        text("SELECT * FROM sales WHERE sales_id = :id"),
        {'id': sales_id}
    ).fetchone()

    if not sale_row:
        flash('Sale not found!', 'danger')
        return redirect(url_for('sales'))

    sale = dict(sale_row._mapping)

    # Handle adding a new item
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        quantity = int(request.form.get('quantity', 1))

        if not product_id:
            flash('Please select a product.', 'danger')
            return redirect(url_for('sale_details', sales_id=sales_id))

        # Get product info
        product = db.session.execute(
            text("SELECT price, stock FROM product WHERE product_id = :pid"),
            {'pid': product_id}
        ).fetchone()

        if not product:
            flash('Product not found!', 'danger')
            return redirect(url_for('sale_details', sales_id=sales_id))

        if product.stock < quantity:
            flash('Not enough stock available.', 'danger')
            return redirect(url_for('sale_details', sales_id=sales_id))

        unit_price = product.price
        total_price = unit_price * quantity

        # Insert into sale_item
        db.session.execute(
            text("""INSERT INTO sale_item (sales_id, product_id, quantity, unit_price)
                    VALUES (:sid, :pid, :qty, :price)"""),
            {'sid': sales_id, 'pid': product_id, 'qty': quantity, 'price': unit_price}
        )

        # Reduce stock
        db.session.execute(
            text("UPDATE product SET stock = stock - :qty WHERE product_id = :pid"),
            {'qty': quantity, 'pid': product_id}
        )

        # Update total amount
        db.session.execute(
            text("UPDATE sales SET total_amount = total_amount + :amount WHERE sales_id = :sid"),
            {'amount': total_price, 'sid': sales_id}
        )

        db.session.commit()
        flash('Product added to invoice.', 'success')
        return redirect(url_for('sale_details', sales_id=sales_id))

    # Fetch sale items
    sale_items_rows = db.session.execute(
        text("""
        SELECT si.sale_item_id, si.product_id, p.product_name, si.quantity, si.unit_price
        FROM sale_item si
        JOIN product p ON si.product_id = p.product_id
        WHERE si.sales_id = :sid
        """),
        {'sid': sales_id}
    ).fetchall()

    sale_items = [dict(row._mapping) for row in sale_items_rows]

    # Product dropdown
    products = db.session.execute(
        text("SELECT product_id, product_name FROM product WHERE stock > 0")
    ).fetchall()

    return render_template(
        'sale/invoice_detail.html',
        sale=sale,
        sale_items=sale_items,
        products=products,
        user=user
    )


@app.post('/delete_sale/<int:sales_id>', endpoint='delete_sale')
def delete_sale(sales_id):
    sale=get_sale_by_id(sales_id)
    if not sale:
        flash('Sale not found!', 'danger')
        return redirect(url_for('sales'))

    delete_sale_items=text('DELETE FROM sale_item WHERE sales_id = :id')
    db.session.execute(delete_sale_items, {'id': sales_id})

    delete_sale=text('DELETE FROM sales WHERE sales_id = :id')
    db.session.execute(delete_sale, {'id': sales_id})

    db.session.commit()
    flash('Sale deleted successfully.', 'success')
    return redirect(url_for('sales'))

@app.post('/delete_sale_item/<int:sale_item_id>/<int:sales_id>')
@jwt_required()
def delete_sale_item(sale_item_id, sales_id):
    # Get sale item info
    item = db.session.execute(
        text("SELECT product_id, quantity, unit_price FROM sale_item WHERE sale_item_id = :id"),
        {'id': sale_item_id}
    ).fetchone()

    if not item:
        flash('Sale item not found!', 'danger')
        return redirect(url_for('sale_details', sales_id=sales_id))

    product_id, qty, unit_price = item
    total_price = unit_price * qty

    # Delete item
    db.session.execute(text("DELETE FROM sale_item WHERE sale_item_id = :id"), {'id': sale_item_id})

    # Return stock
    db.session.execute(
        text("UPDATE product SET stock = stock + :qty WHERE product_id = :pid"),
        {'qty': qty, 'pid': product_id}
    )

    # Update total
    db.session.execute(
        text("UPDATE sales SET total_amount = total_amount - :total WHERE sales_id = :sid"),
        {'total': total_price, 'sid': sales_id}
    )

    db.session.commit()
    flash('Item removed successfully.', 'success')
    return redirect(url_for('sale_details', sales_id=sales_id))

















