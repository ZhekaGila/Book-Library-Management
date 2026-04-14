import os
import time
from flask import Flask, request, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.exc import OperationalError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

app.config['SECRET_KEY'] = 'supersecret'
app.config["TEMPLATES_AUTO_RELOAD"] = True

database_url = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@db:5432/library_db"
)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
Migrate(app, db)

# ---- Prometheus metrics ----
REQUEST_COUNT = Counter(
    'flask_requests_total',
    'Total Flask HTTP Requests',
    ['method', 'endpoint', 'http_status']
)

ERROR_COUNT = Counter(
    'flask_errors_total',
    'Total Flask HTTP Errors',
    ['method', 'endpoint']
)

REQUEST_LATENCY = Histogram(
    'flask_request_latency_seconds',
    'Flask Request Latency',
    ['method', 'endpoint']
)

@app.before_request
def start_timer():
    request.start_time = time.time()

@app.after_request
def record_metrics(response):
    if request.path != '/metrics':
        resp_time = time.time() - request.start_time
        REQUEST_LATENCY.labels(request.method, request.path).observe(resp_time)
        REQUEST_COUNT.labels(request.method, request.path, response.status_code).inc()

        if response.status_code >= 400:
            ERROR_COUNT.labels(request.method, request.path).inc()

    return response

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

# ---- Wait for DB ----
for i in range(10):
    try:
        with app.app_context():
            db.engine.connect()
        print("Connected to DB")
        break
    except OperationalError:
        print("Waiting for DB...")
        time.sleep(2)

from project.core.views import core
from project.books.views import books
from project.customers.views import customers
from project.loans.views import loans

app.register_blueprint(core)
app.register_blueprint(books)
app.register_blueprint(customers)
app.register_blueprint(loans)