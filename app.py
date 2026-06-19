import os
import re
import uuid

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from models import BlogPost, Bookmark, Comment, PostLike, User, db
from utils import generate_unique_slug

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join('static', 'uploads')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'jfif', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    posts = BlogPost.query.order_by(BlogPost.id.desc()).all()
    return render_template('index.html', posts=posts)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        if User.query.filter_by(email=request.form['email']).first():
            flash('exists')
            return redirect(url_for('register'))
        u = User(username=request.form['username'], email=request.form['email'])
        u.set_password(request.form['password'])
        db.session.add(u)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form['email']).first()
        if not u or not u.verify_password(request.form['password']):
            flash('fail')
            return redirect(url_for('login'))
        session['uid'] = u.id
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'uid' not in session:
        return redirect(url_for('login'))
    u = User.query.get(session['uid'])
    posts = BlogPost.query.filter_by(user_id=u.id).all()
    return render_template('dashboard.html', user=u, posts=posts)


@app.route('/create', methods=['GET','POST'])
def create():
    if 'uid' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        slug = generate_unique_slug(db, BlogPost, title)

        cover_image_url = None

        if 'cover_image' in request.files:
            file = request.files['cover_image']

            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{slug}.{ext}"

                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                cover_image_url = f"/static/uploads/{filename}"

        p = BlogPost(
            title=title,
            summary=request.form['summary'],
            cover_image=cover_image_url,
            content=request.form['content'],
            category=request.form['category'],
            slug=slug,
            user_id=session['uid']
        )

        db.session.add(p)
        db.session.commit()

        return redirect(url_for('dashboard'))

    return render_template('create.html')

@app.route('/upload-inline', methods=['POST'])
def upload_inline():
    """AJAX endpoint for uploading rich-text inline images."""
    if 'uid' not in session:
        return {'error': 'Authentication required'}, 401
        
    if 'image' not in request.files:
        return {'error': 'No file uploaded'}, 400
        
    file = request.files['image']
    if file and file.filename != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex}_{filename}"
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return {'url': f"/static/uploads/{filename}"}
        
    return {'error': 'Invalid file format'}, 400

@app.route('/post/<string:slug>')
def post(slug):
    p = BlogPost.query.filter_by(slug=slug).first_or_404()
    p.views = (p.views or 0) + 1
    db.session.commit()
    comments = Comment.query.filter_by(post_id=p.id).all()
    return render_template('post.html', post=p, comments=comments)

@app.route('/comment/<id>', methods=['POST'])
def comment(id):
    if 'uid' not in session:
        return redirect(url_for('login'))
    post = BlogPost.query.filter_by(id=id).first()
    
    c = Comment(content=request.form['content'], user_id=session['uid'], post_id=id)
    db.session.add(c)
    db.session.commit()
    return redirect(url_for('post', slug=post.slug))

@app.route('/like/<id>')
def like(id):
    if 'uid' not in session:
        return redirect(url_for('login'))
    post = BlogPost.query.filter_by(id=id).first()
    if not PostLike.query.filter_by(user_id=session['uid'], post_id=id).first():
        db.session.add(PostLike(user_id=session['uid'], post_id=id))
        BlogPost.query.get(id).likes_count += 1
        db.session.commit()
    return redirect(url_for('post', slug=post.slug))

@app.route('/bookmark/<id>')
def bookmark(id):
    if 'uid' not in session:
        
        return redirect(url_for('login'))
    post = BlogPost.query.filter_by(id=id).first()
    
    if not Bookmark.query.filter_by(user_id=session['uid'], post_id=id).first():
        db.session.add(Bookmark(user_id=session['uid'], post_id=id))
        db.session.commit()
    return redirect(url_for('post', slug=post.slug))

@app.route('/profile/<string:username>')
def profile(username):
    u = User.query.filter_by(username=username).first_or_404()
    posts = BlogPost.query.filter_by(user_id=u.id).all()
    return render_template('profile.html', user=u, posts=posts)

@app.route('/search')
def search():
    q = request.args.get('q','')
    posts = BlogPost.query.filter(BlogPost.title.contains(q)).all()
    return render_template('search.html', posts=posts, q=q)

if __name__ == '__main__':
    print("app.run(debug=True)")