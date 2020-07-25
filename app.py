import os
import requests

from flask import Flask, session, render_template, request, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

api_key = "gEkkIjvVdWiasAdxviNcA"
'''
# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")
'''
# Configure session to use filesystem
app.secret_key=os.urandom(24)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine("postgres://qodplerxaoqxhp:fbcecf33adb201172c3047eb309ac9e8ed5c3fbd5ad897b0eb5d3eeeb0b89624@ec2-52-71-85-210.compute-1.amazonaws.com:5432/dcbavq33jd0qt3")
db = scoped_session(sessionmaker(bind=engine))


@app.route("/", methods=["POST","GET"])
def index():
    if "USERNAME" in session:
        user = session["USERNAME"]
        return render_template("home.html",user=user)
    else:
        return redirect("/login")
@app.route("/login", methods=["POST","GET"])
def login():
    session.clear()
    if request.method=="POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "" or password == "":
            error = "Enter username or password"
            return render_template("login.html", error=error)
        user = db.execute("SELECT * FROM users WHERE username=:username and password=:password",
                          {"username": username, "password": password}).fetchone()
        if user is None:
            error = "Invalid username or password"
            return render_template("login.html", error=error)
        session["USERNAME"] = user.username
        session["USER_ID"] = user.user_id
        return redirect("/")
    else:
        return render_template("login.html")

@app.route("/register", methods=["POST","GET"])
def register():
    if request.method=="GET":
        return render_template("register.html")
    else:
        session.clear()
        username = request.form.get("username")
        password = request.form.get("password")
        cpassword = request.form.get("confirmpassword")
        error=""
        if password!=cpassword:
            error="Enter both password same"
            return render_template("register.html",error=error)
        if username=="" or password=="":
            error="Username and password should have atleast one character"
            return render_template("register.html",error=error)
        check = db.execute("SELECT * FROM users WHERE username = :username", \
                           {"username": username}).fetchone()
        if check is not None:
            error="Username already exist try another"
            return render_template("register.html",error=error)
        db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {"username": username, "password": password})
        db.commit()
        return redirect("/login")

@app.route("/logout",methods=["GET"])
def logout():
    session.clear()
    return redirect("/login")

@app.route("/home", methods=["POST","GET"])
def home():
    if "USERNAME" not in session:
        return redirect("/login")
    if request.method=="GET":
        return redirect("/")
    user = session["USERNAME"]
    search= request.form.get("search")
    if search=="":
        error="Enter something"
    data = db.execute("SELECT * FROM books where title ILIKE :title or isbn ILIKE :isbn or author ILIKE :author",
                        {"title":f"%{search}%","isbn":f"%{search}%","author":f"%{search}%"})
    if data.rowcount==0:
        return render_template("home.html",message="No book match",rows=data.rowcount)
    return render_template("search.html",rows=data.rowcount,books=data)

@app.route("/book/<string:isbn>", methods=["POST","GET"])
def book(isbn):
    if "USERNAME" not in session:
        return redirect("/login")
    if request.method=="POST":
        review=request.form.get("review")
        rating=request.form.get("rating")
        if review is None or rating is None:
            return redirect("/book/"+str(isbn))
        user_id=session["USER_ID"]
        db.execute("INSERT INTO ratings (user_id, isbn, review, rating, username) VALUES (:user_id, :isbn, :review, :rating, :username)",
                   {"user_id":user_id,"isbn":isbn,"review":review,"rating":rating,"username":session["USERNAME"]})
        db.commit()
        return redirect("/book/"+str(isbn))
    else:
        book = db.execute("SELECT * FROM books WHERE isbn=:isbn",{"isbn":isbn}).fetchone()


        reviews= db.execute("SELECT * FROM ratings WHERE isbn=:isbn",{"isbn":isbn}).fetchall()
        user_id = session["USER_ID"]
        avg = 0
        user = True

        for review in reviews:
            avg += review.rating
            if session["USER_ID"]==review.user_id:
                user=False

        count = len(reviews)

        if count != 0:
            avg /= count

        res = requests.get("https://www.goodreads.com/book/review_counts.json",
                                     params={"key":"gEkkIjvVdWiasAdxviNcA","isbns":isbn})
        goodread_data = res.json()
        #print(res.text)
        review_count = goodread_data["books"][0]["work_ratings_count"]
        average_rating = goodread_data["books"][0]["average_rating"]
        return render_template("book.html", user=user, review_count=review_count,average_rating=average_rating,reviews=reviews,book=book,avg=avg)

@app.route("/api/<isbn>", methods=["GET"])
def api(isbn):
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn",
                      {"isbn": isbn}).fetchone()
    # make sure the isbn is in the database (required 404 fuckup)
    if book is None:
        return jsonify({"error": "Invalid ISBN number"}), 404

    book = db.execute("SELECT * FROM books WHERE isbn = :isbn",
                      {"isbn": isbn}).fetchone()
    ratingl = db.execute("SELECT AVG(rating) FROM ratings WHERE isbn = :isbn", \
                        {"isbn": isbn}).scalar()
    review_countl = db.execute("SELECT COUNT(*) FROM ratings WHERE isbn = :isbn", \
                              {"isbn": isbn}).scalar()
    #title, author, year, isbn = (book.title, book.author, book.year, book.isbn)
    if ratingl is None:
        ratingl=0
    if review_countl is None:
        review_countl="no reviews yet"
    return jsonify({
        "title":book.title,
        "author":book.author,
        "year":book.year,
        "isbn":book.isbn,
        "review_count":review_countl,
        "average_score":float('%.2f'%(ratingl))
    })