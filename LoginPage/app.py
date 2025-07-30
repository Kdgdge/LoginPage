from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "replace-with-random-secret-key"

# API endpoint to fetch chat messages as JSON (for auto-refresh)
@app.route("/show/<int:show_id>/chat/messages")
def get_show_chat_messages(show_id):
    with get_db_connection() as conn:
        messages = conn.execute(
            "SELECT id, username, message, created_at FROM live_show_chats WHERE show_id=? ORDER BY created_at ASC LIMIT 100",
            (show_id,)
        ).fetchall()
        return jsonify([
            {"id": m[0], "username": m[1], "message": m[2], "created_at": m[3]} for m in messages
        ])

# Delete a chat message (moderation, only for chef of the show)
@app.route("/show/<int:show_id>/chat/delete/<int:msg_id>", methods=["POST"])
def delete_show_chat(show_id, msg_id):
    if 'username' not in session or session.get('user_type') != 'chef':
        flash('Only chefs can delete chat messages.', 'error')
        return redirect(url_for('show_detail', show_id=show_id))
    with get_db_connection() as conn:
        # Only allow chef of the show to delete
        chef = conn.execute("SELECT chef_id FROM live_shows WHERE id=?", (show_id,)).fetchone()
        user = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        if not chef or not user or chef['chef_id'] != user['id']:
            flash('Not authorized.', 'error')
            return redirect(url_for('show_detail', show_id=show_id))
        conn.execute("DELETE FROM live_show_chats WHERE id=? AND show_id=?", (msg_id, show_id))
        conn.commit()
        flash('Message deleted.', 'info')
    return redirect(url_for('show_detail', show_id=show_id))

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "replace-with-random-secret-key"

# ...existing code...

@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    with get_db_connection() as conn:
        recipe = conn.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,)).fetchone()
        chef_name = None
        if recipe:
            chef = conn.execute("SELECT username FROM users WHERE id=?", (recipe['chef_id'],)).fetchone()
            chef_name = chef['username'] if chef else "Unknown"
        if not recipe:
            flash("Recipe not found.", "error")
            return redirect(url_for('home'))
    return render_template("recipe_detail.html", recipe=recipe, chef_name=chef_name)

DB_PATH = os.path.join(app.root_path, "user.db")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'recipe_images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        # Muted users table for live shows
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS live_show_muted (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(show_id, user_id),
                FOREIGN KEY (show_id) REFERENCES live_shows(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )'''
        )
        conn.commit()
        # Live chat table for shows
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS live_show_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (show_id) REFERENCES live_shows(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )'''
        )
        conn.commit()
import filetype
# Post a chat message to a live show (with optional image upload)
@app.route("/show/<int:show_id>/chat", methods=["POST"])
def post_show_chat(show_id):
    if 'username' not in session:
        flash('Please log in to chat.', 'error')
        return redirect(url_for('show_detail', show_id=show_id))
    message = request.form.get('message', '').strip()
    image_url = None
    # Handle image upload
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
            upload_folder = os.path.join(app.root_path, 'static', 'chat_uploads')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            # Validate image type using filetype
            kind = filetype.guess(file_path)
            if kind and kind.extension in ALLOWED_EXTENSIONS:
                image_url = f"/static/chat_uploads/{filename}"
            else:
                os.remove(file_path)
                flash('Invalid image file.', 'error')
                return redirect(url_for('show_detail', show_id=show_id))
    if not message and not image_url:
        flash('Message or image required.', 'error')
        return redirect(url_for('show_detail', show_id=show_id))
    with get_db_connection() as conn:
        user = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('show_detail', show_id=show_id))
        # Check if user is muted for this show
        muted = conn.execute("SELECT 1 FROM live_show_muted WHERE show_id=? AND user_id=?", (show_id, user['id'])).fetchone()
        if muted:
            flash('You have been muted for this show.', 'error')
            return redirect(url_for('show_detail', show_id=show_id))
        # Add image_url column if missing
        chat_cols = conn.execute("PRAGMA table_info(live_show_chats)").fetchall()
        chat_col_names = [col['name'] for col in chat_cols]
        if 'image_url' not in chat_col_names:
            conn.execute("ALTER TABLE live_show_chats ADD COLUMN image_url TEXT")
        conn.execute(
            "INSERT INTO live_show_chats (show_id, user_id, username, message, image_url) VALUES (?, ?, ?, ?, ?)",
            (show_id, user['id'], session['username'], message, image_url)
        )
        conn.commit()
    return redirect(url_for('show_detail', show_id=show_id))

