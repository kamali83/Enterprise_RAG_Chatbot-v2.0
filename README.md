# Enterprise RAG Chatbot v2.0

A production-ready, enterprise-grade Retrieval-Augmented Generation (RAG) chatbot for intelligent document Q&A.

## 🚀 Features

### Core Capabilities
- **Multi-LLM Support**: Switch between local models (FLAN-T5), OpenAI, and Ollama
- **Advanced RAG Pipeline**: Retrieval with optional reranking for better answer quality
- **Semantic Caching**: Redis-backed caching with semantic similarity matching
- **Multi-user Authentication**: JWT-based secure authentication
- **Conversation Management**: Persistent chat history with search capabilities
- **Document Management**: Upload, manage, and index PDF, TXT, DOCX, and Markdown files

### Enterprise Features
- **PostgreSQL Database**: Production-ready relational database
- **Redis Caching**: High-performance caching layer
- **Rate Limiting**: API rate limiting to prevent abuse
- **Structured Logging**: Loguru-based logging with correlation IDs
- **Prometheus Metrics**: Built-in monitoring and observability
- **Docker Support**: Full containerization with Docker Compose
- **CI/CD Pipeline**: GitHub Actions for automated testing and deployment

### Developer Experience
- **Modular Architecture**: Clean separation of concerns (API, Services, Repositories)
- **Async/Await**: Full async support for high concurrency
- **Type Hints**: Comprehensive type annotations
- **Test Suite**: Pytest-based testing with >80% coverage
- **API Documentation**: Auto-generated OpenAPI/Swagger docs

---

## 📁 Project Structure

```
Enterprise_Chatbot_002/
├── app/
│   ├── api/                  # API routes
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── conversations.py # Conversation management
│   │   ├── rag.py           # RAG Q&A endpoints
│   │   ├── documents.py     # Document management
│   │   └── health.py        # Health & monitoring
│   ├── core/                 # Core configuration
│   │   ├── config.py        # Pydantic settings
│   │   ├── database.py      # DB connections
│   │   ├── security.py      # Auth & JWT
│   │   ├── logging.py       # Logging setup
│   │   └── middleware.py    # Custom middleware
│   ├── models/               # Data models
│   │   ├── db_models.py     # SQLAlchemy models
│   │   └── schemas.py       # Pydantic schemas
│   ├── repositories/         # Data access layer
│   │   ├── base.py          # Generic repository
│   │   ├── user_repository.py
│   │   ├── conversation_repository.py
│   │   └── message_repository.py
│   ├── services/             # Business logic
│   │   ├── auth_service.py
│   │   ├── llm_service.py   # Multi-LLM provider
│   │   ├── rag_service.py   # RAG pipeline
│   │   ├── cache_service.py # Redis caching
│   │   └── document_service.py
│   └── __init__.py
├── tests/                    # Test suite
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_conversations.py
│   └── test_rag.py
├── frontend/                 # Web UI
├── data/docs/               # Uploaded documents
├── faiss_index/             # Vector store
├── logs/                    # Application logs
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env
└── main.py
```

---

## 🛠️ Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for containerized deployment)
- PostgreSQL 15+
- Redis 7+

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repo-url>
cd Enterprise_Chatbot_002

# Configure environment variables
cp .env.example .env
# Edit .env with your settings

# Start all services
docker-compose up -d

# Access the application
# Frontend: http://localhost:8000/frontend
# API Docs: http://localhost:8000/docs
# Health: http://localhost:8000/api/health
```

### Option 2: Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your settings

# Start PostgreSQL and Redis
# (Use Docker or install locally)

# Run database migrations
python -c "from app.core.database import init_db; init_db()"

# Start the application
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/rag_chatbot` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT secret key | (auto-generated) |
| `LLM_PROVIDER` | LLM provider (`local`, `openai`, `ollama`) | `local` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `EMBEDDING_MODEL` | Sentence transformer model | `sentence-transformers/all-MiniLM-L6-v2` |
| `CHUNK_SIZE` | Document chunk size | `1000` |
| `RETRIEVAL_K` | Number of documents to retrieve | `5` |
| `USE_RERANKING` | Enable document reranking | `False` |

