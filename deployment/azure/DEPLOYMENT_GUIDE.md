# 🚀 Guía de Despliegue en Microsoft Azure

Esta guía te llevará paso a paso para desplegar la **Retail API** en Microsoft Azure usando diferentes servicios.

## 📋 Índice

- [☁️ Opción 1: Azure Container Instances (Más Fácil)](#️-opción-1-azure-container-instances-más-fácil)
- [🏢 Opción 2: Azure App Service (Recomendado para Producción)](#-opción-2-azure-app-service-recomendado-para-producción)
- [🚀 Opción 3: Azure Kubernetes Service (Escalable)](#-opción-3-azure-kubernetes-service-escalable)
- [🗄️ Configuración de Base de Datos](#️-configuración-de-base-de-datos)
- [🔐 Configuración de Seguridad](#-configuración-de-seguridad)
- [📊 Monitoreo y Logging](#-monitoreo-y-logging)

---

## 📋 Prerrequisitos

### 🔧 Herramientas Necesarias

```bash
# 1. Azure CLI
# Instalar desde: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
az --version

# 2. Docker (para containerización)
docker --version

# 3. Git (para deployment desde repositorio)
git --version
```

### 🔑 Configuración Inicial

```bash
# Iniciar sesión en Azure
az login

# Verificar suscripciones disponibles
az account list --output table

# Seleccionar suscripción específica (si tienes varias)
az account set --subscription "Your-Subscription-ID"

# Crear grupo de recursos
az group create --name retail-api-rg --location "East US"
```

---

## ☁️ Opción 1: Azure Container Instances (Más Fácil)

### 🎯 **Ideal para**: Desarrollo, testing, aplicaciones pequeñas

### 📦 Paso 1: Preparar el Contenedor

```bash
# 1. Crear Azure Container Registry
az acr create \
  --resource-group retail-api-rg \
  --name retailapiregistry \
  --sku Basic \
  --admin-enabled true

# 2. Obtener credenciales del registry
az acr credential show --name retailapiregistry

# 3. Hacer login al registry
az acr login --name retailapiregistry

# 4. Construir y pushear la imagen
docker build -t retailapiregistry.azurecr.io/retail-api:latest .
docker push retailapiregistry.azurecr.io/retail-api:latest
```

### 🗄️ Paso 2: Crear Base de Datos PostgreSQL

```bash
# Crear servidor PostgreSQL
az postgres flexible-server create \
  --resource-group retail-api-rg \
  --name retail-api-postgres \
  --admin-user retailadmin \
  --admin-password "SecurePassword123!" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 15 \
  --location "East US" \
  --public-access 0.0.0.0

# Crear base de datos
az postgres flexible-server db create \
  --resource-group retail-api-rg \
  --server-name retail-api-postgres \
  --database-name retail_api_db
```

### 🚀 Paso 3: Desplegar Container Instance

```bash
# Crear container instance con variables de entorno
az container create \
  --resource-group retail-api-rg \
  --name retail-api-container \
  --image retailapiregistry.azurecr.io/retail-api:latest \
  --registry-login-server retailapiregistry.azurecr.io \
  --registry-username retailapiregistry \
  --registry-password $(az acr credential show --name retailapiregistry --query passwords[0].value -o tsv) \
  --dns-name-label retail-api-demo \
  --ports 8000 \
  --environment-variables \
    DEBUG=False \
    DB_NAME=retail_api_db \
    DB_USER=retailadmin \
    DB_PASSWORD="SecurePassword123!" \
    DB_HOST=retail-api-postgres.postgres.database.azure.com \
    DB_PORT=5432 \
    ALLOWED_HOSTS="retail-api-demo.eastus.azurecontainer.io" \
  --cpu 1 \
  --memory 1.5

# Verificar el estado
az container show \
  --resource-group retail-api-rg \
  --name retail-api-container \
  --query "{FQDN:ipAddress.fqdn,ProvisioningState:provisioningState}" \
  --out table
```

### 🌐 Acceso a la Aplicación

```bash
# Tu API estará disponible en:
echo "https://retail-api-demo.eastus.azurecontainer.io:8000/api/"
```

---

## 🏢 Opción 2: Azure App Service (Recomendado para Producción)

### 🎯 **Ideal para**: Aplicaciones de producción, auto-scaling, integración CI/CD

### 📋 Paso 1: Configurar Variables de Entorno

Crear archivo `deployment/azure/.env.production`:

```bash
# Azure App Service Environment Variables
DEBUG=False
SECRET_KEY=your-super-secret-production-key-here
ALLOWED_HOSTS=retail-api-webapp.azurewebsites.net,your-custom-domain.com

# Database Configuration
DB_NAME=retail_api_db
DB_USER=retailadmin@retail-api-postgres
DB_PASSWORD=SecurePassword123!
DB_HOST=retail-api-postgres.postgres.database.azure.com
DB_PORT=5432

# Azure Specific
AZURE_STORAGE_ACCOUNT_NAME=retailapistorage
AZURE_STORAGE_ACCOUNT_KEY=your-storage-key

# Security
SECURE_SSL_REDIRECT=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True
```

### 🗄️ Paso 2: Crear Base de Datos (si no existe)

```bash
# Crear PostgreSQL (si no se hizo antes)
az postgres flexible-server create \
  --resource-group retail-api-rg \
  --name retail-api-postgres \
  --admin-user retailadmin \
  --admin-password "SecurePassword123!" \
  --sku-name Standard_D2s_v3 \
  --tier GeneralPurpose \
  --storage-size 128 \
  --version 15 \
  --location "East US" \
  --public-access 0.0.0.0

# Configurar firewall para App Service
az postgres flexible-server firewall-rule create \
  --resource-group retail-api-rg \
  --name retail-api-postgres \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

### 🚀 Paso 3: Crear App Service

```bash
# 1. Crear App Service Plan
az appservice plan create \
  --resource-group retail-api-rg \
  --name retail-api-plan \
  --sku B2 \
  --is-linux

# 2. Crear Web App con Python
az webapp create \
  --resource-group retail-api-rg \
  --plan retail-api-plan \
  --name retail-api-webapp \
  --runtime "PYTHON|3.11" \
  --deployment-source-url https://github.com/UrielMartinez21/retail-api.git \
  --deployment-source-branch main

# 3. Configurar variables de entorno
az webapp config appsettings set \
  --resource-group retail-api-rg \
  --name retail-api-webapp \
  --settings \
    DEBUG=False \
    SECRET_KEY="your-super-secret-production-key" \
    DB_NAME=retail_api_db \
    DB_USER=retailadmin \
    DB_PASSWORD="SecurePassword123!" \
    DB_HOST=retail-api-postgres.postgres.database.azure.com \
    DB_PORT=5432 \
    ALLOWED_HOSTS="retail-api-webapp.azurewebsites.net"

# 4. Configurar startup command
az webapp config set \
  --resource-group retail-api-rg \
  --name retail-api-webapp \
  --startup-file "startup.sh"
```

### 📦 Paso 4: Configurar Deployment

Crear `deployment/azure/startup.sh`:

```bash
#!/bin/bash
# Azure App Service startup script

echo "Starting Retail API deployment..."

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Create superuser (optional, for first deployment)
# python manage.py shell -c "
# from django.contrib.auth import get_user_model;
# User = get_user_model();
# User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')"

# Start Gunicorn
gunicorn retail_api.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --worker-class gevent \
    --worker-connections 1000 \
    --timeout 30 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --preload
```

### 🔧 Paso 5: Configurar CI/CD (Opcional)

```bash
# Habilitar deployment continuo desde GitHub
az webapp deployment source config \
  --resource-group retail-api-rg \
  --name retail-api-webapp \
  --repo-url https://github.com/UrielMartinez21/retail-api.git \
  --branch main \
  --manual-integration

# Configurar webhook para auto-deployment
az webapp deployment source sync \
  --resource-group retail-api-rg \
  --name retail-api-webapp
```

---

## 🚀 Opción 3: Azure Kubernetes Service (Escalable)

### 🎯 **Ideal para**: Aplicaciones de alta escala, microservicios, múltiples entornos

### 🔧 Paso 1: Crear AKS Cluster

```bash
# Crear service principal (si es necesario)
az ad sp create-for-rbac --name retail-api-sp --skip-assignment

# Crear AKS cluster
az aks create \
  --resource-group retail-api-rg \
  --name retail-api-aks \
  --node-count 3 \
  --node-vm-size Standard_D2s_v3 \
  --enable-addons monitoring \
  --generate-ssh-keys

# Obtener credenciales
az aks get-credentials \
  --resource-group retail-api-rg \
  --name retail-api-aks
```

### 📦 Paso 2: Configurar Manifiestos de Kubernetes

Ver archivos en `deployment/azure/k8s/` (se crearán a continuación).

### 🗄️ Paso 3: Desplegar en Kubernetes

```bash
# Aplicar configuraciones
kubectl apply -f deployment/azure/k8s/

# Verificar deployments
kubectl get pods
kubectl get services

# Obtener IP externa
kubectl get service retail-api-service
```

---

## 🗄️ Configuración de Base de Datos

### 🔧 Configuración de Producción PostgreSQL

```bash
# Crear PostgreSQL optimizado para producción
az postgres flexible-server create \
  --resource-group retail-api-rg \
  --name retail-api-postgres-prod \
  --admin-user retailadmin \
  --admin-password "VerySecurePassword2025!" \
  --sku-name Standard_D4s_v3 \
  --tier GeneralPurpose \
  --storage-size 512 \
  --storage-auto-grow Enabled \
  --version 15 \
  --location "East US" \
  --high-availability ZoneRedundant \
  --backup-retention 30

# Configurar parámetros de rendimiento
az postgres flexible-server parameter set \
  --resource-group retail-api-rg \
  --server-name retail-api-postgres-prod \
  --name max_connections \
  --value 200

az postgres flexible-server parameter set \
  --resource-group retail-api-rg \
  --server-name retail-api-postgres-prod \
  --name shared_buffers \
  --value "256MB"
```

### 💾 Configuración de Backups Automáticos

```bash
# Los backups están habilitados por defecto en Azure PostgreSQL
# Configurar retención extendida si es necesario
az postgres flexible-server parameter set \
  --resource-group retail-api-rg \
  --server-name retail-api-postgres-prod \
  --name backup_retention_days \
  --value 30
```

---

## 🔐 Configuración de Seguridad

### 🛡️ Azure Key Vault para Secretos

```bash
# Crear Key Vault
az keyvault create \
  --resource-group retail-api-rg \
  --name retail-api-keyvault \
  --location "East US"

# Agregar secretos
az keyvault secret set \
  --vault-name retail-api-keyvault \
  --name "django-secret-key" \
  --value "your-super-secret-key"

az keyvault secret set \
  --vault-name retail-api-keyvault \
  --name "db-password" \
  --value "VerySecurePassword2025!"
```

### 🌐 Configurar Custom Domain y SSL

```bash
# Mapear dominio personalizado
az webapp config hostname add \
  --webapp-name retail-api-webapp \
  --resource-group retail-api-rg \
  --hostname your-api-domain.com

# Habilitar HTTPS/SSL managed certificate
az webapp config ssl bind \
  --certificate-thumbprint $(az webapp config ssl upload \
    --certificate-file path/to/certificate.pfx \
    --certificate-password "cert-password" \
    --name retail-api-webapp \
    --resource-group retail-api-rg \
    --query thumbprint -o tsv) \
  --ssl-type SNI \
  --name retail-api-webapp \
  --resource-group retail-api-rg
```

---

## 📊 Monitoreo y Logging

### 🔍 Application Insights

```bash
# Crear Application Insights
az monitor app-insights component create \
  --app retail-api-insights \
  --location "East US" \
  --resource-group retail-api-rg

# Obtener Instrumentation Key
az monitor app-insights component show \
  --app retail-api-insights \
  --resource-group retail-api-rg \
  --query instrumentationKey -o tsv
```

### 📈 Log Analytics

```bash
# Crear Log Analytics workspace
az monitor log-analytics workspace create \
  --resource-group retail-api-rg \
  --workspace-name retail-api-logs \
  --location "East US"
```

---

## 💰 Estimación de Costos

| Servicio | Configuración | Costo Mensual Estimado (USD) |
|----------|---------------|-------------------------------|
| **App Service B2** | 2 Core, 3.5GB RAM | ~$55 |
| **PostgreSQL Standard_D2s_v3** | 2 vCore, 8GB RAM | ~$120 |
| **Container Registry** | Basic tier | ~$5 |
| **Application Insights** | Standard | ~$10 |
| **Storage Account** | Standard LRS | ~$5 |
| **Total Estimado** | | **~$195/mes** |

### 💡 Optimización de Costos

```bash
# Usar Azure Cost Management
az consumption budget create \
  --budget-name retail-api-budget \
  --amount 200 \
  --time-grain Monthly \
  --resource-group retail-api-rg

# Auto-shutdown para desarrollo
az webapp config appsettings set \
  --resource-group retail-api-rg \
  --name retail-api-webapp \
  --settings WEBSITE_TIME_ZONE="Eastern Standard Time"
```

---

## ✅ Checklist de Deployment

### 🚀 Pre-Deployment
- [ ] Código en repositorio de Git
- [ ] Variables de entorno configuradas
- [ ] Migraciones de BD probadas
- [ ] Tests pasando
- [ ] SSL/HTTPS configurado

### 🔧 Durante Deployment
- [ ] Recursos de Azure creados
- [ ] Base de datos inicializada
- [ ] App desplegada exitosamente
- [ ] Monitoreo configurado
- [ ] Backups programados

### ✅ Post-Deployment
- [ ] Health checks funcionando
- [ ] Load testing realizado
- [ ] Logs siendo capturados
- [ ] Alertas configuradas
- [ ] Documentación actualizada

---

## 🆘 Troubleshooting Común

### ❌ Error: "Application failed to start"

```bash
# Verificar logs
az webapp log tail --name retail-api-webapp --resource-group retail-api-rg

# Verificar variables de entorno
az webapp config appsettings list --name retail-api-webapp --resource-group retail-api-rg
```

### ❌ Error de Conexión a Base de Datos

```bash
# Verificar firewall rules
az postgres flexible-server firewall-rule list \
  --resource-group retail-api-rg \
  --name retail-api-postgres

# Test de conexión
az postgres flexible-server connect \
  --name retail-api-postgres \
  --admin-user retailadmin \
  --database-name retail_api_db
```

### ❌ Performance Issues

```bash
# Escalar App Service
az appservice plan update \
  --name retail-api-plan \
  --resource-group retail-api-rg \
  --sku P2V2

# Habilitar auto-scaling
az monitor autoscale create \
  --resource-group retail-api-rg \
  --resource retail-api-webapp \
  --resource-type Microsoft.Web/sites \
  --name retail-api-autoscale \
  --min-count 1 \
  --max-count 5 \
  --count 2
```

---

## 📞 Recursos y Soporte

- **Azure Documentation**: https://docs.microsoft.com/azure/
- **Azure Status**: https://status.azure.com/
- **Pricing Calculator**: https://azure.microsoft.com/pricing/calculator/
- **Support Tickets**: Azure Portal > Help + Support

¡Tu Retail API estará ejecutándose en Azure con alta disponibilidad y escalabilidad! 🚀