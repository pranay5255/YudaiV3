#!/bin/bash

# YudaiV3 S3 Configuration Script
# This script helps you configure external S3-compatible storage for Langfuse

set -e

echo "🌐 YudaiV3 S3 Configuration"
echo "============================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please run ./scripts/setup-langfuse.sh first."
    exit 1
fi

echo "This script will help you configure external S3-compatible storage for Langfuse."
echo "Supported providers: AWS S3, Google Cloud Storage, Azure Blob Storage, MinIO, etc."
echo ""

read -p "Enter S3 endpoint URL (e.g., https://s3.amazonaws.com): " s3_endpoint
read -p "Enter S3 access key ID: " s3_access_key
read -p "Enter S3 secret access key: " s3_secret_key
read -p "Enter S3 region (e.g., us-east-1): " s3_region
read -p "Enter S3 bucket name: " s3_bucket

echo ""
echo "🔧 Updating configuration..."

# Update .env with external S3 configuration
sed -i "s|LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=.*|LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=$s3_endpoint|" .env
sed -i "s/LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=.*/LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=$s3_access_key/" .env
sed -i "s/LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=.*/LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=$s3_secret_key/" .env
sed -i "s/LANGFUSE_S3_EVENT_UPLOAD_REGION=.*/LANGFUSE_S3_EVENT_UPLOAD_REGION=$s3_region/" .env
sed -i "s/LANGFUSE_S3_EVENT_UPLOAD_BUCKET=.*/LANGFUSE_S3_EVENT_UPLOAD_BUCKET=$s3_bucket/" .env
sed -i "s/LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=.*/LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=false/" .env

sed -i "s|LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT=.*|LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT=$s3_endpoint|" .env
sed -i "s/LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID=.*/LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID=$s3_access_key/" .env
sed -i "s/LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY=.*/LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY=$s3_secret_key/" .env
sed -i "s/LANGFUSE_S3_MEDIA_UPLOAD_REGION=.*/LANGFUSE_S3_MEDIA_UPLOAD_REGION=$s3_region/" .env
sed -i "s/LANGFUSE_S3_MEDIA_UPLOAD_BUCKET=.*/LANGFUSE_S3_MEDIA_UPLOAD_BUCKET=$s3_bucket/" .env
sed -i "s/LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE=.*/LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE=false/" .env

sed -i "s|LANGFUSE_S3_BATCH_EXPORT_ENDPOINT=.*|LANGFUSE_S3_BATCH_EXPORT_ENDPOINT=$s3_endpoint|" .env
sed -i "s|LANGFUSE_S3_BATCH_EXPORT_EXTERNAL_ENDPOINT=.*|LANGFUSE_S3_BATCH_EXPORT_EXTERNAL_ENDPOINT=$s3_endpoint|" .env
sed -i "s/LANGFUSE_S3_BATCH_EXPORT_ACCESS_KEY_ID=.*/LANGFUSE_S3_BATCH_EXPORT_ACCESS_KEY_ID=$s3_access_key/" .env
sed -i "s/LANGFUSE_S3_BATCH_EXPORT_SECRET_ACCESS_KEY=.*/LANGFUSE_S3_BATCH_EXPORT_SECRET_ACCESS_KEY=$s3_secret_key/" .env
sed -i "s/LANGFUSE_S3_BATCH_EXPORT_REGION=.*/LANGFUSE_S3_BATCH_EXPORT_REGION=$s3_region/" .env
sed -i "s/LANGFUSE_S3_BATCH_EXPORT_BUCKET=.*/LANGFUSE_S3_BATCH_EXPORT_BUCKET=$s3_bucket/" .env
sed -i "s/LANGFUSE_S3_BATCH_EXPORT_FORCE_PATH_STYLE=.*/LANGFUSE_S3_BATCH_EXPORT_FORCE_PATH_STYLE=false/" .env

echo "✅ S3 configuration updated successfully!"
echo ""
echo "📋 Configuration Summary:"
echo "  - Endpoint: $s3_endpoint"
echo "  - Region: $s3_region"
echo "  - Bucket: $s3_bucket"
echo "  - Access Key: $s3_access_key"
echo ""
echo "🔄 Next Steps:"
echo "1. Restart the services to apply changes:"
echo "   docker compose down && docker compose up -d"
echo ""
echo "2. Verify the configuration:"
echo "   docker compose logs langfuse-worker"
echo ""
echo "3. Check Langfuse UI for any errors:"
echo "   open http://localhost:3000"
echo ""
echo "🎉 S3 configuration complete!" 