# Mute a user for a live show (chef only)
@app.route("/show/<int:show_id>/mute/<int:user_id>", methods=["POST"])
def mute_show_user(show_id, user_id):
    if 'username' not in session or session.get('user_type') != 'chef':
        flash('Only chefs can mute users.', 'error')
        return redirect(url_for('show_detail', show_id=show_id))
    with get_db_connection() as conn:
        chef = conn.execute("SELECT chef_id FROM live_shows WHERE id=?", (show_id,)).fetchone()
        user = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        if not chef or not user or chef['chef_id'] != user['id']:
            flash('Not authorized.', 'error')
            return redirect(url_for('show_detail', show_id=show_id))
        try:
            conn.execute("INSERT OR IGNORE INTO live_show_muted (show_id, user_id) VALUES (?, ?)", (show_id, user_id))
            conn.commit()
            flash('User muted.', 'info')
        except Exception:
            flash('Could not mute user.', 'error')
    return redirect(url_for('show_detail', show_id=show_id))

# Unmute a user for a live show (chef only)
@app.route("/show/<int:show_id>/unmute/<int:user_id>", methods=["POST"])
def unmute_show_user(show_id, user_id):
    if 'username' not in session or session.get('user_type') != 'chef':
        flash('Only chefs can unmute users.', 'error')
        return redirect(url_for('show_detail', show_id=show_id))
    with get_db_connection() as conn:
        chef = conn.execute("SELECT chef_id FROM live_shows WHERE id=?", (show_id,)).fetchone()
        user = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        if not chef or not user or chef['chef_id'] != user['id']:
            flash('Not authorized.', 'error')
            return redirect(url_for('show_detail', show_id=show_id))
        conn.execute("DELETE FROM live_show_muted WHERE show_id=? AND user_id=?", (show_id, user_id))
        conn.commit()
        flash('User unmuted.', 'info')
    return redirect(url_for('show_detail', show_id=show_id))
# RSVP to a live show
@app.route("/rsvp_show/<int:show_id>", methods=["POST"])
def rsvp_show(show_id):
    if 'username' not in session or session.get('user_type') != 'customer':
        flash('Please log in as a customer to RSVP.', 'error')
        return redirect(url_for('show_detail', show_id=show_id))
    with get_db_connection() as conn:
        user = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('show_detail', show_id=show_id))
        try:
            conn.execute("INSERT INTO live_show_rsvps (show_id, user_id) VALUES (?, ?)", (show_id, user['id']))
            conn.commit()
            flash('RSVP confirmed! You will be reminded.', 'success')
        except Exception:
            flash('You have already RSVPed for this show.', 'info')
    return redirect(url_for('show_detail', show_id=show_id))

# Un-RSVP from a live show
@app.route("/unrsvp_show/<int:show_id>", methods=["POST"])
def unrsvp_show(show_id):
    if 'username' not in session or session.get('user_type') != 'customer':
        flash('Please log in as a customer to update RSVP.', 'error')
        return redirect(url_for('show_detail', show_id=show_id))
    with get_db_connection() as conn:
        user = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('show_detail', show_id=show_id))
        conn.execute("DELETE FROM live_show_rsvps WHERE show_id=? AND user_id=?", (show_id, user['id']))
        conn.commit()
        flash('RSVP removed.', 'info')
    return redirect(url_for('show_detail', show_id=show_id))
