from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from minio import Minio
import requests
import time
import socket
from werkzeug.utils import secure_filename
import uuid
import json
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max

metrics = PrometheusMetrics(app)
metrics.info("app_info", "Application info", version="1.0.0")

# Configuración desde variables de entorno
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", "0"))  # Default a 0 si no está configurado
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_USER = os.getenv("MINIO_USER")
MINIO_PASSWORD = os.getenv("MINIO_PASSWORD")
MINIO_PUBLIC_PORT = os.getenv("MINIO_PUBLIC_PORT")

LB_HOST = os.getenv("LB_HOST", "dev-load-balancer")
LB_PORT = int(os.getenv("LB_PORT", "80"))

INSTANCE_ID = socket.gethostname()
BUCKET_NAME = "user-images"
CACHE_TTL = 300
USERS_CACHE_KEY = "users_list"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def get_redis():
    if not REDIS_HOST or REDIS_PORT == 0:
        return None
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def get_minio():
    return Minio(
        MINIO_ENDPOINT, access_key=MINIO_USER, secret_key=MINIO_PASSWORD, secure=False
    )


def invalidate_users_cache():
    """Invalida la caché de usuarios"""
    try:
        r = get_redis()
        if r:
            r.delete(USERS_CACHE_KEY)
    except Exception:
        pass


def get_users_from_cache():
    """Obtiene usuarios desde caché Redis"""
    try:
        r = get_redis()
        if not r:
            return None, False
        cached_data = r.get(USERS_CACHE_KEY)
        if cached_data:
            return json.loads(cached_data), True  # True = desde caché
    except Exception:
        pass
    return None, False


def save_users_to_cache(users_list):
    """Guarda usuarios en caché Redis"""
    try:
        r = get_redis()
        if r:
            r.setex(USERS_CACHE_KEY, CACHE_TTL, json.dumps(users_list))
    except Exception:
        pass


def check_postgres():
    try:
        conn = get_db()
        conn.close()
        return True
    except Exception:
        return False


def check_redis():
    try:
        r = get_redis()
        if not r:
            return False
        r.ping()
        return True
    except Exception:
        return False


def check_minio():
    try:
        client = get_minio()
        client.list_buckets()
        return True
    except Exception:
        return False


def check_load_balancer():
    try:
        response = requests.get(f"http://{LB_HOST}:{LB_PORT}/health", timeout=3)
        return response.status_code == 200
    except Exception:
        return False


@app.route("/health")
def health():
    """
    Endpoint de health-check para Kubernetes livenessProbe.
    Solo verifica que la aplicación Flask esté respondiendo.
    No falla si las dependencias (BD, Redis, MinIO) están caídas.
    """
    health_status = {
        "status": "healthy",
        "instance_id": INSTANCE_ID,
        "message": "Application is running",
    }
    return jsonify(health_status), 200


@app.route("/health/ready")
def health_ready():
    """
    Endpoint para Kubernetes readinessProbe.
    Verifica que los servicios críticos estén disponibles.
    """
    health_status = {"status": "ready", "instance_id": INSTANCE_ID, "checks": {}}

    # Verificar PostgreSQL (crítico)
    postgres_ok = check_postgres()
    health_status["checks"]["postgres"] = "ok" if postgres_ok else "error"

    # Verificar MinIO (crítico)
    minio_ok = check_minio()
    health_status["checks"]["minio"] = "ok" if minio_ok else "error"

    # Verificar Redis (opcional - solo en pro)
    if REDIS_HOST and REDIS_PORT:
        redis_ok = check_redis()
        health_status["checks"]["redis"] = "ok" if redis_ok else "warning"
    else:
        health_status["checks"]["redis"] = "not_configured"

    # Si falla algo crítico, marcar como not ready
    if not postgres_ok or not minio_ok:
        health_status["status"] = "not_ready"
        return jsonify(health_status), 503

    return jsonify(health_status), 200


@app.route("/")
def index():
    redis_configured = REDIS_HOST and REDIS_PORT != 0
    return render_template(
        "index.html",
        db_status=check_postgres(),
        cache_status=check_redis() if redis_configured else None,
        redis_configured=redis_configured,
        minio_status=check_minio(),
        lb_status=check_load_balancer(),
        instance_id=INSTANCE_ID,
    )


@app.route("/users")
def users():
    from_cache = False
    query_time = 0

    try:
        start_time = time.time()

        # Intentar obtener desde caché
        users_list, from_cache = get_users_from_cache()

        if users_list is None:
            # Si no está en caché, consultar base de datos
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM users ORDER BY created_at DESC")
            users_list = cur.fetchall()
            cur.close()
            conn.close()

            # Convertir a lista de diccionarios normales para JSON
            users_list = [dict(user) for user in users_list]

            # Convertir datetime a string para poder serializar en JSON
            for user in users_list:
                if user.get("created_at"):
                    user["created_at"] = user["created_at"].isoformat()

            # Guardar en caché
            save_users_to_cache(users_list)

        query_time = round((time.time() - start_time) * 1000, 2)

        # Generar URL completa para cada imagen
        environment = os.getenv("ENVIRONMENT", "dev")
        minio_host = f"minio-api.{environment}.localhost:8080"

        for user in users_list:
            if user.get("image_url"):
                user["image_display_url"] = (
                    f"http://{minio_host}/{BUCKET_NAME}/{user['image_url']}"
                )
            else:
                user["image_display_url"] = None

        return render_template(
            "users.html",
            users=users_list,
            instance_id=INSTANCE_ID,
            from_cache=from_cache,
            query_time=query_time,
        )
    except Exception as e:
        return render_template(
            "users.html",
            users=[],
            error=str(e),
            instance_id=INSTANCE_ID,
            from_cache=False,
            query_time=0,
        )


@app.route("/users/add", methods=["POST"])
def add_user():
    name = request.form.get("name")
    email = request.form.get("email")
    image = request.files.get("image")

    print(
        f"[ADD_USER] Recibido: name={name}, email={email}, image={image.filename if image else 'None'}"
    )

    image_url = None

    try:
        # Subir imagen a MinIO si existe
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"

            print(f"[ADD_USER] Subiendo imagen {unique_filename} a MinIO...")
            client = get_minio()
            client.put_object(
                BUCKET_NAME,
                unique_filename,
                image,
                length=-1,
                part_size=10 * 1024 * 1024,
                content_type=image.content_type,
            )

            image_url = unique_filename
            print("[ADD_USER] Imagen subida correctamente")

        # Guardar en base de datos
        print(f"[ADD_USER] Guardando en BD: {name}, {email}, {image_url}")
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (name, email, image_url) VALUES (%s, %s, %s)",
            (name, email, image_url),
        )
        conn.commit()
        print("[ADD_USER] Usuario guardado correctamente")
        cur.close()
        conn.close()

        # Invalidar caché para que se recargue con el nuevo usuario
        invalidate_users_cache()

    except Exception as e:
        print(f"Error: {e}")

    return redirect(url_for("users"))


@app.route("/users/delete/<int:user_id>")
def delete_user(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Obtener la imagen antes de eliminar
        cur.execute("SELECT image_url FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()

        if user and user["image_url"]:
            # Eliminar imagen de MinIO
            client = get_minio()
            try:
                client.remove_object(BUCKET_NAME, user["image_url"])
            except Exception:
                pass

        # Eliminar usuario
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()

        # Invalidar caché
        invalidate_users_cache()

    except Exception as e:
        print(f"Error: {e}")

    return redirect(url_for("users"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
