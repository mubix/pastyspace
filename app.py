"""PastySpace - a tiny write-once pastebin."""
import base64
import os
import re
import secrets
import sqlite3
import time

from flask import (Flask, Response, abort, g, jsonify, redirect,
                   render_template, request, url_for)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("PASTY_DB", os.path.join(BASE_DIR, "data", "pastyspace.db"))
MAX_MB = int(os.environ.get("PASTY_MAX_MB", "50"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024

with open(os.path.join(BASE_DIR, "wordlist.txt")) as fh:
    WORDS = [w.strip() for w in fh if w.strip()]

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
RESERVED = {"new", "api", "raw", "f", "static", "favicon.ico", "robots.txt"}
SYNTAX_RE = re.compile(r"^[a-z0-9+#_-]{1,24}$")


# --- database -------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS pastes (
            slug TEXT PRIMARY KEY,
            title TEXT,
            syntax TEXT NOT NULL DEFAULT 'auto',
            body TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL REFERENCES pastes(slug) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            mime TEXT NOT NULL,
            size INTEGER NOT NULL,
            data_b64 TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS files_slug ON files(slug);
    """)
    db.commit()
    db.close()


init_db()


# --- helpers --------------------------------------------------------------

def normalize_slug(slug):
    slug = (slug or "").strip().lower()
    if not SLUG_RE.match(slug) or slug in RESERVED:
        return None
    return slug


def random_slug():
    db = get_db()
    for _ in range(50):
        slug = "-".join(secrets.choice(WORDS) for _ in range(3))
        if not db.execute("SELECT 1 FROM pastes WHERE slug=?", (slug,)).fetchone():
            return slug
    abort(503, "Could not find a free name, try again")


def paste_exists(slug):
    return get_db().execute("SELECT 1 FROM pastes WHERE slug=?", (slug,)).fetchone() is not None


def wants_text():
    """True for curl/wget-style clients that want a plain URL back."""
    accept = request.headers.get("Accept", "")
    return "text/html" not in accept and "application/json" not in accept


def create_paste(slug):
    """Insert a paste from the current request. Returns (ok, error)."""
    title, syntax, body, uploads = "", "auto", "", []

    # curl --data-binary sends form-urlencoded by default, so only treat a request
    # as a form if it's multipart or actually carries our "body" field.
    is_form = request.mimetype == "multipart/form-data"
    if request.mimetype == "application/x-www-form-urlencoded":
        raw_data = request.get_data(cache=True)  # cached, so request.form can still parse it
        is_form = "body" in request.form
    elif not is_form:
        raw_data = request.get_data()

    if is_form:
        title = request.form.get("title", "")[:200]
        syntax = request.form.get("syntax", "auto")
        body = request.form.get("body", "")
        for key in request.files:
            for f in request.files.getlist(key):
                data = f.read()
                if not f.filename and not data:
                    continue
                uploads.append((f.filename or "file", f.mimetype or "application/octet-stream", data))
    else:
        # Raw body: `curl --data-binary @file` or `cmd | curl --data-binary @- ...`
        data = raw_data
        ctype = (request.mimetype or "").lower()
        fname = request.args.get("filename", "")
        is_text = (not fname and (ctype.startswith("text/") or ctype in ("", "application/x-www-form-urlencoded")))
        if is_text:
            try:
                body = data.decode("utf-8")
            except UnicodeDecodeError:
                is_text = False
        if not is_text:
            uploads.append((fname or "upload.bin", ctype or "application/octet-stream", data))
        title = request.args.get("title", "")[:200]
        syntax = request.args.get("syntax", "auto")

    if not SYNTAX_RE.match(syntax or ""):
        syntax = "auto"
    if not body.strip() and not uploads:
        return False, "Paste is empty"

    db = get_db()
    try:
        with db:
            db.execute("INSERT INTO pastes (slug, title, syntax, body, created_at) VALUES (?,?,?,?,?)",
                       (slug, title, syntax, body, int(time.time())))
            for name, mime, data in uploads:
                db.execute("INSERT INTO files (slug, filename, mime, size, data_b64) VALUES (?,?,?,?,?)",
                           (slug, os.path.basename(name)[:255], mime, len(data),
                            base64.b64encode(data).decode("ascii")))
    except sqlite3.IntegrityError:
        return False, "That URL was already claimed"
    return True, None


def created_response(slug):
    url = url_for("view", slug=slug, _external=True)
    if wants_text():
        return Response(url + "\n", status=201, mimetype="text/plain")
    return jsonify(slug=slug, url=url), 201


def error_response(msg, code):
    if wants_text():
        return Response(msg + "\n", status=code, mimetype="text/plain")
    return jsonify(error=msg), code


# --- routes ---------------------------------------------------------------

@app.route("/")
def index():
    count = get_db().execute("SELECT COUNT(*) FROM pastes").fetchone()[0]
    return render_template("index.html", count=count)


@app.route("/new")
def new():
    return redirect(url_for("view", slug=random_slug()))


@app.route("/", methods=["POST"])
def post_random():
    slug = random_slug()
    ok, err = create_paste(slug)
    return created_response(slug) if ok else error_response(err, 400)


@app.route("/<slug>", methods=["GET"])
def view(slug):
    norm = normalize_slug(slug)
    if norm is None:
        abort(404)
    if norm != slug:
        return redirect(url_for("view", slug=norm))
    db = get_db()
    paste = db.execute("SELECT * FROM pastes WHERE slug=?", (slug,)).fetchone()
    if paste is None:
        return render_template("edit.html", slug=slug, max_mb=MAX_MB), 404
    files = db.execute("SELECT id, filename, mime, size FROM files WHERE slug=? ORDER BY id",
                       (slug,)).fetchall()
    return render_template("view.html", paste=paste, files=files,
                           created=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(paste["created_at"])))


@app.route("/<slug>", methods=["POST", "PUT"])
def claim(slug):
    norm = normalize_slug(slug)
    if norm is None:
        return error_response("Invalid URL. Use a-z, 0-9, '.', '_' or '-' (max 100 chars).", 400)
    if paste_exists(norm):
        return error_response("That URL was already claimed", 409)
    ok, err = create_paste(norm)
    if ok:
        return created_response(norm)
    return error_response(err, 409 if "claimed" in err else 400)


@app.route("/raw/<slug>")
def raw(slug):
    paste = get_db().execute("SELECT body FROM pastes WHERE slug=?", (slug,)).fetchone()
    if paste is None:
        abort(404)
    resp = Response(paste["body"], mimetype="text/plain")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@app.route("/f/<int:file_id>")
@app.route("/f/<int:file_id>/<path:_name>")
def file_download(file_id, _name=None):
    row = get_db().execute("SELECT filename, mime, data_b64 FROM files WHERE id=?", (file_id,)).fetchone()
    if row is None:
        abort(404)
    resp = Response(base64.b64decode(row["data_b64"]), mimetype=row["mime"])
    disp = "inline" if row["mime"].startswith(("image/", "video/", "audio/")) and "dl" not in request.args else "attachment"
    safe_name = row["filename"].replace('"', "").replace("\r", "").replace("\n", "")
    resp.headers["Content-Disposition"] = f'{disp}; filename="{safe_name}"'
    # Uploaded content is untrusted: never let it run script on our origin (e.g. SVG/HTML).
    resp.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@app.route("/api/random-slug")
def api_random_slug():
    return jsonify(slug=random_slug())


@app.errorhandler(413)
def too_large(_e):
    return error_response(f"Paste too large (max {MAX_MB} MB)", 413)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)
