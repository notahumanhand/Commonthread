import os

from flask import Flask, render_template

app = Flask(__name__)


@app.get("/")
def index():
    # The index page is the navigation/landing page, not the Home page.
    return render_template("index.html")


@app.get("/about")
def about():
    return render_template("about.html")


@app.get("/home")
def home():
    return render_template("home.html")


@app.get("/data")
def data():
    return render_template("data.html")


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