# Route for chefs/admins to create and manage live shows
from datetime import datetime


# Manage, edit, and delete live shows
@app.route("/manage_live_shows", methods=["GET", "POST"])
def manage_live_shows():
    if 'username' not in session or session.get('user_type') != 'chef':
        flash('Access denied. Only chefs can manage live shows.', 'error')
        return redirect(url_for('home'))
    with get_db_connection() as conn:
        chef = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        # Handle add or edit
        if request.method == "POST":
            action = request.form.get('action', 'add')
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            start_time = request.form.get('start_time', '').strip()
            status = request.form.get('status', 'upcoming')
            show_id = request.form.get('show_id')
            if action == 'edit' and show_id:
                # Edit existing show
                if title and start_time and status in ("live", "upcoming", "ended"):
                    try:
                        dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
                        conn.execute(
                            "UPDATE live_shows SET title=?, description=?, start_time=?, status=? WHERE id=? AND chef_id=?",
                            (title, description, dt.isoformat(' '), status, show_id, chef['id'])
                        )
                        conn.commit()
                        flash('Live show updated!', 'success')
                    except Exception as e:
                        flash(f'Error: {e}', 'error')
                else:
                    flash('All fields are required and status must be valid.', 'error')
            elif action == 'add':
                if title and start_time and status in ("live", "upcoming", "ended"):
                    try:
                        dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
                        conn.execute(
                            "INSERT INTO live_shows (title, description, start_time, status, chef_id) VALUES (?, ?, ?, ?, ?)",
                            (title, description, dt.isoformat(' '), status, chef['id'])
                        )
                        conn.commit()
                        flash('Live show created!', 'success')
                    except Exception as e:
                        flash(f'Error: {e}', 'error')
                else:
                    flash('All fields are required and status must be valid.', 'error')
# Show details page (for customers and chefs)
@app.route("/show/<int:show_id>")
def show_detail(show_id):
    user_rsvped = False
    rsvp_count = 0
    chat_messages = []
    is_chef = False
    with get_db_connection() as conn:
        show = conn.execute("SELECT live_shows.*, users.username as chef_name FROM live_shows JOIN users ON live_shows.chef_id = users.id WHERE live_shows.id=?", (show_id,)).fetchone()
        if show:
            rsvp_count = conn.execute("SELECT COUNT(*) FROM live_show_rsvps WHERE show_id=?", (show_id,)).fetchone()[0]
            if 'username' in session:
                user = conn.execute("SELECT id, user_type FROM users WHERE username=?", (session['username'],)).fetchone()
                if user and user['user_type'] == 'customer':
                    user_rsvped = conn.execute("SELECT 1 FROM live_show_rsvps WHERE show_id=? AND user_id=?", (show_id, user['id'])).fetchone() is not None
                if user and user['user_type'] == 'chef' and show['chef_id'] == user['id']:
                    is_chef = True
            # Fetch chat messages for live shows (with image_url)
            if show['status'] == 'live':
                # Add image_url column if missing
                chat_cols = conn.execute("PRAGMA table_info(live_show_chats)").fetchall()
                chat_col_names = [col['name'] for col in chat_cols]
                if 'image_url' not in chat_col_names:
                    conn.execute("ALTER TABLE live_show_chats ADD COLUMN image_url TEXT")
                chat_messages = conn.execute(
                    "SELECT id, username, message, created_at, image_url, user_id FROM live_show_chats WHERE show_id=? ORDER BY created_at ASC LIMIT 100",
                    (show_id,)
                ).fetchall()
                # Get muted user ids for this show (for chef UI)
                muted_user_ids = set()
                if is_chef:
                    muted = conn.execute("SELECT user_id FROM live_show_muted WHERE show_id=?", (show_id,)).fetchall()
                    muted_user_ids = set([row['user_id'] for row in muted])
                else:
                    muted_user_ids = set()
            else:
                muted_user_ids = set()
    if not show:
        flash("Show not found.", "error")
        return redirect(url_for('home'))
    return render_template("show_detail.html", show=show, rsvp_count=rsvp_count, user_rsvped=user_rsvped, chat_messages=chat_messages, is_chef=is_chef, muted_user_ids=muted_user_ids)
    # Fetch shows for display and editing
    shows = conn.execute("SELECT * FROM live_shows WHERE chef_id=? ORDER BY start_time DESC", (chef['id'],)).fetchall()
    edit_show = None
    edit_id = request.args.get('edit_id')
    if edit_id:
        edit_show = conn.execute("SELECT * FROM live_shows WHERE id=? AND chef_id=?", (edit_id, chef['id'])).fetchone()
    return render_template("manage_live_shows.html", shows=shows, edit_show=edit_show)

