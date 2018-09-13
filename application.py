import os
import requests

from flask import Flask, session, render_template, request, url_for, redirect
from flask_session import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

loggedin = False
user = None


@app.route("/")
def index():
    return render_template("index.html", user=user, loggedin=loggedin, cond=loggedin)


@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "GET":
        return render_template("search.html", loggedin=loggedin)
    else:
        input = request.form.get("search").lower()
        results = db.execute("SELECT * FROM books WHERE isbn = :i OR LOWER(title) LIKE :x OR LOWER(author) LIKE :x", {"i": input, "x": "%" + input + "%"}).fetchall()
        count = db.execute("SELECT count(*) FROM books WHERE isbn = :i OR LOWER(title) LIKE :x OR LOWER(author) LIKE :x", {"i": input, "x": "%" + input + "%"}).fetchone()

        return render_template("search.html", result=True, books=results, count=count[0], loggedin=loggedin, input=input)


@app.route("/login", methods=["GET", "POST"])
def login():
    global loggedin
    global user

    if request.method == "GET":
        return render_template("login.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")

        one = db.execute("SELECT * FROM users WHERE username = :u", {"u": username}).fetchone()
        if one == None:
            return render_template("login.html", cond=True, type="alert-danger",
                                   message="username is incorrect or does not exist, register first")
        else:
            if one.password != password:
                return render_template("login.html", cond=True, type="alert-danger",
                                       message="password is incorrect")
            else:
                loggedin = True
                user = username
                return render_template("index.html", cond=loggedin, user=user, loggedin=loggedin)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        firstname = request.form.get("firstname")
        lastname = request.form.get("lastname")
        username = request.form.get("username")
        password = request.form.get("password")

        one = db.execute("SELECT * FROM users WHERE username = :u", {"u": username}).fetchone()

        if one == None:
            db.execute("INSERT INTO users (firstname, lastname, username, password) VALUES (:f, :l, :u, :p)",
                       {"f": firstname, "l": lastname, "u": username, "p": password})
            db.commit()
            return render_template("login.html", cond=True, type="alert-success",
                                   message="You have successfully registered, you may now login")
        else:
            return render_template("register.html", cond=True, type="alert-danger",
                                   message="The username is already taken")


@app.route("/logout")
def logout():
    global user
    global loggedin

    user = None
    loggedin = False

    return redirect(url_for('index'))


@app.route("/book/<string:isbn>", methods=["POST", "GET"])
def bookpage(isbn):
    book = db.execute("SELECT * FROM books WHERE isbn = :i", {"i": isbn}).fetchone()

    res = requests.get(f"https://www.goodreads.com/book/review_counts.json?isbns={isbn}&key=Kc62cBqOVe7j6NJUipu9wQ")

    avg_rating = res.json()["books"][0]["average_rating"]
    ratings_ct = res.json()["books"][0]["ratings_count"]

    reviews = db.execute("SELECT * FROM reviews WHERE isbn = :i", {"i": isbn}).fetchall()

    if request.method == "GET":
        if book == None:
            return "Book not found"
        else:
            return render_template("bookpage.html", book=book, avg_rating=avg_rating, ratings_ct=ratings_ct,
                                   loggedin=loggedin, reviews=reviews, user=user)
    else:
        one = db.execute("SELECT * FROM reviews WHERE username = :u", {"u": user}).fetchone()
        if one == None:
            comment = request.form.get("comment")
            rating = request.form.get("rating")

            if len(comment) > 500:
                return render_template("bookpage.html", book=book, avg_rating=avg_rating, ratings_ct=ratings_ct,
                                       loggedin=loggedin, reviews=reviews, user=user, acond=True)

            db.execute(text("INSERT INTO reviews (username, isbn, comment, rating) VALUES (:u, :i, :c, :r)"),
                       {"u": user, "i": isbn, "c": comment, "r": rating})

            db.commit()

            reviews = db.execute("SELECT * FROM reviews WHERE isbn = :i", {"i": isbn}).fetchall()

            return render_template("bookpage.html", book=book, avg_rating=avg_rating, ratings_ct=ratings_ct,
                                   loggedin=loggedin, reviews=reviews, cond=True, user=user)
        else:
            return render_template("bookpage.html", book=book, avg_rating=avg_rating, ratings_ct=ratings_ct,
                                   loggedin=loggedin, reviews=reviews, cond=True, user=user)
