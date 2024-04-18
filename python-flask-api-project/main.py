from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/hello', methods=['GET'])
def helloworld():
    data = {"data": "Hello World"}
    return jsonify(data)  # Directly return a jsonify response
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9001)
