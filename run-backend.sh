#!/bin/bash

# Script to run only the database and backend containers for testing

echo "🚀 Starting YudaiV3 Backend Services..."

# Check if .env file exists
if [ ! -f "backend/.env" ]; then
    echo "⚠️  No .env file found in backend directory"
    echo "�� Creating .env file from template..."
    cp backend/.env.example backend/.env
    echo "🔑 Please edit backend/.env and add your OPENROUTER_API_KEY"
    echo "   You can get one from: https://openrouter.ai/keys"
    echo ""
    echo "Press Enter to continue with default values..."
    read
fi

# Run only db and backend services
echo "🐳 Starting database and backend containers..."
docker compose up db backend

echo "✅ Backend services are running!"
echo "📊 Database: localhost:5432"
echo "🔌 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "🧪 To test the Daifu chat:"
echo "   curl -X POST http://localhost:8000/chat/daifu \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"message\": {\"content\": \"Hello Daifu!\", \"is_code\": false}}'" 