from app import app, db
from flask import render_template, request,url_for, redirect, flash
from sqlalchemy import text
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime


@app.route('/report')
@jwt_required()
def report_home():
    user = get_jwt_identity()
    return render_template('report/report.html', user=user)


@app.route('/report/daily')
@jwt_required()
def report_daily():
    user = get_jwt_identity()
    sql = text("""
        SELECT DATE(sale_date) AS date, SUM(total_amount) AS total
        FROM sales
        GROUP BY DATE(sale_date)
        ORDER BY DATE(sale_date) DESC
    """)
    rows = db.session.execute(sql).fetchall()
    data = [dict(row._mapping) for row in rows]
    return render_template('report/daily.html', data=data, user=user)


@app.route('/report/weekly')
@jwt_required()
def report_weekly():
    user = get_jwt_identity()
    sql = text("""
        SELECT
            STRFTIME('%Y-%W', sale_date) AS week_label,
            MIN(DATE(sale_date)) AS week_start,
            MAX(DATE(sale_date)) AS week_end,
            SUM(total_amount) AS total
        FROM sales
        GROUP BY STRFTIME('%Y-%W', sale_date)
        ORDER BY week_label DESC
    """)
    rows = db.session.execute(sql).fetchall()
    data = [dict(row._mapping) for row in rows]
    return render_template('report/weekly.html', data=data, user=user)


@app.route('/report/monthly')
@jwt_required()
def report_monthly():
    user = get_jwt_identity()
    sql = text("""
        SELECT
            STRFTIME('%Y-%m', sale_date) AS month_label,
            SUM(total_amount) AS total
        FROM sales
        GROUP BY STRFTIME('%Y-%m', sale_date)
        ORDER BY month_label DESC
    """)
    rows = db.session.execute(sql).fetchall()
    data = [dict(row._mapping) for row in rows]
    return render_template('report/monthly.html', data=data, user=user)


@app.route('/report/saleby')
@jwt_required()
def report_saleby():
    user = get_jwt_identity()
    criteria = request.args.get('by', 'product')  # product / category / user

    if criteria == 'product':
        sql = text("""
            SELECT p.product_name, SUM(si.quantity * si.unit_price) AS total_sales, SUM(si.quantity) AS total_qty
            FROM sale_item si
            JOIN product p ON si.product_id = p.product_id
            GROUP BY p.product_id, p.product_name
            ORDER BY total_sales DESC
        """)
    elif criteria == 'category':
        sql = text("""
            SELECT c.category_name, SUM(si.quantity * si.unit_price) AS total_sales, SUM(si.quantity) AS total_qty
            FROM sale_item si
            JOIN product p ON si.product_id = p.product_id
            JOIN category c ON p.category_id = c.category_id
            GROUP BY c.category_id, c.category_name
            ORDER BY total_sales DESC
        """)
    elif criteria == 'user':
        sql = text("""
            SELECT u.username, SUM(s.total_amount) AS total_sales, COUNT(s.sales_id) AS sale_count
            FROM sales s
            JOIN "user" u ON s.user_id = u.id
            GROUP BY u.id, u.username
            ORDER BY total_sales DESC
        """)
    else:
        flash("Invalid report criteria!", "danger")
        return redirect(url_for('report_home'))

    rows = db.session.execute(sql).fetchall()
    data = [dict(row._mapping) for row in rows]

    return render_template('report/saleby.html', data=data, user=user, criteria=criteria)
