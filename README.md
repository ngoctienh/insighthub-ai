# InsightHub AI — AI-powered Product Feedback Management Platform

**InsightHub AI** là nền tảng **Product Discovery SaaS** thuần Python hỗ trợ đội ngũ Product thu thập phản hồi đa kênh, phát hiện feedback trùng lặp, gom nhóm thành Insight bằng AI, chấm điểm mức độ ưu tiên (`0.4V + 0.35I + 0.25S`), sinh nháp phản hồi khách hàng, quản lý luồng xử lý trên Kanban và đồng bộ Product Roadmap (Public / Private).

---

## 1. Kiến trúc & Công nghệ (Thuần Python)

| Thành phần | Công nghệ chính | Thư mục |
|---|---|---|
| **Web App & UI** | Python, Django, **Django Templates**, Tailwind CSS, Chart.js, Session Auth + RBAC, WhiteNoise, Gunicorn | [`backend/apps/web/`](backend/apps/web/), [`backend/templates/`](backend/templates/) |
| **REST API** | Django REST Framework, SimpleJWT (phục vụ tích hợp/API clients) | [`backend/apps/`](backend/apps/) |
| **AI Microservice** | FastAPI, scikit-learn (Word+Concept+Char TF-IDF + SVD + Cosine Similarity + DBSCAN), OpenAI / Anthropic LLM (tùy chọn) | [`ai_service/`](ai_service/) |
| **Database & Queue** | PostgreSQL 16 (fallback SQLite cho quick test), Redis 7, Celery Worker | [`docker-compose.yml`](docker-compose.yml) |

---

## 2. Chức năng nổi bật theo phân quyền (RBAC)

- **Admin (`ADMIN`)**: Quản lý người dùng, cấu hình bảng phân quyền chức năng động theo từng vai trò (`Role.permissions`), quản lý sản phẩm & nguồn tiếp nhận, toàn quyền trên Feedback / Insight / Roadmap.
- **Product Manager (`PRODUCT_MANAGER`)**: Điều hành Feedback Inbox, chạy **AI Insight Engine**, xác nhận/từ chối/gộp/tách/chỉnh tay điểm ưu tiên nhóm insight, kéo thả Kanban và xuất bản Roadmap (Public/Private).
- **Developer (`DEVELOPER`) & Customer Support (`CUSTOMER_SUPPORT`)**: Tiếp nhận và xử lý feedback/insight được phân công, cập nhật trạng thái Kanban, kiểm tra tương đồng AI và tạo nháp trả lời khách hàng.
- **Customer (`CUSTOMER`)**: Gửi feedback qua Customer Portal, theo dõi tiến trình 4 bước xử lý phản hồi của bản thân, nhận thông báo cập nhật và xem **Public Roadmap** (đã ẩn thông tin nội bộ).

Tất cả phân quyền đều được kiểm tra trực tiếp trên server Django (`apps/web/decorators.py`, `apps/accounts/permissions.py` và row-level scoping).

---

## 3. Cấu trúc thư mục

```text
insighthub-ai/
├── ai_service/                 # FastAPI AI Engine (Tiền xử lý, Embedding, Similarity, DBSCAN, Summarize, Priority, Draft Reply)
│   ├── app/
│   └── tests/
├── backend/                    # Django Full-stack (Web Templates UI + DRF API + Celery)
│   ├── apps/
│   │   ├── accounts/           # Auth, JWT, Dynamic RBAC Roles & Users
│   │   ├── feedbacks/          # Dashboard metrics, Multi-source Ingestion, Feedback Inbox, Tags
│   │   ├── insights/           # AI Pipeline, Celery Task Status, Insight Groups, Merge/Split, Kanban
│   │   ├── roadmap/            # Public & Private Product Roadmap
│   │   ├── notifications/      # Notifications & Votes
│   │   ├── web/                # Django MVT Views, RBAC Decorators, Context Processors, Template Tags
│   │   └── core/               # Pagination, Exceptions, Demo Data Seeder & Pytest Suite
│   ├── templates/              # 16 màn hình Django Templates + Tailwind CSS + Chart.js
│   ├── static/                 # Static JS helpers (Kanban drag-drop, Toast, Celery polling)
│   └── insighthub/             # Settings, URLs, WSGI/ASGI, Celery
├── database/                   # PostgreSQL Schema & Seed SQL dump
├── docs/                       # Tài liệu kiến trúc, ERD, API, Thuật toán AI & Deploy
├── docker-compose.yml          # Full stack (PostgreSQL + Redis + AI + Web + Celery Worker)
├── render.yaml                 # Render Blueprint deploy 1 click (thuần Python)
└── .env.example
```

