from flask import Flask
import baggage

app = Flask(__name__)
baggage.init_app(app)

@app.route("/")
def hello():
    return "tekton-dag-flask"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
