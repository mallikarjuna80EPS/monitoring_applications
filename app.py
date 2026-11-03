from flask import Flask, render_template

app = Flask(__name__)

PLACEHOLDER_SERVER = {
    "name": "Local host",
    "hostname": "127.0.0.1",
}


@app.get("/")
def sign_in():
    return render_template("sign_in.html")


@app.get("/servers")
def servers():
    return render_template("servers.html", server=PLACEHOLDER_SERVER)


@app.get("/metrics")
def metrics():
    return render_template("metrics.html", server=PLACEHOLDER_SERVER)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
