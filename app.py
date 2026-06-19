import os
import uuid
from functools import wraps
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from models import db, User, BlogPost, Comment, PostLike, Bookmark
from utils import generate_unique_slug

User.is_admin = property(lambda self: self.role == 'admin')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'jfif', 'gif'}

migrate = Migrate(app, db)
db.init_app(app)

with app.app_context():
    db.create_all()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'uid' not in session:
            return redirect(url_for('login'))
        u = User.query.get(session['uid'])
        if not u:
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_post_by_id_or_slug(identifier):
    if str(identifier).isdigit():
        return BlogPost.query.get(int(identifier))
    return BlogPost.query.filter_by(slug=identifier).first()

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
    return render_template('login.html')

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
@login_required
def dashboard():
    u = User.query.get(session['uid'])

    if not u or u.role not in ['creator', 'admin']:
        flash('Access Denied: Admin privileges required.')
        return redirect(url_for('index'))

    posts = BlogPost.query.filter_by(user_id=u.id).all()
    return render_template('dashboard.html', user=u, posts=posts)

@app.route('/admin')
@login_required
def admin_panel():
    u = User.query.get(session['uid'])
    if not u or not u.is_admin:
        flash('Access Denied: Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    posts = BlogPost.query.all()
    
    users_count = len(users)
    posts_count = len(posts)
    
    return render_template(
        'admin.html',
        user=u,
        users=users,
        posts=posts,
        users_count=users_count,
        posts_count=posts_count
    )

@app.route('/toggle-admin/<int:id>', methods=['POST'])
@login_required
def toggle_admin(id):
    u = User.query.get(session['uid'])
    if not u or not u.is_admin:
        return "Unauthorized", 403
        
    target_user = User.query.get_or_404(id)
    if target_user.id == u.id:
        flash("You cannot demote yourself!")
        return redirect(url_for('admin_panel'))
        
    target_user.role = 'user' if target_user.is_admin else 'admin'
    db.session.commit()
    flash(f"Permissions updated for {target_user.username}!")
    return redirect(url_for('admin_panel'))

@app.route('/delete-user/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    u = User.query.get(session['uid'])
    if not u or not u.is_admin:
        return "Unauthorized", 403
        
    target_user = User.query.get_or_404(id)
    if target_user.id == u.id:
        flash("You cannot delete your own account!")
        return redirect(url_for('admin_panel'))
        
    db.session.delete(target_user)
    db.session.commit()
    flash('User account deleted!')
    return redirect(url_for('admin_panel'))

@app.route('/create', methods=['GET','POST'])
@login_required
def create():
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

@app.route('/edit/<string:identifier>', methods=['GET', 'POST'])
@login_required
def edit_post(identifier):
    u = User.query.get(session['uid'])
    p = get_post_by_id_or_slug(identifier)
    if not p:
        return "Not Found", 404
        
    if p.user_id != u.id and not u.is_admin:
        return "Unauthorized", 403
        
    if request.method == 'POST':
        p.title = request.form['title']
        p.summary = request.form['summary']
        p.category = request.form['category']
        p.content = request.form['content']
        
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{p.slug}.{ext}"
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                p.cover_image = f"/static/uploads/{filename}"
                
        db.session.commit()
        return redirect(url_for('dashboard'))
        
    return render_template('create.html', post=p)

@app.route('/delete/<string:identifier>', methods=['POST'])
@login_required
def delete_post(identifier):
    u = User.query.get(session['uid'])
    p = get_post_by_id_or_slug(identifier)
    if not p:
        return "Not Found", 404
        
    if p.user_id != u.id and not u.is_admin:
        return "Unauthorized", 403
        
    db.session.delete(p)
    db.session.commit()
    flash('Article deleted successfully!')
    ref = request.referrer or ''
    if 'admin' in ref:
        return redirect(url_for('admin_panel'))
    return redirect(url_for('dashboard'))

@app.route('/upload-inline', methods=['POST'])
def upload_inline():
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

@app.route('/post/<string:identifier>')
def post(identifier):
    p = get_post_by_id_or_slug(identifier)
    if not p:
        return "Not Found", 404
    p.views = (p.views or 0) + 1
    db.session.commit()
    comments = Comment.query.filter_by(post_id=p.id).all()
    return render_template('post.html', post=p, comments=comments)

@app.route('/comment/<string:identifier>', methods=['POST'])
@login_required
def comment(identifier):
    post_item = get_post_by_id_or_slug(identifier)
    if not post_item:
        return "Not Found", 404
    c = Comment(content=request.form['content'], user_id=session['uid'], post_id=post_item.id)
    db.session.add(c)
    db.session.commit()
    return redirect(url_for('post', identifier=post_item.slug))

@app.route('/like/<string:identifier>')
@login_required
def like(identifier):
    post_item = get_post_by_id_or_slug(identifier)
    if not post_item:
        return "Not Found", 404
    if not PostLike.query.filter_by(user_id=session['uid'], post_id=post_item.id).first():
        db.session.add(PostLike(user_id=session['uid'], post_id=post_item.id))
        post_item.likes_count += 1
        db.session.commit()
    return redirect(url_for('post', identifier=post_item.slug))

@app.route('/bookmark/<string:identifier>')
@login_required
def bookmark(identifier):
    post_item = get_post_by_id_or_slug(identifier)
    if not post_item:
        return "Not Found", 404
    if not Bookmark.query.filter_by(user_id=session['uid'], post_id=post_item.id).first():
        db.session.add(Bookmark(user_id=session['uid'], post_id=post_item.id))
        db.session.commit()
    return redirect(url_for('post', identifier=post_item.slug))

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
    app.run(debug=True)