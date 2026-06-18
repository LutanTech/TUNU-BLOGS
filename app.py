from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, User, BlogPost, Comment, PostLike, Bookmark
from utils import generate_unique_slug

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

        p = BlogPost(
            title=title,
            summary=request.form['summary'],
            content=request.form['content'],
            category=request.form['category'],
            slug=slug,
            user_id=session['uid']
        )

        db.session.add(p)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('create.html')

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
    app.run(debug=True)