# Route to delete a live show
@app.route("/delete_live_show/<int:show_id>", methods=["POST"])
def delete_live_show(show_id):
    if 'username' not in session or session.get('user_type') != 'chef':
        flash('Access denied. Only chefs can delete live shows.', 'error')
        return redirect(url_for('home'))
    with get_db_connection() as conn:
        chef = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        conn.execute("DELETE FROM live_shows WHERE id=? AND chef_id=?", (show_id, chef['id']))
        conn.commit()
        flash('Live show deleted!', 'success')
    return redirect(url_for('manage_live_shows'))
# Live show page for chefs
@app.route('/live_show', methods=['GET', 'POST'])
def live_show():
    if 'username' not in session or session.get('user_type') != 'chef':
        flash('Access denied. Only chefs can host live shows.', 'error')
        return redirect(url_for('home'))
    invites = []
    if request.method == 'POST':
        invite_message = request.form.get('invite_message', '').strip()
        if invite_message:
            with get_db_connection() as conn:
                conn.execute(
                    'INSERT INTO live_invites (chef_username, message) VALUES (?, ?)',
                    (session['username'], invite_message)
                )
                conn.commit()
            flash('Invite sent to your customers!', 'success')
    # Show previous invites
    with get_db_connection() as conn:
        invites = conn.execute(
            'SELECT message, timestamp FROM live_invites WHERE chef_username=? ORDER BY timestamp DESC LIMIT 5',
            (session['username'],)
        ).fetchall()
    return render_template('live_show.html', invites=invites)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    if 'username' in session:
        return redirect(url_for('home'))
    return redirect(url_for("login"))

@app.route("/home")
def home():
    if 'username' not in session:
        flash("Please login first", "error")
        return redirect(url_for('login'))
    # Get user type and latest recipes from database
    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT user_type FROM users WHERE username=?", (session['username'],)
        ).fetchone()
        user_type = user['user_type'] if user else 'customer'
        # Get latest 5 recipes with chef name
        latest_recipes = conn.execute(
            """
            SELECT recipes.*, users.username as chef_name FROM recipes
            JOIN users ON recipes.chef_id = users.id
            ORDER BY recipes.id DESC LIMIT 5
            """
        ).fetchall()
    return render_template("home.html", username=session['username'], user_type=user_type, latest_recipes=latest_recipes)

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
        
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username=? AND password=?", (username, password)
            ).fetchone()
            if user:
                session['username'] = username
                session['user_type'] = user['user_type'] # Store user type in session
                flash("Logged in successfully!", "success")
                return redirect(url_for("home"))
            else:
                flash("Invalid credentials", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('username', None)
    flash("You have been logged out", "success")
    return redirect(url_for('login'))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user_type = request.form["user_type"]  # Get user type from form
        try:
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO users (username, password, user_type) VALUES (?, ?, ?)", 
                    (username, password, user_type)  # Include user_type
                )
                conn.commit()
                flash("Account created! Please login.", "success")
                return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists", "error")
    return render_template("signup.html")

