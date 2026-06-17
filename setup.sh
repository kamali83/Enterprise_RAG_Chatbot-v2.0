#!/bin/bash

# Enterprise RAG Chatbot - Quick Start Script
# This script sets up and runs the application

set -e

echo "========================================="
echo "  Enterprise RAG Chatbot - Setup"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"
}

# Create necessary directories
create_directories() {
    echo "Creating necessary directories..."
    mkdir -p logs data/docs faiss_index
    touch logs/.gitkeep data/docs/.gitkeep faiss_index/.gitkeep
    echo -e "${GREEN}✓ Directories created${NC}"
}

# Setup environment file
setup_env() {
    if [ ! -f .env ]; then
        echo "Creating .env file..."
        cp .env.example .env 2>/dev/null || cat > .env << EOF
# Application Settings
APP_NAME=Enterprise RAG Chatbot
APP_VERSION=2.0.0
DEBUG=True

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rag_chatbot
DATABASE_ASYNC_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rag_chatbot

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379/0

# JWT Authentication
SECRET_KEY=$(openssl rand -hex 32)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# LLM Configuration
LLM_PROVIDER=local
MODEL_NAME=google/flan-t5-large

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
EOF
        echo -e "${GREEN}✓ .env file created${NC}"
    else
        echo -e "${YELLOW}! .env file already exists${NC}"
    fi
}

# Choose deployment mode
choose_mode() {
    echo ""
    echo "Select deployment mode:"
    echo "1) Docker Compose (Recommended)"
    echo "2) Local Development (requires Python, PostgreSQL, Redis)"
    echo ""
    read -p "Enter choice [1-2]: " mode
    
    case $mode in
        1)
            docker_setup
            ;;
        2)
            local_setup
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
}

# Docker Compose setup
docker_setup() {
    echo ""
    echo -e "${YELLOW}Starting Docker Compose setup...${NC}"
    
    # Start services
    echo "Starting services (this may take a few minutes)..."
    docker-compose up -d
    
    # Wait for services to be ready
    echo "Waiting for services to be ready..."
    sleep 10
    
    # Check health
    echo "Checking service health..."
    if curl -s http://localhost:8000/api/health > /dev/null; then
        echo -e "${GREEN}✓ Application is running!${NC}"
    else
        echo -e "${YELLOW}! Application may still be starting. Check logs with: docker-compose logs -f${NC}"
    fi
    
    echo ""
    echo "========================================="
    echo "  Setup Complete!"
    echo "========================================="
    echo ""
    echo "Access points:"
    echo "  - Frontend:    http://localhost:8000/frontend"
    echo "  - API Docs:    http://localhost:8000/docs"
    echo "  - Health:      http://localhost:8000/api/health"
    echo ""
    echo "Useful commands:"
    echo "  - View logs:   docker-compose logs -f"
    echo "  - Stop:        docker-compose down"
    echo "  - Restart:     docker-compose restart"
    echo ""
}

# Local development setup
local_setup() {
    echo ""
    echo -e "${YELLOW}Starting local development setup...${NC}"
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is not installed${NC}"
        exit 1
    fi
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    fi
    
    # Activate virtual environment
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    # Install dependencies
    echo "Installing dependencies (this may take a few minutes)..."
    pip install --upgrade pip
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
    
    # Run database migration
    echo "Running database migration..."
    python migrate_db.py
    
    echo ""
    echo "========================================="
    echo "  Setup Complete!"
    echo "========================================="
    echo ""
    echo "To start the application:"
    echo "  1. Ensure PostgreSQL and Redis are running"
    echo "  2. Run: source venv/bin/activate"
    echo "  3. Run: uvicorn main:app --reload"
    echo ""
    echo "Access points:"
    echo "  - Frontend:    http://localhost:8000/frontend"
    echo "  - API Docs:    http://localhost:8000/docs"
    echo ""
}

# Main execution
main() {
    check_docker
    create_directories
    setup_env
    choose_mode
}

# Run main function
main
