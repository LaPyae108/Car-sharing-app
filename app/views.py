from flask import render_template, redirect, url_for, flash, request,abort
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from .models import Post,User,Comment,Like  # Changed from database to models for convention
from app.forms import RegistrationForm, LoginForm, PostForm, CommentForm  # Added CommentForm for comments
from werkzeug.security import generate_password_hash, check_password_hash  # For secure password handling


@app.route('/')
def home():
    posts = Post.query.all()  # Retrieve all posts
    return render_template('home.html', posts=posts)

#register Function
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if the email or username already exists
        existing_user = User.query.filter((User.email == form.email.data) | (User.username == form.username.data)).first()
        if existing_user:
            if existing_user.email == form.email.data:
                flash('Email is already registered. Please use a different email.', 'danger')
            elif existing_user.username == form.username.data:
                flash('Username is already taken. Please choose a different username.', 'danger')
            return render_template('register.html', form=form)

        # Hash the password before storing it
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

#loggin function
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Query the database for the user by email
        user = User.query.filter_by(email=form.email.data).first()

        # Check if the user exists and if the password is correct
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Login unsuccessful. Please check your email and password.', 'danger')
    return render_template('login.html', form=form)

#Loggout function
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

#Post function
@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', form=form)

#Post to display on post page function
@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    return render_template('post_detail.html', post=post, form=form)

#To check the amount of user only for admin
@app.route('/users')
@login_required
def users():
    # Check if the logged-in user is an admin (modify as per your model)
    if not current_user.is_admin:  # Assuming `is_admin` is a boolean column in the User model
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    all_users = User.query.all()
    return render_template('user.html', users=all_users)

# post comment function
@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def comment(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    
    if form.validate_on_submit():
        comment = Comment(content=form.content.data, user_id=current_user.id, post_id=post.id)
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been added!', 'success')
        return redirect(url_for('post_detail', post_id=post.id))  # Correctly redirect to the post detail page
    flash('Failed to add comment. Please try again.', 'danger')
    return redirect(url_for('post_detail', post_id=post.id))  # Correctly handle failure with a redirect


#like handeling function
@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()

    if like:
        # If the user already liked the post, unlike it
        db.session.delete(like)
        db.session.commit()
        flash('You unliked the post.', 'info')
    else:
        # Otherwise, like the post
        like = Like(user_id=current_user.id, post_id=post.id)
        db.session.add(like)
        db.session.commit()
        flash('You liked the post!', 'success')

    return redirect(url_for('post_detail', post_id=post.id))

@app.route('/user/<username>')
def user_profile(username):
    # Query user by username
    user = User.query.filter_by(username=username).first_or_404()
    # Query posts created by the user
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).all()
    return render_template('user_profile.html', user=user, posts=posts)


# Edit Post
@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)

    # Ensure only the owner can edit the post
    if post.author != current_user:
        abort(403)  # Forbidden access

    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('post_detail', post_id=post.id))

    # Pre-fill the form with the post's current data
    form.title.data = post.title
    form.content.data = post.content
    return render_template('edit_post.html', form=form, post=post)


# Delete Post
@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    # Ensure only the owner can delete the post
    if post.author != current_user:
        abort(403)  # Forbidden access

    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'info')
    return redirect(url_for('home'))