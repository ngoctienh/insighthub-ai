# InsightHub AI — AI-powered Product Feedback Management Platform

**InsightHub AI** là nền tảng **Product Discovery SaaS** hỗ trợ đội ngũ Product thu thập phản hồi đa kênh, phát hiện feedback trùng lặp, gom nhóm thành Insight bằng AI, chấm điểm mức độ ưu tiên (`0.4V + 0.35I + 0.25S`), sinh nháp phản hồi khách hàng, quản lý luồng xử lý trên Kanban và đồng bộ Product Roadmap (Public / Private).

---

## 1. Kiến trúc & Công nghệ

| Thành phần | Công nghệ chính | Thư mục |
|---|---|---|
| **Frontend SaaS** | React 18, TypeScript, Vite, Tailwind CSS, Recharts, Axios | [`frontend/`](frontend/) |
| **Backend API** | Python, Django, Django REST Framework, SimpleJWT, RBAC, Gunicorn, WhiteNoise | [`backend/`](backend/) |
| **AI Microservice** | FastAPI, scikit-learn (Word+Concept+Char TF-IDF + SVD + Cosine Similarity + DBSCAN), OpenAI / Anthropic LLM (tùy chọn) | [`ai_service/`](ai_service/) |
| **Database & Queue** | PostgreSQL 16 (fallback SQLite cho quick test), Redis 7, Celery Worker | [`docker-compose.yml`](docker-compose.yml) |

---

## 2. Chức năng nổi bật theo phân quyền (RBAC)

- **Admin (`ADMIN`)**: Quản lý người dùng, phân quyền RBAC, quản lý sản phẩm & nguồn tiếp nhận, toàn quyền trên Feedback / Insight / Roadmap.
- **Product Manager (`PRODUCT_MANAGER`)**: Điều hành Feedback Inbox, chạy **AI Insight Engine**, xác nhận/từ chối/gộp/tách nhóm insight, điều chỉnh điểm ưu tiên, kéo thả Kanban và xuất bản Roadmap (Public/Private).
- **Developer (`DEVELOPER`) & Customer Support (`CUSTOMER_SUPPORT`)**: Tiếp nhận và xử lý feedback/insight được phân công, cập nhật trạng thái Kanban, trao đổi bình luận nội bộ hoặc tạo nháp trả lời khách hàng.
- **Customer (`CUSTOMER`)**: Gửi feedback qua portal, theo dõi trạng thái xử lý phản hồi của bản thân, nhận thông báo cập nhật và xem **Public Roadmap** (đã ẩn thông tin nội bộ).

Tất cả phân quyền đều được kiểm tra trực tiếp trên API Django backend (`permissions.py` và row-level `get_queryset`), không chỉ ẩn nút trên giao diện.

---

## 3. Cấu trúc thư mục

```text
insighthub-ai/
├── ai_service/                 # FastAPI AI Engine (Tiền xử lý, Embedding, Similarity, DBSCAN, Summarize, Priority, Draft Reply)
│   ├── app/
│   └── tests/
├── backend/                    # Django + DRF + Celery Backend
│   ├── apps/
│   │   ├── accounts/           # Auth, JWT, Password Reset, RBAC Roles & Users
│   │   ├── feedbacks/          # Dashboard, Multi-source Ingestion, Feedback Inbox, Tags
│   │   ├── insights/           # AI Jobs, Insight Groups, Merge/Split, Kanban
│   │   ├── roadmap/            # Public & Private Product Roadmap
│   │   ├── notifications/      # Notifications, Comments, Votes, Activity Audit Logs
│   │   └── core/               # Pagination, Exceptions, Demo Data Seeder & Pytest Suite
│   └── insighthub/             # Settings, URLs, WSGI/ASGI, Celery
├── frontend/                   # React + TypeScript + Tailwind + Recharts SPA
│   ├── src/
│   │   ├── api/                # Axios client + JWT refresh interceptor
│   │   ├── components/         # Layout, Badges, ProtectedRoute
│   │   ├── contexts/           # AuthContext, ToastContext
│   │   └── pages/              # 17 màn hình nghiệp vụ đầy đủ
│   ├── Dockerfile & nginx.conf
│   └── vercel.json
├── docs/                       # Tài liệu kiến trúc, ERD, API, Thuật toán AI & Deploy
├── docker-compose.yml          # Full stack (PostgreSQL + Redis + AI + Backend + Celery + Nginx)
├── render.yaml                 # Render Blueprint deploy 1 click
└── .env.example
```

---

## 4. Tài liệu thiết kế chi tiết

- [01 — Kiến trúc hệ thống & Ma trận phân quyền](docs/01_SYSTEM_ARCHITECTURE.md)
- [02 — Thiết kế cơ sở dữ liệu PostgreSQL & ERD (16 bảng)](docs/02_DATABASE_ERD.md)
- [03 — Đặc tả REST API (Backend & AI Service)](docs/03_API_DOCUMENTATION.md)
- [04 — Quy trình & Thuật toán AI Insight Engine](docs/04_AI_ALGORITHM.md)
- [05 — Hướng dẫn Deploy Online (Render / Vercel / Railway / Docker)](docs/05_DEPLOYMENT_GUIDE.md)

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
Truy cập Frontend: `http://localhost:3000` | Backend Health: `http://localhost:8000/api/health/` | AI Swagger: `http://localhost:8001/docs`.

### Cách B — Chạy trực tiếp trên máy (Venv + NodeJS)

1. **Chuẩn bị môi trường biến**:
   ```bash
   cp .env.example .env
   ```
   *(Nếu chưa cài PostgreSQL cục bộ, có thể bật `USE_SQLITE_FALLBACK=True` trong `.env` để thử nghiệm nhanh.)*

2. **Chạy AI Microservice (Terminal 1)**:
   ```bash
   cd ai_service
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```

3. **Chạy Backend Django (Terminal 2)**:
   ```bash
   cd backend
   python manage.py migrate
   python manage.py seed_demo_data
   python manage.py runserver 0.0.0.0:8000
   ```

4. **Chạy Frontend React Vite (Terminal 3)**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Mở trình duyệt tại `http://localhost:5173`.

---

## 7. Chạy Automated Tests & Build Check

```bash
# 1. Test AI Service (Preprocessing, Cosine Similarity, DBSCAN, Priority Score)
cd ai_service && pytest -v

# 2. Test Backend (Auth/RBAC, Multi-source Ingestion, AI Clustering Pipeline, Kanban/Roadmap/Notifications)
cd backend && pytest -v

# 3. Typecheck & Build Frontend Production
cd frontend && npm run build
```

---

## 8. Checklist Deploy Online cho Giảng viên truy cập

1. Push toàn bộ dự án lên GitHub repository cá nhân (kiểm tra `.env` không bị commit).
2. Xem hướng dẫn chi tiết tại [docs/05_DEPLOYMENT_GUIDE.md](docs/05_DEPLOYMENT_GUIDE.md) để tạo Blueprint trên **Render** (`render.yaml`) hoặc kết hợp **Vercel + Railway/Render + Neon PostgreSQL**.
3. Sau khi deploy xong, đồng bộ `VITE_API_BASE_URL` (trên Frontend) với `CORS_ALLOWED_ORIGINS` & `CSRF_TRUSTED_ORIGINS` (trên Backend) và kiểm tra `/api/health/`.