@app.route("/browse_chefs")
def browse_chefs():
    with get_db_connection() as conn:
        chefs = conn.execute("SELECT username, profile_info FROM users WHERE user_type='chef'").fetchall()
    return render_template("browse_chefs.html", chefs=chefs)

@app.route("/chef_profile/<username>")
def chef_profile(username):
    with get_db_connection() as conn:
        chef = conn.execute("SELECT username, profile_info FROM users WHERE username=? AND user_type='chef'", (username,)).fetchone()
        if not chef:
            flash("Chef not found.", "error")
            return redirect(url_for('browse_chefs'))
        recipes = conn.execute("SELECT * FROM recipes WHERE chef_id=(SELECT id FROM users WHERE username=?)", (username,)).fetchall()
    return render_template("chef_profile.html", chef=chef, recipes=recipes)

@app.route("/view_menu")
def view_menu():
    if 'username' not in session or session.get('user_type') != 'customer':
        flash("Access denied. Only customers can view the menu.", "error")
        return redirect(url_for('home'))
    with get_db_connection() as conn:
        # Get the current user's ID
        current_user = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        
        # Get recipes with chef names, ratings, and comments
        recipes = conn.execute("""
            SELECT 
                recipes.*,
                users.username as chef_name,
                COALESCE(avg_ratings.avg_rating, 0) as avg_rating,
                user_ratings.rating as user_rating,
                GROUP_CONCAT(
                    json_object(
                        'text', comments.comment_text,
                        'username', comment_users.username,
                        'date', comments.created_at
                    ),
                    '||'
                ) as comments
            FROM recipes 
            JOIN users ON recipes.chef_id = users.id
            LEFT JOIN (
                SELECT recipe_id, AVG(rating) as avg_rating 
                FROM ratings 
                GROUP BY recipe_id
            ) avg_ratings ON recipes.id = avg_ratings.recipe_id
            LEFT JOIN ratings user_ratings 
                ON recipes.id = user_ratings.recipe_id 
                AND user_ratings.user_id = ?
            LEFT JOIN comments 
                ON recipes.id = comments.recipe_id
            LEFT JOIN users comment_users 
                ON comments.user_id = comment_users.id
            GROUP BY recipes.id
        """, (current_user['id'],)).fetchall()
        
        import json
        processed_recipes = []
        for recipe in recipes:
            recipe_dict = dict(recipe)
            comments_str = recipe_dict.get('comments')
            comments_list = []
            if comments_str:
                for c in comments_str.split('||'):
                    try:
                        comments_list.append(json.loads(c))
                    except Exception:
                        comments_list.append({'text': c, 'username': 'Anonymous', 'date': ''})
            recipe_dict['comments'] = comments_list
            processed_recipes.append(recipe_dict)
            
    return render_template("view_menu.html", recipes=processed_recipes)

@app.route("/order/<int:recipe_id>", methods=["POST"])
def order_recipe(recipe_id):
    if 'username' not in session or session.get('user_type') != 'customer':
        flash("Access denied. Only customers can order.", "error")
        return redirect(url_for('home'))
    quantity = request.form.get('quantity', 1)
    instructions = request.form.get('instructions', '').strip()
    with get_db_connection() as conn:
        customer = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        # For now, store quantity and instructions in the status field for demonstration (since orders table does not have these columns)
        status = f"pending | qty:{quantity} | note:{instructions}" if instructions else f"pending | qty:{quantity}"
        conn.execute("INSERT INTO orders (customer_id, recipe_id, status) VALUES (?, ?, ?)", (customer['id'], recipe_id, status))
        conn.commit()
    flash("Order placed!", "success")
    return redirect(url_for('view_menu'))

