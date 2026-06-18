import re
import unicodedata

def make_slug(text):
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return '-'.join(text.split())

def generate_unique_slug(db, BlogPost, title):
    base_slug = make_slug(title)
    slug = base_slug
    counter = 1

    while BlogPost.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug