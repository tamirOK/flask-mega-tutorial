from datetime import datetime
from flask import render_template, flash, redirect, url_for, request
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.urls import url_parse

from app import app, db
from app.email import send_password_reset_email
from app.forms import LoginForm, RegistrationForm, EditProfileForm, PostForm, ResetPasswordRequestForm, \
    ResetPasswordForm
from app.models import User, Post


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user or not user.check_password(password=form.password.data):
            flash('Incorrect user or login')
            return redirect(url_for('login'))
        else:
            login_user(user, remember=form.remember_me.data)
            next_url = request.args.get('next')
            if not next_url or url_parse(next_url).netloc != '':
                next_url = url_for('index')
            return redirect(next_url)
    return render_template('login.html', title='Sign in', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()

    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You successfully registered')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/logout', methods=['GET'])
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/user/<username>')
@login_required
def user(username):
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, app.config['POSTS_PER_PAGE'], False
    )
    next_page = url_for('user', username=username,  page=posts.next_num) if posts.has_next else None
    prev_page = url_for('user', username=username, page=posts.prev_num) if posts.has_prev else None
    return render_template('user.html', user=user, posts=posts.items, next_page=next_page, prev_page=prev_page)


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Changes have been saved')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me

    return render_template('edit_profile.html', form=form)


@app.route('/follow/<username>')
@login_required
def follow(username):
    followed_user = User.query.filter_by(username=username).first()
    if not followed_user:
        flash('No user with such username')
        return redirect(url_for('index'))

    if current_user == followed_user:
        flash('You cannot follow yourself')
        return redirect(url_for('index'))

    current_user.follow(followed_user)
    db.session.commit()
    flash('You are following {}!'.format(followed_user))
    return redirect(url_for('user', username=username))


@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    unfollowed_user = User.query.filter_by(username=username).first()
    if not unfollowed_user:
        flash('No user with such username')
        return redirect(url_for('index'))

    if current_user == unfollowed_user:
        flash('You cannot unfollow yourself')
        return redirect(url_for('index'))

    current_user.unfollow(unfollowed_user)
    db.session.commit()
    flash('You have unfollowed {}!'.format(unfollowed_user))
    return redirect(url_for('user', username=username))


@app.route('/', methods=['GET', 'POST'])
@app.route('/index/', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    page = request.args.get('page', 1, type=int)
    if form.validate_on_submit():
        post = Post(body=form.post.data, user_id=current_user.id)
        flash('Your post successfully added')
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('index'))
    posts = current_user.followed_posts().paginate(page, app.config['POSTS_PER_PAGE'], False)
    next_page = url_for('index', page=posts.next_num) if posts.has_next else None
    prev_page = url_for('index', page=posts.prev_num) if posts.has_prev else None
    return render_template('index.html', title='Home Page', form=form,
                            posts=posts.items, next_page=next_page, prev_page=prev_page)


@app.route('/explore', methods=['GET'])
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(page, app.config['POSTS_PER_PAGE'], False)
    next_page = url_for('explore', page=posts.next_num) if posts.has_next else None
    prev_page = url_for('explore', page=posts.prev_num) if posts.has_prev else None
    return render_template('index.html', title='Explore',
                           posts=posts.items, next_page=next_page, prev_page=prev_page)


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for password reset')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html', form=form, title='Reset password')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('login'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Password successfully changed!')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)


@app.before_request
def update_user_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()