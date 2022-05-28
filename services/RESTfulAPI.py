# aim: this is used to define the restful api for clients
# date: 2022-05-28
# author: zhangxunhui

from flask import Flask, request

app = Flask(__name__)


@app.route("/clone_detection", methods=["POST"])
def clone_detection():
    if "code" not in request.args:
        return "RESTful request error: code parameter not found!"
    else:
        code = request.args["code"]
        return code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
