from app import create_app
from app.db import init_db

app = create_app()

if __name__ == "__main__":
    init_db(app)
    print("=" * 50)
    print(" SchoolPro | base de données:", app.config["DB_LABEL"])
    print("=" * 50)
    app.run(debug=True)
