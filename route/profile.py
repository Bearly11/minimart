from app import app, db
from flask import render_template, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import text
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
import os


UPLOAD_DIR = os.path.join("static/image", "user_image")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.route('/profile')
@jwt_required()
def profile():
    user = get_jwt_identity()
    search = request.args.get('q', '').strip()

    if search:
        # Raw SQL with LIKE for username search
        sql = """
            SELECT *
            FROM user
            WHERE LOWER(username) LIKE LOWER(:search)
            ORDER BY id DESC
        """
        params = {'search': f"%{search}%"}
    else:
        sql = "SELECT * FROM user ORDER BY id DESC"
        params = {}

    profile_data = db.session.execute(text(sql), params).fetchall()

    profile = []
    for row in profile_data:
        prof = {
            'user_id': row[0],
            'username': row[1],
            'password': row[2],
            'email': row[3],
            'address': row[4],
            'user_image': row[5]
        }
        profile.append(prof)

    return render_template('profile/profile.html', profile=profile, user=user, q=search)






@app.get('/add_profile_form')
@jwt_required()
def add_profile_form():
    user = get_jwt_identity()
    return render_template('profile/add_profile.html', user=user)

@app.post('/create_profile')
def create_profile():
    username = request.form.get('username')
    password= request.form.get('password')
    email = request.form.get('email')
    address= request.form.get('address')
    user_image = request.files.get('user_image')
    if not username or not password or not email:
        flash('Username, password, and email are required!', 'danger')
        return redirect(url_for('add_profile_form'))
    exist_email = db.session.execute(text('SELECT * FROM user WHERE email = :email'),
                                        {
                                            'email': email
                                        }).fetchone()
    if exist_email:
        flash('This email already exists!', 'warning')
        return redirect(url_for('add_profile_form'))

    image_url_db = None
    if user_image:
        user_image.seek(0, os.SEEK_END)
        file_size = user_image.tell()
        user_image.seek(0)
        if file_size > 5 * 1024 * 1024:
            flash("Image too large! Max size is 5MB.", "danger")
            return redirect(url_for('add_profile_form'))
        filename = secure_filename(user_image.filename)
        image_url_db = filename
        user_image.save(os.path.join(UPLOAD_DIR, filename))
    db.session.execute(
        text("""
        INSERT INTO user (username, password, email, address, user_image)
        VALUES (:username, :password, :email, :address, :user_image)
        """),
        {
            'username': username,
            'password': password,
            'email': email,
            'address': address,
            'user_image': image_url_db
        }
    )
    db.session.commit()
    flash('Profile created successfully!', 'success')
    return redirect(url_for('profile'))

@app.get('/edit_profile_form/<int:user_id>')
@jwt_required()
def edit_profile_form(user_id):
    user = get_jwt_identity()
    profile_data = db.session.execute(
        text('SELECT * FROM user WHERE id = :user_id'),
        {'user_id': user_id}
    ).fetchone()
    if not profile_data:
        flash('Profile not found!', 'danger')
        return redirect(url_for('profile'))

    profile = {
        'user_id': profile_data[0],
        'username': profile_data[1],
        'password': profile_data[2],
        'email': profile_data[3],
        'address': profile_data[4],
        'user_image': profile_data[5]
    }

    return render_template('profile/update_profile.html', profile=profile, user=user)

@app.post('/update_profile/<int:user_id>')
def update_profile(user_id):
    username = request.form.get('username')
    email = request.form.get('email')
    address = request.form.get('address')
    user_image = request.files.get('user_image')

    if not username or not email:
        flash('Username and email are required!', 'danger')
        return redirect(url_for('edit_profile_form', user_id=user_id))

    # Get current user data
    profile_data = db.session.execute(
        text('SELECT * FROM user WHERE id = :user_id'), {'user_id': user_id}
    ).fetchone()
    if not profile_data:
        flash('Profile not found!', 'danger')
        return redirect(url_for('profile'))

    image_filename = profile_data[5]  # Keep current image

    # Update image if provided
    if user_image:
        user_image.seek(0, os.SEEK_END)
        file_size = user_image.tell()
        user_image.seek(0)
        if file_size > 5 * 1024 * 1024:
            flash("Image too large! Max size is 5MB.", "danger")
            return redirect(url_for('edit_profile_form', user_id=user_id))
        filename = secure_filename(user_image.filename)
        image_filename = filename
        user_image.save(os.path.join(UPLOAD_DIR, filename))

    db.session.execute(
        text("""
            UPDATE user
            SET username = :username,
                email = :email,
                address = :address,
                user_image = :user_image
            WHERE id = :user_id
        """),
        {
            'username': username,
            'email': email,
            'address': address,
            'user_image': image_filename,
            'user_id': user_id
        }
    )
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))


@app.post('/delete_profile/<int:user_id>')
def delete_profile(user_id):
    db.session.execute(
        text('DELETE FROM user WHERE id = :user_id'),
        {'user_id': user_id}
    )
    db.session.commit()
    flash('Profile deleted successfully!', 'success')
    return redirect(url_for('profile'))

@app.post('/reset_password/<int:user_id>')
def reset_password(user_id):
    new_password = request.form.get('new_password')
    if not new_password:
        flash('New password is required!', 'danger')
        return redirect(url_for('edit_profile_form', user_id=user_id))

    db.session.execute(
        text('UPDATE user SET password = :password WHERE id = :user_id'),
        {
            'password': generate_password_hash(new_password),
            'user_id': user_id
        }
    )
    db.session.commit()
    flash('Password reset successfully!', 'success')
    return redirect(url_for('profile'))