@app.route("/order_history")
def order_history():
    if 'username' not in session or session.get('user_type') != 'customer':
        flash("Access denied. Only customers can view order history.", "error")
        return redirect(url_for('home'))
    from datetime import datetime
    with get_db_connection() as conn:
        customer = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        orders = conn.execute("SELECT orders.*, recipes.title, recipes.description, users.username as chef_name FROM orders JOIN recipes ON orders.recipe_id = recipes.id JOIN users ON recipes.chef_id = users.id WHERE orders.customer_id=? ORDER BY orders.timestamp DESC", (customer['id'],)).fetchall()
        # Fetch live and upcoming shows
        now = datetime.now().isoformat(' ')
        # If you don't have a live_shows table, create it as described previously
        live_shows = conn.execute(
            "SELECT * FROM live_shows WHERE status='live' AND start_time<=? ORDER BY start_time ASC", (now,)
        ).fetchall() if 'live_shows' in [row['name'] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else []
        upcoming_shows = conn.execute(
            "SELECT * FROM live_shows WHERE status='upcoming' AND start_time> ? ORDER BY start_time ASC", (now,)
        ).fetchall() if 'live_shows' in [row['name'] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else []
    return render_template("order_history.html", orders=orders, live_shows=live_shows, upcoming_shows=upcoming_shows)

@app.route("/manage_recipes")
def manage_recipes():
    if 'username' not in session or session.get('user_type') != 'chef':
        flash("Access denied. Only chefs can manage recipes.", "error")
        return redirect(url_for('home'))
    with get_db_connection() as conn:
        chef = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        recipes = conn.execute("SELECT * FROM recipes WHERE chef_id=?", (chef['id'],)).fetchall()
    return render_template("manage_recipes.html", recipes=recipes)

@app.route("/add_recipe", methods=["GET", "POST"])
def add_recipe():
    if 'username' not in session or session.get('user_type') != 'chef':
        flash("Access denied. Only chefs can add recipes.", "error")
        return redirect(url_for('home'))
    if request.method == "POST":
        title = request.form['title']
        description = request.form['description']
        ingredients = request.form['ingredients']
        instructions = request.form['instructions']
        rating = int(request.form.get('rating', 0))
        comment = request.form.get('comment', '').strip()
        image_file = request.files.get('image')
        video_file = request.files.get('video')
        image_filename = None
        video_filename = None
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            image_file.save(image_path)
            image_filename = unique_name
        # Video upload
        if video_file and video_file.filename and video_file.filename.lower().endswith('.mp4'):
            video_folder = os.path.join(app.root_path, 'static', 'recipe_videos')
            os.makedirs(video_folder, exist_ok=True)
            video_filename = f"{uuid.uuid4().hex}_{secure_filename(video_file.filename)}"
            video_path = os.path.join(video_folder, video_filename)
            video_file.save(video_path)
        with get_db_connection() as conn:
            chef = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
            conn.execute(
                "INSERT INTO recipes (chef_id, title, description, ingredients, instructions, image_filename, video_filename, rating, comment) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (chef['id'], title, description, ingredients, instructions, image_filename, video_filename, rating, comment)
            )
            conn.commit()
        flash("Recipe added!", "success")
        return redirect(url_for('manage_recipes'))
    return render_template("add_recipe.html")

@app.route("/edit_recipe/<int:recipe_id>", methods=["GET", "POST"])
def edit_recipe(recipe_id):
    if 'username' not in session or session.get('user_type') != 'chef':
        flash("Access denied. Only chefs can edit recipes.", "error")
        return redirect(url_for('home'))
    with get_db_connection() as conn:
        recipe = conn.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,)).fetchone()
        chef = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        if not recipe or recipe['chef_id'] != chef['id']:
            abort(403)
        if request.method == "POST":
            title = request.form['title']
            description = request.form['description']
            ingredients = request.form['ingredients']
            instructions = request.form['instructions']
            image_file = request.files.get('image')
            image_filename = recipe['image_filename']
            if image_file and allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                image_file.save(image_path)
                image_filename = unique_name
            conn.execute(
                "UPDATE recipes SET title=?, description=?, ingredients=?, instructions=?, image_filename=? WHERE id=?",
                (title, description, ingredients, instructions, image_filename, recipe_id)
            )
            conn.commit()
            flash("Recipe updated!", "success")
            return redirect(url_for('manage_recipes'))
    return render_template("edit_recipe.html", recipe=recipe)

