import os

from app import create_app
from config import ProductionConfig


app = create_app(ProductionConfig) if os.environ.get("APP_ENV") == "production" else create_app()


if __name__ == "__main__":
    app.run(debug=True)
