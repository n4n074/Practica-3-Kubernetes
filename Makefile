.PHONY: up down stop-db-pro start-db-pro stop-cache-pro start-cache-pro stop-dev stop-pro start-dev start-pro \
        update-image update-dev update-pro update-monitoring restart-dev restart-pro 

up:
	@echo "Creando cluster k3d..."
	k3d cluster create practica3 --servers 1 --agents 2 --port "8080:80@loadbalancer"
	
	@echo "Construyendo imagen Docker..."
	docker build -t flask-app:latest ./app
	
	@echo "Importando imagen al cluster..."
	k3d image import flask-app:latest -c practica3
	
	@echo "Creando namespaces..."
	kubectl apply -f k8s/namespaces/namespaces.yaml
	
	@echo "Desplegando entorno DEV..."
	kubectl apply -k k8s/dev/
	
	@echo "Desplegando entorno PRO..."
	kubectl apply -k k8s/pro/
	
	@echo "Instalando stack de monitoreo..."
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true
	helm repo update
	helm install monitoring prometheus-community/kube-prometheus-stack \
		--namespace monitoring --create-namespace \
		-f k8s/helm/values.yaml
	
	@echo "Despliegue completado."
	@echo ""
	@echo "URLs disponibles:"
	@echo "  - App DEV:    http://app.dev.localhost:8080"
	@echo "  - App PRO:    http://app.pro.localhost:8080"
	@echo "  - Grafana:    http://grafana.monitoring.localhost:8080 (admin/admin123)"
	@echo "  - Prometheus: http://prometheus.monitoring.localhost:8080"

down:
	@echo "Eliminando cluster k3d..."
	k3d cluster delete practica3
	@echo "Cluster eliminado."

stop-db-pro:
	@echo "Deteniendo base de datos de PRO..."
	kubectl scale statefulset postgres -n pro --replicas=0
	@echo "Base de datos de PRO detenida."

start-db-pro:
	@echo "Levantando base de datos de PRO..."
	kubectl scale statefulset postgres -n pro --replicas=1
	@echo "Base de datos de PRO levantada."

stop-cache-pro:
	@echo "Deteniendo Redis de PRO..."
	kubectl scale deployment redis -n pro --replicas=0
	@echo "Redis de PRO detenido."

start-cache-pro:
	@echo "Levantando Redis de PRO..."
	kubectl scale deployment redis -n pro --replicas=1
	@echo "Redis de PRO levantado."

stop-dev:
	@echo "Deteniendo entorno DEV..."
	kubectl scale deployment web-app -n dev --replicas=0
	kubectl scale statefulset postgres -n dev --replicas=0
	kubectl scale deployment minio -n dev --replicas=0
	@echo "Entorno DEV detenido."

stop-pro:
	@echo "Deteniendo entorno PRO..."
	kubectl scale deployment web-app -n pro --replicas=0
	kubectl scale statefulset postgres -n pro --replicas=0
	kubectl scale deployment redis -n pro --replicas=0
	kubectl scale deployment minio -n pro --replicas=0
	@echo "Entorno PRO detenido."

start-dev:
	@echo "Levantando entorno DEV..."
	kubectl scale deployment web-app -n dev --replicas=2
	kubectl scale statefulset postgres -n dev --replicas=1
	kubectl scale deployment minio -n dev --replicas=1
	@echo "Entorno DEV levantado."

start-pro:
	@echo "Levantando entorno PRO..."
	kubectl scale deployment web-app -n pro --replicas=4
	kubectl scale statefulset postgres -n pro --replicas=1
	kubectl scale deployment redis -n pro --replicas=1
	kubectl scale deployment minio -n pro --replicas=1
	@echo "Entorno PRO levantado."

# ==========================================
# Comandos de actualización (sin reiniciar cluster)
# ==========================================

update-image:
	@echo "Reconstruyendo imagen Docker..."
	docker build -t flask-app:latest ./app
	@echo "Importando imagen actualizada al cluster..."
	k3d image import flask-app:latest -c practica3
	@echo "Imagen actualizada. Usa 'make restart-dev' o 'make restart-pro' para aplicar cambios."

update-dev:
	@echo "Actualizando configuración de DEV..."
	kubectl apply -k k8s/dev/
	@echo "Configuración de DEV actualizada."

update-pro:
	@echo "Actualizando configuración de PRO..."
	kubectl apply -k k8s/pro/
	@echo "Configuración de PRO actualizada."

update-monitoring:
	@echo "Actualizando stack de monitoreo..."
	helm upgrade monitoring prometheus-community/kube-prometheus-stack \
		--namespace monitoring \
		-f k8s/helm/values.yaml
	@echo "Monitoreo actualizado."

restart-dev:
	@echo "Reiniciando pods de DEV..."
	kubectl rollout restart deployment web-app -n dev
	kubectl rollout restart deployment minio -n dev
	kubectl rollout restart statefulset postgres -n dev
	@echo "Pods de DEV reiniciados."

restart-pro:
	@echo "Reiniciando pods de PRO..."
	kubectl rollout restart deployment web-app -n pro
	kubectl rollout restart deployment minio -n pro
	kubectl rollout restart deployment redis -n pro
	kubectl rollout restart statefulset postgres -n pro
	@echo "Pods de PRO reiniciados."