@app.route("/delete_recipe/<int:recipe_id>", methods=["POST"])
def delete_recipe(recipe_id):
    if 'username' not in session or session.get('user_type') != 'chef':
        flash("Access denied. Only chefs can delete recipes.", "error")
        return redirect(url_for('home'))
    with get_db_connection() as conn:
        recipe = conn.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,)).fetchone()
        chef = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        if not recipe or recipe['chef_id'] != chef['id']:
            abort(403)
        conn.execute("DELETE FROM recipes WHERE id=?", (recipe_id,))
        conn.commit()
        flash("Recipe deleted!", "success")
    return redirect(url_for('manage_recipes'))

@app.route("/view_orders")
def view_orders():
    if 'username' not in session or session.get('user_type') != 'chef':
        flash("Access denied. Only chefs can view orders.", "error")
        return redirect(url_for('home'))
    with get_db_connection() as conn:
        chef = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        orders = conn.execute("""
            SELECT orders.*, recipes.title, users.username as customer_name
            FROM orders
            JOIN recipes ON orders.recipe_id = recipes.id
            JOIN users ON orders.customer_id = users.id
            WHERE recipes.chef_id=?
            ORDER BY orders.timestamp DESC
        """, (chef['id'],)).fetchall()
    return render_template("view_orders.html", orders=orders)

@app.route("/update_order_status/<int:order_id>", methods=["POST"])
def update_order_status(order_id):
    if 'username' not in session or session.get('user_type') != 'chef':
        flash("Access denied. Only chefs can update order status.", "error")
        return redirect(url_for('home'))
    new_status = request.form.get('status')
    if new_status not in ['pending', 'accepted', 'completed', 'cancelled']:
        flash("Invalid status.", "error")
        return redirect(url_for('view_orders'))
    with get_db_connection() as conn:
        # Ensure the order belongs to a recipe by this chef
        chef = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        order = conn.execute("SELECT orders.*, recipes.chef_id FROM orders JOIN recipes ON orders.recipe_id = recipes.id WHERE orders.id=?", (order_id,)).fetchone()
        if not order or order['chef_id'] != chef['id']:
            flash("Order not found or access denied.", "error")
            return redirect(url_for('view_orders'))
        conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
        conn.commit()
        flash("Order status updated!", "success")
    return redirect(url_for('view_orders'))

@app.route("/add_comment/<int:recipe_id>", methods=["POST"])
def add_comment(recipe_id):
    if 'username' not in session:
        flash("Please log in to add a comment.", "error")
        return redirect(url_for('login'))
        
    comment_text = request.form.get('comment')
    if not comment_text or len(comment_text) > 180:
        flash("Comment must be between 1 and 180 characters.", "error")
        return redirect(url_for('view_menu'))
        
    with get_db_connection() as conn:
        # Get user ID
        user = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        if not user:
            flash("User not found.", "error")
            return redirect(url_for('view_menu'))
            
        # Check if recipe exists
        recipe = conn.execute("SELECT id FROM recipes WHERE id=?", (recipe_id,)).fetchone()
        if not recipe:
            flash("Recipe not found.", "error")
            return redirect(url_for('view_menu'))
            
        # Add comment
        conn.execute("""
            INSERT INTO comments (recipe_id, user_id, comment_text)
            VALUES (?, ?, ?)
        """, (recipe_id, user['id'], comment_text))
        conn.commit()
        
        flash("Comment added successfully!", "success")
    return redirect(url_for('view_menu'))

