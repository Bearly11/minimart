from flask_jwt_extended import jwt_required, get_jwt_identity
from app import app, db
from sqlalchemy import text
from flask import request, render_template, flash, redirect, url_for


def get_all_categories():
    sql = db.session.execute(text('SELECT * FROM category')).fetchall()
    categories = [dict(row._mapping) for row in sql]
    return categories

def get_category_by_id(category_id):
    sql = db.session.execute(text('SELECT * FROM category WHERE category_id = :id'),
                             {
                                 'id': category_id
                             }).fetchone()

    if sql:
        return dict(sql._mapping)
    return 'not found this id'



@app.get('/category_list')
@jwt_required()
def category_list():
    user= get_jwt_identity()
    list = db.session.execute(text('SELECT * FROM category')).fetchall()
    categories =[]
    for row in list:
        category={
            'category_id': row[0],
            'category_name': row[1]
        }
        categories.append(category)
    return render_template('category/category_list.html', categories=categories, user=user)

@app.get('/get_category/<int:category_id>')
def get_category(category_id):
    return get_category_by_id(category_id)

def exist_category(name):
    sql = db.session.execute(text('SELECT category_name FROM category WHERE category_name = :name'),
                                {
                                    'name': name
                                }).fetchone()
    if sql:
        return True
    return False

@app.route('/add_category_form')
@jwt_required()
def add_category_form():
    user= get_jwt_identity()
    return render_template('category/add_category.html', user=user)
@app.post('/create_category',endpoint='create_category')
def create_category():
    if request.method == 'POST':
        category_name = request.form.get('category_name')
        if exist_category(category_name):
            flash('This category name already exists!', 'warning')
            return redirect(url_for('add_category_form'))
        if not category_name:
            flash('Category name is required!', 'danger')
            return redirect(url_for('add_category_form'))
        category= text('INSERT INTO category (category_name) VALUES (:name)')
        result=db.session.execute(category, {'name': category_name})
        category_id = result.lastrowid
        db.session.commit()
        flash('Category created successfully.', 'success')
        return redirect(url_for('category_list'))

@app.route('/update_category_form/<int:category_id>')
def update_category_form(category_id):
    category_row = db.session.execute(
        text("""
            SELECT category_id, category_name
            FROM category
            WHERE category_id = :id
        """), {'id': category_id}
    ).fetchone()

    if not category_row:
        flash('Category not found!', 'danger')
        return redirect(url_for('category_list'))

    category = dict(category_row._mapping)

    return render_template(
        'category/update_category.html',
        category=category
    )
@app.post('/update_category/<int:category_id>')
def update_category(category_id):
    if request.method == 'POST':
        category_name = request.form.get('category_name')
        if exist_category(category_name):
            flash('This category name already exists!', 'warning')
            return redirect(url_for('update_category_form', category_id=category_id))
        if not category_name:
            flash('Category name is required!', 'danger')
            return redirect(url_for('update_category_form', category_id=category_id))
        category = text('UPDATE category SET category_name = :name WHERE category_id = :id')
        result = db.session.execute(category, {'name': category_name, 'id': category_id})
        db.session.commit()
        if result.rowcount == 0:
            return 'not found this id', 404
        flash('Category updated successfully.', 'success')
        return redirect(url_for('category_list'))

@app.post('/delete_category/<int:category_id>')
def delete_category(category_id):
    category = text('DELETE FROM category WHERE category_id = :id')
    result = db.session.execute(category, {'id': category_id})
    db.session.commit()
    if result.rowcount == 0:
        flash('Category not found!', 'danger')
        return redirect(url_for('category_list'))
    return redirect(url_for('category_list'))