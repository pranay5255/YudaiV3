#!/bin/bash

# YudaiV3 Langfuse Setup Script
# This script helps you configure Langfuse with your object storage credentials

set -e

echo "🚀 YudaiV3 Langfuse Setup"
echo "=========================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo "✅ Created .env file"
else
    echo "📝 .env file already exists"
fi

# Generate encryption key
echo "🔐 Generating encryption key..."
ENCRYPTION_KEY=$(openssl rand -hex 32)
echo "Generated encryption key: $ENCRYPTION_KEY"

# Update .env file with generated key
sed -i "s/LANGFUSE_ENCRYPTION_KEY=.*/LANGFUSE_ENCRYPTION_KEY=$ENCRYPTION_KEY/" .env

echo ""
echo "🔧 Configuration Options:"
echo "1. Use local MinIO (default) - data stored locally"
echo "2. Use external S3-compatible storage (AWS S3, etc.)"
echo "3. Skip object storage configuration for now"
echo ""

read -p "Choose option (1-3): " choice

case $choice in
    1)
        echo "✅ Using local MinIO storage"
        echo "MinIO will be available at:"
        echo "  - API: http://localhost:9090"
        echo "  - Console: http://localhost:9091"
        echo "  - Default credentials: minio / miniosecret"
        ;;
    2)
        echo "🌐 External S3 Configuration"
        echo ""
        read -p "Enter S3 endpoint URL (e.g., https://s3.amazonaws.com): " s3_endpoint
        read -p "Enter S3 access key ID: " s3_access_key
        read -p "Enter S3 secret access key: " s3_secret_key
        read -p "Enter S3 region (e.g., us-east-1): " s3_region
        read -p "Enter S3 bucket name: " s3_bucket
        
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
        
        echo "✅ External S3 configuration updated"
        ;;
    3)
        echo "⏭️  Skipping object storage configuration"
        ;;
    *)
        echo "❌ Invalid option"
        exit 1
        ;;
esac

echo ""
echo "🔑 Security Configuration"
echo "=========================="

# Generate secure salt
SALT=$(openssl rand -hex 16)
sed -i "s/LANGFUSE_SALT=.*/LANGFUSE_SALT=$SALT/" .env

# Generate secure NextAuth secret
NEXTAUTH_SECRET=$(openssl rand -hex 32)
sed -i "s/LANGFUSE_NEXTAUTH_SECRET=.*/LANGFUSE_NEXTAUTH_SECRET=$NEXTAUTH_SECRET/" .env

# Generate secure Redis password
REDIS_AUTH=$(openssl rand -hex 16)
sed -i "s/REDIS_AUTH=.*/REDIS_AUTH=$REDIS_AUTH/" .env

# Generate secure ClickHouse password
CLICKHOUSE_PASSWORD=$(openssl rand -hex 16)
sed -i "s/CLICKHOUSE_PASSWORD=.*/CLICKHOUSE_PASSWORD=$CLICKHOUSE_PASSWORD/" .env

echo "✅ Generated secure credentials:"
echo "  - Salt: $SALT"
echo "  - NextAuth Secret: $NEXTAUTH_SECRET"
echo "  - Redis Password: $REDIS_AUTH"
echo "  - ClickHouse Password: $CLICKHOUSE_PASSWORD"

echo ""
echo "📋 Next Steps:"
echo "1. Update your .env file with your actual API keys:"
echo "   - OPENROUTER_API_KEY"
echo "   - GITHUB_CLIENT_ID"
echo "   - GITHUB_CLIENT_SECRET"
echo ""
echo "2. Start the services:"
echo "   docker compose up -d"
echo ""
echo "3. Access the applications:"
echo "   - YudaiV3 Frontend: http://localhost:5173"
echo "   - YudaiV3 Backend: http://localhost:8000"
echo "   - Langfuse UI: http://localhost:3000"
echo "   - MinIO Console: http://localhost:9091 (if using local MinIO)"
echo ""
echo "4. Initialize Langfuse (first time only):"
echo "   - Visit http://localhost:3000"
echo "   - Create your first organization and project"
echo ""

echo "�� Setup complete!" 