---

## 4. Tài liệu thiết kế chi tiết

- [01 — Kiến trúc hệ thống & Ma trận phân quyền](docs/01_SYSTEM_ARCHITECTURE.md)
- [02 — Thiết kế cơ sở dữ liệu PostgreSQL & ERD (13 bảng)](docs/02_DATABASE_ERD.md)
- [03 — Đặc tả REST API & Routes](docs/03_API_DOCUMENTATION.md)
- [04 — Quy trình & Thuật toán AI Insight Engine](docs/04_AI_ALGORITHM.md)
- [05 — Hướng dẫn Deploy Online (Render / Railway / Docker)](docs/05_DEPLOYMENT_GUIDE.md)

---

## 5. Tài khoản Demo mặc định (Seed Data)

Lệnh `python manage.py seed_demo_data` khởi tạo sẵn **1 sản phẩm (`Bếp Việt Go`)**, **4 kênh tiếp nhận**, **8 người dùng**, **54 feedback tiếng Việt thực tế** (42 đã gom vào 5 nhóm insight + 12 feedback chưa gom để chạy live AI Clustering), **5 insight** và **5 roadmap items**.

> Mật khẩu mặc định lấy từ biến môi trường `DEMO_USER_PASSWORD` (mặc định: `InsightDemo!2026`).

| Vai trò | Username | Email đăng nhập |
|---|---|---|
| **Admin** | `admin` | `admin@insighthub.vn` |
| **Product Manager** | `pm_minh` | `pm@insighthub.vn` |
| **Developer** | `dev_tuan` | `dev@insighthub.vn` |
| **Customer Support** | `cs_linh` | `cs@insighthub.vn` |
| **Customer** | `customer_an` | `an.nguyen@gmail.com` |

---

## 6. Hướng dẫn chạy Local Development

### Cách A — Khởi chạy nhanh bằng Docker Compose (PostgreSQL + Redis + Celery + Full App)
```bash
cp .env.example .env
docker compose up --build -d
```
Truy cập Web App: `http://localhost:8000` | Backend Health: `http://localhost:8000/api/health/` | AI Swagger: `http://localhost:8001/docs`.

### Cách B — Chạy trực tiếp trên máy (Python Venv)

1. **Chuẩn bị biến môi trường**:
   ```bash
   cp .env.example .env
   ```
   *(Nếu chưa cài PostgreSQL cục bộ, bật `USE_SQLITE_FALLBACK=True` trong `.env` để chạy thử nghiệm nhanh.)*

2. **Chạy AI Microservice (Terminal 1)**:
   ```bash
   cd ai_service
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```

3. **Chạy Web App Django (Terminal 2)**:
   ```bash
   cd backend
   python manage.py migrate
   python manage.py seed_demo_data
   python manage.py runserver 0.0.0.0:8000
   ```
   Mở trình duyệt tại `http://localhost:8000`.

---

## 7. Chạy Automated Tests & Check

```bash
# 1. Test AI Service (Preprocessing, Cosine Similarity, DBSCAN, Priority Score)
cd ai_service && pytest -v

# 2. Test Web App Django Templates + REST API (Auth/RBAC, Multi-source, AI Pipeline, Kanban, Roadmap, Notifications)
cd backend && pytest -v

# 3. Kiểm tra Django migration & staticfiles
cd backend && python manage.py check && python manage.py makemigrations --check --dry-run
```

---

## 8. Checklist Deploy Online

1. Commit & push toàn bộ dự án lên GitHub repository (`git push origin main`).
2. Xem hướng dẫn chi tiết tại [docs/05_DEPLOYMENT_GUIDE.md](docs/05_DEPLOYMENT_GUIDE.md) để tạo Blueprint trên **Render** (`render.yaml`) hoặc deploy trên **Railway** / **Fly.io**.
3. Sau khi deploy xong, mở URL web service `insighthub-web`, đăng nhập thử với `pm_minh` / `InsightDemo!2026` và kiểm tra `/api/health/`.