@app.route("/add_rating/<int:recipe_id>", methods=["POST"])
def add_rating(recipe_id):
    if 'username' not in session:
        flash("Please log in to rate recipes.", "error")
        return redirect(url_for('login'))
        
    rating = request.form.get('rating')
    try:
        rating = int(rating)
        if not 1 <= rating <= 5:
            raise ValueError()
    except (TypeError, ValueError):
        flash("Rating must be between 1 and 5.", "error")
        return redirect(url_for('view_menu'))
        
    with get_db_connection() as conn:
        # Get user ID
        user = conn.execute("SELECT id FROM users WHERE username=?", (session['username'],)).fetchone()
        if not user:
            flash("User not found.", "error")
            return redirect(url_for('view_menu'))
            
        # Check if recipe exists
        recipe = conn.execute("SELECT id FROM recipes WHERE id=?", (recipe_id,)).fetchone()
        if not recipe:
            flash("Recipe not found.", "error")
            return redirect(url_for('view_menu'))
            
        try:
            # Add or update rating
            conn.execute("""
                INSERT INTO ratings (recipe_id, user_id, rating)
                VALUES (?, ?, ?)
                ON CONFLICT(recipe_id, user_id) 
                DO UPDATE SET rating = excluded.rating
            """, (recipe_id, user['id'], rating))
            conn.commit()
            flash("Rating updated successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Error updating rating.", "error")
            
    return redirect(url_for('view_menu'))
@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if 'username' not in session or session.get('user_type') != 'chef':
        flash("Access denied. Only chefs can edit their profile.", "error")
        return redirect(url_for('home'))
    with get_db_connection() as conn:
        chef = conn.execute("SELECT * FROM users WHERE username=?", (session['username'],)).fetchone()
        if request.method == "POST":
            profile_info = request.form.get('profile_info', '')
            contact = request.form.get('contact', '')
            social = request.form.get('social', '')
            email = request.form.get('email', '')
            password = request.form.get('password', '')
            theme = request.form.get('theme', '')
            # Handle profile picture upload
            profile_pic_url = chef['profile_pic_url'] if chef and 'profile_pic_url' in chef.keys() else None
            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
                    upload_folder = os.path.join(app.root_path, 'static', 'profile_pics')
                    os.makedirs(upload_folder, exist_ok=True)
                    file_path = os.path.join(upload_folder, filename)
                    file.save(file_path)
                    profile_pic_url = f"/static/profile_pics/{filename}"
            # Update user info
            update_fields = ["profile_info = ?", "contact = ?", "social = ?", "email = ?"]
            update_values = [profile_info, contact, social, email]
            if profile_pic_url:
                update_fields.append("profile_pic_url = ?")
                update_values.append(profile_pic_url)
            if theme:
                update_fields.append("theme = ?")
                update_values.append(theme)
            if password:
                update_fields.append("password = ?")
                update_values.append(password)
            update_values.append(session['username'])
            try:
                conn.execute(f"UPDATE users SET {', '.join(update_fields)} WHERE username=?", tuple(update_values))
                conn.commit()
                flash("Profile updated!", "success")
                return redirect(url_for('chef_profile', username=session['username']))
            except Exception as e:
                flash(f"Error updating profile: {e}", "error")
        # Pass all fields to template for UI interactivity
        return render_template(
            "edit_profile.html",
            profile_info=chef['profile_info'] if chef else "",
            contact=chef['contact'] if chef and 'contact' in chef.keys() else "",
            social=chef['social'] if chef and 'social' in chef.keys() else "",
            email=chef['email'] if chef and 'email' in chef.keys() else "",
            profile_pic_url=chef['profile_pic_url'] if chef and 'profile_pic_url' in chef.keys() else None,
            theme=chef['theme'] if chef and 'theme' in chef.keys() else ""
        )

if __name__ == "__main__":
    init_db()
    app.run(debug=True) 