See `.env` file for all available options.

---

## 📡 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup` | Register new user |
| POST | `/api/auth/login` | Login and get token |

### Conversations
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/conversations` | Create conversation |
| GET | `/api/conversations` | List conversations |
| GET | `/api/conversations/{id}` | Get conversation |
| PUT | `/api/conversations/{id}` | Rename conversation |
| DELETE | `/api/conversations/{id}` | Delete conversation |
| POST | `/api/conversations/{id}/messages` | Add message |
| GET | `/api/conversations/{id}/messages` | Get messages |

### RAG (Q&A)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ask` | Ask a question |
| GET | `/api/ask_stream` | Ask with streaming |
| GET | `/api/sources` | List document sources |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents` | List documents |
| POST | `/api/documents` | Upload document |
| DELETE | `/api/documents/{filename}` | Delete document |
| POST | `/api/documents/reindex` | Reindex all documents |

### Health & Monitoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/metrics` | Prometheus metrics |
| GET | `/api/stats/documents` | Document statistics |

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py -v

# Run with live reload for development
pytest --watch
```

---

## 📊 Monitoring

### Prometheus Metrics

Access metrics at `http://localhost:9090` (when using Docker Compose with monitoring profile):

```bash
docker-compose --profile monitoring up -d
```

### Key Metrics
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `http_requests_in_progress` - Active requests

### Grafana Dashboards

Access Grafana at `http://localhost:3000` (admin/admin)

---

## 🔐 Security

### Authentication
- JWT-based authentication with configurable expiry
- Bcrypt password hashing
- Automatic token refresh

### Rate Limiting
- Default: 60 requests per minute per IP
- Configurable via `RATE_LIMIT_PER_MINUTE`

### Best Practices
- Never commit `.env` files
- Rotate `SECRET_KEY` regularly
- Use HTTPS in production
- Enable CORS only for trusted origins

---

## 🚀 Production Deployment

### Docker Swarm

```bash
docker swarm init
docker stack deploy -c docker-compose.yml rag-chatbot
```

### Kubernetes

See `k8s/` directory for Helm charts and manifests (coming soon).

### Environment-Specific Configs

```bash
# Development
docker-compose -f docker-compose.yml up -d

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 🔄 Architecture Decisions

### Why PostgreSQL?
- ACID compliance for conversation integrity
- Better scalability than SQLite
- Rich querying capabilities
- Production-proven reliability

### Why Redis?
- Sub-millisecond response times
- Semantic caching support
- Pub/sub for real-time features
- Battle-tested caching solution

### Why Modular Architecture?
- Easy to test individual components
- Swappable implementations (e.g., vector stores)
- Clear separation of concerns
- Better maintainability

---

## 🛣️ Roadmap

### Phase 1 (Completed) ✅
- [x] PostgreSQL migration
- [x] Redis caching integration
- [x] Rate limiting
- [x] Structured logging
- [x] Modular architecture

### Phase 2 (Completed) ✅
- [x] Service/Repository pattern
- [x] Pydantic settings
- [x] Docker Compose
- [x] Test suite

### Phase 3 (In Progress) 🚧
- [x] Multi-LLM support
- [x] Re-ranking
- [ ] Query rewriting (HyDE)
- [ ] Multi-modal RAG

### Phase 4 (Planned) 📋
- [ ] OpenTelemetry tracing
- [ ] RBAC with admin dashboard
- [ ] Audit logging
- [ ] CI/CD pipeline

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style
- Follow PEP 8
- Use type hints
- Write tests for new features
- Update documentation

---

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

---

## 🙏 Acknowledgments

- LangChain for RAG orchestration
- Hugging Face for models and transformers
- FastAPI for the web framework
- The open-source community

---

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check existing documentation
- Contact: support@example.com

---

**Built with ❤️ for Enterprise AI**
# Enterprise_RAG_Chatbot-v2.0
