#!/usr/bin/env bash
# Creates or reconciles the three Container Apps used by the protected release workflow.
# This script is intentionally executed only after Azure OIDC login in GitHub Actions.
set -euo pipefail

required=(
  APP_ENV
  AZURE_RESOURCE_GROUP
  AZURE_LOCATION
  AZURE_CONTAINERAPPS_ENVIRONMENT
  AZURE_API_APP
  AZURE_WORKER_APP
  AZURE_DISPATCHER_APP
  API_IMAGE
  WORKER_IMAGE
  DATABASE_URL
  REDIS_URL
  OBJECT_STORAGE_ENDPOINT_URL
  OBJECT_STORAGE_ACCESS_KEY_ID
  OBJECT_STORAGE_SECRET_ACCESS_KEY
  OBJECT_STORAGE_BUCKET
  QDRANT_URL
  QDRANT_API_KEY
  NVIDIA_API_KEY
  NVIDIA_INPUT_COST_PER_MILLION_USD
  NVIDIA_OUTPUT_COST_PER_MILLION_USD
  TAVILY_API_KEY
  SUPABASE_URL
  ACCESS_TOKEN_ISSUER
  CORS_ALLOWED_ORIGINS
  LANGFUSE_PUBLIC_KEY
  LANGFUSE_SECRET_KEY
)

for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required release configuration: ${name}" >&2
    exit 2
  fi
done

if [[ "$APP_ENV" != "preview" && "$APP_ENV" != "production" ]]; then
  echo "APP_ENV must be preview or production" >&2
  exit 2
fi

if [[ "${1:-}" == "--check" ]]; then
  echo "Release configuration is complete for $APP_ENV; no Azure resource was changed."
  exit 0
fi

az config set extension.use_dynamic_install=yes_without_prompt
az provider register --namespace Microsoft.App --wait --only-show-errors
az group create --name "$AZURE_RESOURCE_GROUP" --location "$AZURE_LOCATION" --only-show-errors >/dev/null

if ! az containerapp env show \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_CONTAINERAPPS_ENVIRONMENT" \
  --only-show-errors >/dev/null 2>&1; then
  # No Azure Monitor workspace is created implicitly. This keeps the student/demo path
  # within a deliberate cost boundary; Langfuse remains the planned trace destination.
  az containerapp env create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_CONTAINERAPPS_ENVIRONMENT" \
    --location "$AZURE_LOCATION" \
    --logs-destination none \
    --only-show-errors >/dev/null
fi

secret_args=(
  "database-url=$DATABASE_URL"
  "redis-url=$REDIS_URL"
  "object-storage-access-key-id=$OBJECT_STORAGE_ACCESS_KEY_ID"
  "object-storage-secret-access-key=$OBJECT_STORAGE_SECRET_ACCESS_KEY"
  "qdrant-api-key=$QDRANT_API_KEY"
  "nvidia-api-key=$NVIDIA_API_KEY"
  "tavily-api-key=$TAVILY_API_KEY"
  "langfuse-public-key=$LANGFUSE_PUBLIC_KEY"
  "langfuse-secret-key=$LANGFUSE_SECRET_KEY"
)

common_env=(
  "APP_ENV=$APP_ENV"
  "DATABASE_URL=secretref:database-url"
  "REDIS_URL=secretref:redis-url"
  "OBJECT_STORAGE_ENDPOINT_URL=$OBJECT_STORAGE_ENDPOINT_URL"
  "OBJECT_STORAGE_ACCESS_KEY_ID=secretref:object-storage-access-key-id"
  "OBJECT_STORAGE_SECRET_ACCESS_KEY=secretref:object-storage-secret-access-key"
  "OBJECT_STORAGE_BUCKET=$OBJECT_STORAGE_BUCKET"
  "OBJECT_STORAGE_REGION=${OBJECT_STORAGE_REGION:-us-east-1}"
  "LLM_PROVIDER=nvidia"
  "EMBEDDING_PROVIDER=nvidia"
  "NVIDIA_API_KEY=secretref:nvidia-api-key"
  "NVIDIA_BASE_URL=${NVIDIA_BASE_URL:-https://integrate.api.nvidia.com/v1}"
  "NVIDIA_MODEL=${NVIDIA_MODEL:-z-ai/glm-5.2}"
  "NVIDIA_EMBEDDING_MODEL=${NVIDIA_EMBEDDING_MODEL:-nvidia/nv-embed-v1}"
  "EMBEDDING_DIMENSION=4096"
  "QDRANT_URL=$QDRANT_URL"
  "QDRANT_API_KEY=secretref:qdrant-api-key"
  "QDRANT_COLLECTION=${QDRANT_COLLECTION:-researchmate_chunks}"
  "WEB_SEARCH_PROVIDER=tavily"
  "TAVILY_API_KEY=secretref:tavily-api-key"
  "LANGFUSE_ENABLED=true"
  "LANGFUSE_PUBLIC_KEY=secretref:langfuse-public-key"
  "LANGFUSE_SECRET_KEY=secretref:langfuse-secret-key"
  "LANGFUSE_BASE_URL=${LANGFUSE_BASE_URL:-https://cloud.langfuse.com}"
  "NVIDIA_INPUT_COST_PER_MILLION_USD=$NVIDIA_INPUT_COST_PER_MILLION_USD"
  "NVIDIA_OUTPUT_COST_PER_MILLION_USD=$NVIDIA_OUTPUT_COST_PER_MILLION_USD"
)

create_or_update() {
  local name="$1"
  local image="$2"
  local ingress="$3"
  local role="$4"

  if ! az containerapp show --resource-group "$AZURE_RESOURCE_GROUP" --name "$name" --only-show-errors >/dev/null 2>&1; then
    local create_args=(
      containerapp create
      --resource-group "$AZURE_RESOURCE_GROUP"
      --name "$name"
      --environment "$AZURE_CONTAINERAPPS_ENVIRONMENT"
      --image "$image"
      --cpu 0.25
      --memory 0.5Gi
      --min-replicas 1
      --max-replicas 1
      --secrets "${secret_args[@]}"
      --env-vars "${common_env[@]}" "RESEARCHMATE_PROCESS_ROLE=$role"
      --only-show-errors
    )
    if [[ "$ingress" == "external" ]]; then
      create_args+=(--ingress external --target-port 8000)
    fi
    az "${create_args[@]}" >/dev/null
  else
    az containerapp secret set \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --name "$name" \
      --secrets "${secret_args[@]}" \
      --only-show-errors >/dev/null
    az containerapp update \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --name "$name" \
      --image "$image" \
      --min-replicas 1 \
      --max-replicas 1 \
      --set-env-vars "${common_env[@]}" "RESEARCHMATE_PROCESS_ROLE=$role" \
      --only-show-errors >/dev/null
  fi
}

create_or_update "$AZURE_API_APP" "$API_IMAGE" external api
create_or_update "$AZURE_WORKER_APP" "$WORKER_IMAGE" internal worker
create_or_update "$AZURE_DISPATCHER_APP" "$WORKER_IMAGE" internal dispatcher

api_fqdn="$(az containerapp show \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_API_APP" \
  --query 'properties.configuration.ingress.fqdn' \
  --output tsv \
  --only-show-errors)"

if [[ -z "$api_fqdn" ]]; then
  echo "Azure API app has no external FQDN" >&2
  exit 3
fi

if [[ -n "${GITHUB_ENV:-}" ]]; then
  echo "API_HEALTH_URL=https://$api_fqdn" >> "$GITHUB_ENV"
fi

echo "Azure Container Apps reconciled for $APP_ENV. API endpoint recorded without credentials."
