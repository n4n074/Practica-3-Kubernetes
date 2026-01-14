# Práctica 3 - Aplicación Flask en Kubernetes

Aplicación web Flask desplegada en Kubernetes (k3d) con dos entornos (DEV y PRO), monitoreo con Prometheus/Grafana, y pipeline CI/CD automatizado.

---
## Autor

Joan - [GitHub](https://github.com/n4n074)



## Guía para hacer el setup y probar el proyecto

### Prerequisitos

Instala las siguientes herramientas:

- **Docker** (>= 20.10)
- **k3d** (>= 5.0)
- **kubectl** (>= 1.24)
- **Helm** (>= 3.0)
- **make**

**Instalación en Linux:**

```bash
# k3d
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/kubectl

# Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

---

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/n4n074/Practica-3-Kubernetes.git
cd Practica-3-Kubernetes
```

---

### Paso 2: Levantar todo el cluster

```bash
make up
```

Este comando ejecuta:
1. Crea cluster k3d (1 server + 2 agents)
2. Construye la imagen Docker de Flask
3. Importa la imagen al cluster
4. Crea los namespaces (dev, pro)
5. Despliega DEV (2 réplicas) y PRO (4 réplicas)
6. Instala Prometheus y Grafana



---

### Paso 3: Verificar que todo está corriendo

```bash
kubectl get pods -n dev
kubectl get pods -n pro
kubectl get pods -n monitoring
```

Todos los pods deben estar en estado `Running`.

---

### Paso 4: Acceder a las aplicaciones


 App DEV  http://app.dev.localhost:8080 
 App PRO  http://app.pro.localhost:8080 
 Grafana  http://grafana.monitoring.localhost:8080 
 Prometheus  http://prometheus.monitoring.localhost:8080 
 MinIO DEV  http://minio-api.dev.localhost:8080 
 MinIO PRO  http://minio-api.pro.localhost:8080 

---

### Paso 5: Probar la aplicación

1. Abre http://app.dev.localhost:8080
2. Clic en "Ver Usuarios"
3. Crea un nuevo usuario (puedes subir una imagen de perfil)
4. Verifica que aparece en la lista
5. Las imágenes se guardan en MinIO
6. Los datos en PostgreSQL
7. En PRO, las consultas se cachean en Redis

---

### Paso 6: Verificar el monitoreo

**Grafana:**
1. Accede a http://grafana.monitoring.localhost:8080
2. Login: `admin` / `admin123`
3. Ve a Dashboards → "Flask Application Monitor"
4. Verás métricas en tiempo real de requests, latencia, errores, etc.

**Prometheus:**
1. Accede a http://prometheus.monitoring.localhost:8080
2. Ve a Status → Targets (verás `flask-app-dev` y `flask-app-pro`)
3. Ve a Alerts (verás 4 alertas configuradas)

---

## Partes del proyecto y diagrama de arquitectura

### Diagrama del cluster

```
┌────────────────────────────────────────────────────────────────┐
│                    K3D CLUSTER: practica3                      │
│              (1 server + 2 agents + load balancer)             │
│                   Port: localhost:8080 → 80                    │
└────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
      ┌───────▼──────┐  ┌────▼─────┐  ┌─────▼────────┐
      │ Namespace:   │  │Namespace:│  │ Namespace:   │
      │     dev      │  │   pro    │  │ monitoring   │
      │ (2 réplicas) │  │(4 réplic)│  │              │
      └──────────────┘  └──────────┘  └──────────────┘
```

### Namespace: DEV

```
┌─────────────────────────────────────────────────────────────┐
│  Ingress: app.dev.localhost:8080                            │
│  Ingress: minio-api.dev.localhost:8080                      │
└────────────────────────┬────────────────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
┌───▼───────┐    ┌──────▼──────┐    ┌───────▼─────┐
│ Flask App │    │ PostgreSQL  │    │    MinIO    │
│ 2 replicas│    │ StatefulSet │    │ Deployment  │
│ Deployment│    │ PVC: 2Gi    │    │ PVC: 5Gi    │
└───────────┘    └─────────────┘    └─────────────┘
```

### Namespace: PRO

```
┌─────────────────────────────────────────────────────────────┐
│  Ingress: app.pro.localhost:8080                            │
│  Ingress: minio-api.pro.localhost:8080                      │
└────────────────────────┬────────────────────────────────────┘
                         │
    ┌────────────────────┼────────────────┬────────────┐
    │                    │                │            │
┌───▼───────┐    ┌──────▼──────┐    ┌───▼──────┐  ┌─▼─────┐
│ Flask App │    │ PostgreSQL  │    │  Redis   │  │ MinIO │
│ 4 réplicas│    │ StatefulSet │    │Deployment│  │Deploy │
│ Deployment│    │ PVC: 2Gi    │    │ (cache)  │  │PVC:5Gi│
└───────────┘    └─────────────┘    └──────────┘  └───────┘
```

### Namespace: MONITORING

```
┌─────────────────────────────────────────────────────────────┐
│  Ingress: grafana.monitoring.localhost:8080                 │
│  Ingress: prometheus.monitoring.localhost:8080              │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
        ┌─────▼────┐  ┌──▼────────┐ ┌────────────┐
        │ Grafana  │  │Prometheus │ │  Operator  │
        │Dashboard │  │  Server   │ │            │
        │ Viewer   │  │  Scraper  │ │  Watches   │
        └──────────┘  │  Alerting │ │   CRDs     │
                      │ PVC: 5Gi  │ └────────────┘
                      └───────────┘
```

---

### Componentes principales

#### **1. Aplicación Flask** (`app/`)
- API REST para gestión de usuarios
- Endpoints: `/`, `/health`, `/users`, `/metrics`
- Health checks con livenessProbe y readinessProbe
- Métricas para Prometheus (requests, latencia, errores)

#### **2. PostgreSQL**
- Base de datos relacional
- StatefulSet con PersistentVolume (datos no se pierden)
- Almacena usuarios y metadatos

#### **3. MinIO**
- Almacenamiento de objetos compatible con S3
- Guarda las imágenes de perfil de usuarios
- Buckets: `dev-bucket`, `pro-bucket`

#### **4. Redis** (solo PRO)
- Sistema de caché en memoria
- Cachea consultas de usuarios
- Mejora el rendimiento en producción

#### **5. Prometheus**
- Scraping de métricas cada 30 segundos
- Almacena series temporales (15 días de retención)
- Evalúa 4 alertas personalizadas

#### **6. Grafana**
- Dashboard personalizado "Flask Application Monitor"
- Visualización de requests/s, latencia, errores, pods activos
- Usuario: `admin`, contraseña: `admin123`

#### **7. CI/CD Pipeline** (GitHub Actions)
- **Lint:** Black + Flake8
- **Test:** 32 tests unitarios con mocks 
- **Build:** Docker build y push a Docker Hub
- **Deploy:** Instrucciones de despliegue

---

## Tests utilizados y sus outputs

### Tipos de tests

El proyecto incluye **32 tests unitarios** organizados en 3 archivos:

#### **1. test_health.py** (12 tests)
Valida los health checks de los servicios:
- Conexión a PostgreSQL
- Conexión a Redis (PRO)
- Conexión a MinIO
- Funcionamiento del load balancer
- Estados de los endpoints `/health`

#### **2. test_database.py** (11 tests)
Valida operaciones de base de datos:
- Conexión a PostgreSQL
- Creación de usuarios
- Obtención de lista de usuarios
- Eliminación de usuarios
- Manejo de errores de conexión

#### **3. test_redis.py** (9 tests)
Valida operaciones de caché:
- Operaciones GET/SET en Redis
- Invalidación de caché
- Comportamiento sin Redis (DEV)
- Manejo de errores de conexión

---

### Técnica de testing: Mocks

Los tests usan **unittest.mock.patch** para simular servicios externos sin necesidad de tenerlos corriendo:

**Ventaja:** los tests corren sin PostgreSQL, Redis ni MinIO reales.

---

### Tests en CI/CD

Los tests también se ejecutan automáticamente en **GitHub Actions** en cada push:

```
Workflow: CI/CD Pipeline
  ↓
Job 1: Lint (Black + Flake8) ✓
  ↓
Job 2: Test (pytest) ✓
  → 32 tests passed
   ↓
Job 3: Build (Docker) ✓
  ↓
Job 4: Deploy (instructions) ✓
```

---

## 🛠️ Uso del Makefile

El Makefile incluye **17 comandos** para gestionar el cluster.

---

### Comandos principales

#### **Levantar todo desde cero**

```bash
make up
```

- Crea cluster k3d
- Construye imagen Docker
- Despliega DEV, PRO y monitoring
- **Tiempo:** 3-5 minutos

#### **Eliminar todo**

```bash
make down
```

- Borra el cluster completo
- Se pierden todos los datos

---

### Control de entornos

#### **DEV**

```bash
make stop-dev      # Apaga DEV (escala a 0 réplicas)
make start-dev     # Enciende DEV (2 réplicas)
```

#### **PRO**

```bash
make stop-pro      # Apaga PRO (escala a 0 réplicas)
make start-pro     # Enciende PRO (4 réplicas)
```

---

### Control de servicios específicos (PRO)

```bash
make stop-db-pro       # Apaga solo PostgreSQL de PRO
make start-db-pro      # Enciende PostgreSQL de PRO

make stop-cache-pro    # Apaga Redis de PRO
make start-cache-pro   # Enciende Redis de PRO
```

**Ejemplo de uso:** Simular caída de base de datos

```bash
make stop-db-pro
# La app sigue corriendo pero devolverá errores en /health
```

---

### Comandos de actualización (sin reiniciar cluster)

#### **Actualizar código de la aplicación**

```bash
make update-image
```

- Reconstruye la imagen Docker
- Importa al cluster
- **NO reinicia pods** (solo actualiza la imagen disponible)

```bash
make restart-dev       # Reinicia pods de DEV con nueva imagen
make restart-pro       # Reinicia pods de PRO con nueva imagen
```

**Flujo completo:**

```bash
# 1. Modificas app/app.py
# 2. Reconstruyes la imagen
make update-image
# 3. Reinicias los pods
make restart-dev
make restart-pro
```

**Ventaja:** No pierdes datos 

---

#### **Actualizar configuración (Secrets, ConfigMaps, Ingress)**

```bash
make update-dev        # Aplica cambios en k8s/dev/
make update-pro        # Aplica cambios en k8s/pro/
```

**Ejemplo:**

```bash
# Modificas k8s/dev/secrets.yaml
make update-dev
# Kubernetes aplica el nuevo Secret automáticamente
```

---

#### **Actualizar monitoreo**

```bash
make update-monitoring
```

- Actualiza Prometheus/Grafana con nuevos valores de `k8s/helm/values.yaml`
- Útil cuando cambias alertas, dashboards o scraping configs

---

### Ejemplos de casos de uso

#### **Caso 1: Cambié código Python**

```bash
make update-image      # Rebuild + import
make restart-dev       # Reinicia DEV
make restart-pro       # Reinicia PRO
```

**Tiempo:** 30-60 segundos
**Downtime:** Rolling update (0 downtime)

---

#### **Caso 2: Cambié contraseña de PostgreSQL**

```bash
# Editar k8s/dev/secrets.yaml
make update-dev
# Kubernetes actualiza el Secret automáticamente
# Los pods nuevos usarán la nueva contraseña
```

---

#### **Caso 3: Cambié número de réplicas en PRO**

```bash
# Editar k8s/pro/app-replicas-patch.yaml: replicas: 6
make update-pro
# Kubernetes escala automáticamente a 6 réplicas
```

---

#### **Caso 4: Cambié una alerta de Prometheus**

```bash
# Editar k8s/helm/values.yaml
make update-monitoring
# Helm actualiza la configuración
# Prometheus recarga las alertas automáticamente
```

---

#### **Caso 5: Solo quiero trabajar en DEV**

```bash
make stop-pro          # Apaga PRO (ahorra recursos)
# Trabajas en DEV...
make start-pro         # Vuelves a levantar PRO cuando necesites
```

---



## Estructura del proyecto

```
.
├── Makefile # Automatización de comandos
├── README.md # Este archivo
├── .github/
│   └── workflows/
│       └── ci-cd.yml # Pipeline CI/CD (lint, test, build)
├── app/ # Aplicación Flask
│   ├── app.py # Código principal
│   ├── Dockerfile # Imagen Docker
│   ├── requirements.txt # Dependencias
│   ├── templates/ # HTML
│   ├── static/ # CSS, JS
│   └── tests/ # Tests unitarios
│       ├── test_health.py
│       ├── test_database.py
│       └── test_redis.py
└── k8s/ # Manifiestos Kubernetes
    ├── namespaces/ # Definición de namespaces
    ├── base-dev/ # Plantillas base DEV
    │   ├── app-deployment.yaml
    │   ├── postgres-statefulset.yaml
    │   └── minio-deployment.yaml
    ├── base-pro/ # Plantillas base PRO (con Redis)
    ├── dev/ # Overlays DEV (personalización)
    │   ├── kustomization.yaml
    │   ├── secrets.yaml
    │   ├── configmap.yaml
    │   └── ingress.yaml
    ├── pro/ # Overlays PRO (personalización)
    │   ├── kustomization.yaml
    │   ├── secrets.yaml
    │   ├── configmap.yaml
    │   └── ingress.yaml
    └── helm/ # Configuración monitoring
        └── values.yaml # Prometheus/Grafana
```

---




## Métricas y Monitoreo

### Prometheus Targets

Prometheus scrapea métricas de:
- `flask-app-dev` (web-app.dev.svc.cluster.local:80/metrics)
- `flask-app-pro` (web-app.pro.svc.cluster.local:80/metrics)

### Alertas configuradas

1. **FlaskAppPodsNotReady:** Al menos un entorno sin pods activos
2. **FlaskAppHighCPU:** CPU > 80% durante 5 minutos
3. **FlaskAppHighMemory:** Memoria > 90% durante 5 minutos
4. **FlaskAppHighErrorRate:** Errores 5xx > 5% durante 5 minutos

### Dashboard Grafana

Paneles incluidos:
- Requests por segundo (por entorno)
- Latencia promedio
- Distribución de códigos HTTP
- Pods activos
- Tasa de errores 5xx
- Tabla de requests por ruta

---

## 🔗 URLs de acceso


 App DEV  http://app.dev.localhost:8080 
 App PRO  http://app.pro.localhost:8080 
 Grafana  http://grafana.monitoring.localhost:8080 
 Prometheus  http://prometheus.monitoring.localhost:8080 
 MinIO Console DEV  http://minio.dev.localhost:8080
 MinIO API DEV  http://minio-api.dev.localhost:8080 
 MinIO Console PRO  http://minio.pro.localhost:8080 
 MinIO API PRO  http://minio-api.pro.localhost:8080 

---



