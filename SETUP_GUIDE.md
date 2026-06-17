# Setup Guide - Enterprise RAG Chatbot v2.0

## Quick Start

### Option 1: Using Docker Compose (Recommended)

This is the easiest way to run the application with all dependencies (PostgreSQL, Redis).

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Access the application
# Frontend: http://localhost:8000/frontend
# API Docs: http://localhost:8000/docs
# Health: http://localhost:8000/api/health
```

### Option 2: Local Development

#### Prerequisites

1. **Python 3.10+**
2. **PostgreSQL 15+**
3. **Redis 7+**

#### Step 1: Install PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Create database:**
```bash
sudo -u postgres psql
CREATE DATABASE rag_chatbot;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE rag_chatbot TO postgres;
\q
```

#### Step 2: Install Redis

```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

#### Step 3: Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Step 4: Configure Environment

Edit `.env` file with your settings:
```bash
# For local development with SQLite (testing only)
DATABASE_URL=sqlite:///./rag_chatbot.db
DATABASE_ASYNC_URL=sqlite+aiosqlite:///./rag_chatbot.db

# Or with PostgreSQL (recommended)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rag_chatbot
DATABASE_ASYNC_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rag_chatbot

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

#### Step 5: Run Database Migration (if upgrading from v1.0)

```bash
python migrate_db.py
```

#### Step 6: Start the Application

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Access:
- **Frontend:** http://localhost:8000/frontend
- **API Docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/api/health

---

## Troubleshooting

### PostgreSQL Connection Error

**Error:** `could not connect to server: Connection refused`

**Solution:**
1. Check if PostgreSQL is running: `sudo systemctl status postgresql`
2. Start PostgreSQL: `sudo systemctl start postgresql`
3. Verify database exists: `psql -U postgres -l`

### Redis Connection Error

**Error:** `Error connecting to Redis`

**Solution:**
1. Check if Redis is running: `redis-cli ping` (should return `PONG`)
2. Start Redis: `sudo systemctl start redis`

### Missing Dependencies

**Error:** `ModuleNotFoundError: No module named 'xxx'`

**Solution:**
```bash
pip install -r requirements.txt
```

### Port Already in Use

**Error:** `Address already in use`

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>
```

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py -v
```

---

## Production Deployment

### Environment Variables for Production

```bash
# Set a secure secret key
SECRET_KEY=$(openssl rand -hex 32)

# Disable debug mode
DEBUG=False

# Production database
DATABASE_URL=postgresql://user:password@prod-db-host:5432/rag_chatbot

# Production Redis
REDIS_HOST=prod-redis-host
```

### Docker Production

```bash
# Build and run
docker-compose -f docker-compose.yml build
docker-compose up -d

# With monitoring
docker-compose --profile monitoring up -d
```

### Kubernetes (Coming Soon)

See `k8s/` directory for Helm charts and manifests.

---

## Architecture Overview

```
┌─────────────┐
│   Client    │
│  (Browser)  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│         FastAPI Application     │
│  ┌───────────────────────────┐  │
│  │   API Routes (6 modules)  │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │   Services (7 modules)    │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Repositories (4 modules) │  │
│  └───────────────────────────┘  │
└─────────┬───────────┬───────────┘
          │           │
     ┌────▼────┐ ┌───▼────┐
     │PostgreSQL│ │ Redis  │
     │ Database │ │ Cache  │
     └──────────┘ └────────┘
```

---

## Support

For issues and questions:
- Check the [README.md](README.md) for general documentation
- Review [ENHANCEMENTS.md](ENHANCEMENTS.md) for feature details
- Create an issue on GitHub
- Contact: support@example.com

---

**Enterprise RAG Chatbot v2.0 - Built for Production** 🚀
