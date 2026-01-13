import psycopg2
import os
import time
from minio import Minio
from minio.error import S3Error
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_USER = os.getenv("MINIO_USER")
MINIO_PASSWORD = os.getenv("MINIO_PASSWORD")


def init_database():
    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        try:
            logger.info(f"Intentando conectar a PostgreSQL en {DB_HOST}:{DB_PORT}...")
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
            )

            cur = conn.cursor()

            with open("init.sql", "r") as f:
                sql = f.read()
                cur.execute(sql)

            conn.commit()
            cur.close()
            conn.close()

            logger.info("Base de datos inicializada correctamente")
            return

        except Exception as e:
            retry_count += 1
            logger.error(
                f"Error al conectar (intento {retry_count}/{max_retries}): {e}"
            )
            time.sleep(2)

    logger.error("No se pudo conectar a la base de datos")
    exit(1)


def init_minio():
    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        try:
            logger.info(f"Intentando conectar a MinIO en {MINIO_ENDPOINT}...")
            client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_USER,
                secret_key=MINIO_PASSWORD,
                secure=False,
            )

            bucket_name = "user-images"
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                logger.info(f"Bucket '{bucket_name}' creado")

                # Hacer el bucket público para lectura
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": "*"},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
                        }
                    ],
                }
                import json

                client.set_bucket_policy(bucket_name, json.dumps(policy))
                logger.info(f"Bucket '{bucket_name}' configurado como público")
            else:
                logger.info(f"Bucket '{bucket_name}' ya existe")

            return

        except Exception as e:
            retry_count += 1
            logger.error(
                f"Error al conectar a MinIO (intento {retry_count}/{max_retries}): {e}"
            )
            time.sleep(2)

    logger.error("No se pudo conectar a MinIO")
    exit(1)


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Inicializando aplicación...")
    logger.info("=" * 50)

    init_database()
    init_minio()

    logger.info("Inicialización completada")
