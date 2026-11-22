from app import create_app

app = create_app()

if __name__ == '__main__':
    # Development only. Do not expose this server directly to the public internet.
    app.run(host='127.0.0.1', port=5000, debug=False)
