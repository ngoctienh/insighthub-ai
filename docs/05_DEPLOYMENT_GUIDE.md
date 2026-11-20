# HƯỚNG DẪN DEPLOY ONLINE & CHẠY PRODUCTION — INSIGHTHUB AI

Tài liệu này hướng dẫn từng bước triển khai **InsightHub AI** (100% thuần Python: Django Templates + DRF + FastAPI AI + PostgreSQL + Redis/Celery) lên môi trường cloud công khai có URL truy cập.

---

## 1. Kiểm tra trước khi Deploy

1. Đảm bảo repository có đầy đủ các file cấu hình ở thư mục gốc:
   - `render.yaml` (Render Blueprint cho PostgreSQL + FastAPI AI Service + Django Web App)
   - `docker-compose.yml` (Docker full stack gồm PostgreSQL + Redis + FastAPI AI + Django Web + Celery Worker)
   - `backend/Dockerfile`, `ai_service/Dockerfile`, `backend/entrypoint.sh`
   - `backend/requirements.txt`, `ai_service/requirements.txt`
2. Tuyệt đối **không** commit file `.env` thật hay mật khẩu/API key lên Git (`.gitignore` đã chặn `.env`, `.venv`, `db.sqlite3`).
3. Hệ thống hỗ trợ sẵn 2 chế độ AI:
   - **Có `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`**: dùng OpenAI Embeddings (`text-embedding-3-small`) + GPT / Claude để tóm tắt và soạn nháp phản hồi khách hàng.
   - **Không nhập API key (Zero-cost Demo)**: tự động kích hoạt Local ML Pipeline (`scikit-learn` TF-IDF + `TruncatedSVD` + `DBSCAN`) chạy ổn định dưới 512MB RAM của gói miễn phí.

---

## 2. Phương án 1 (Khuyên dùng — 1 click trên Render): Render Blueprint

Vì giao diện đã dùng hoàn toàn **Django Templates** phục vụ trực tiếp trên cùng domain với Django, bạn **không cần deploy frontend riêng** và **không gặp lỗi CORS**.

File `render.yaml` khai báo sẵn 3 thành phần:
1. `insighthub-db`: Managed **PostgreSQL** (`plan: free`).
2. `insighthub-ai-service`: **FastAPI** (`rootDir: ai_service`, health `/health`).
3. `insighthub-web`: **Django Templates + DRF + Gunicorn + WhiteNoise** (`rootDir: backend`, tự chạy `migrate`, `seed_demo_data`, `gunicorn`). `settings.py` tự động thêm `RENDER_EXTERNAL_HOSTNAME` / `RENDER_EXTERNAL_URL` vào `ALLOWED_HOSTS` và `CSRF_TRUSTED_ORIGINS`.

### Các bước thực hiện:
1. **Commit & Push mã nguồn lên GitHub**:
   ```bash
   git add .
   git commit -m "Complete Topic 9: Pure Python Django Templates + FastAPI + PostgreSQL + Celery"
   git push origin main
   ```
2. **Tạo Blueprint trên Render**:
   - Đăng nhập [Render Dashboard](https://dashboard.render.com) -> **New +** -> **Blueprint**.
   - Kết nối repository `ngoctienh/insighthub-ai` -> Render tự đọc `render.yaml`.
   - Khi được hỏi các biến `sync: false`:
     - `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`: dán key thật nếu muốn bật LLM cloud, hoặc để trống để chạy Local ML/NLP.
     - `DEMO_USER_PASSWORD`: nhập `InsightDemo!2026` (hoặc mật khẩu riêng cho bản demo).
   - Bấm **Apply** và chờ Render build 2 web service + khởi tạo PostgreSQL (~3–5 phút).
3. **Kiểm tra sau Deploy**:
   - Mở `https://<insighthub-ai-service>.onrender.com/health` -> `{"status": "ok"}`.
   - Mở `https://<insighthub-web>.onrender.com/api/health/` -> `{"status": "ok", "database": "connected"}`.
   - Truy cập `https://<insighthub-web>.onrender.com/` và đăng nhập thử bằng tài khoản **PM** (`pm_minh` / `InsightDemo!2026`) hoặc **Admin** (`admin`).

> **Mẹo Free Tier Render**: Service free tự sleep sau 15 phút không truy cập; request đầu tiên có thể mất ~30–50 giây để khởi động lại. Nên mở URL kiểm tra trước buổi demo khoảng 2 phút.

---

## 3. Phương án 2: Deploy Full-Stack có Redis + Celery Worker (Railway / VPS Docker)

Nếu bạn muốn kích hoạt **Redis + Celery Worker** chạy background job thực tế trên cloud:
- **Trên Railway**: Tạo 1 Project gồm 4 service: PostgreSQL plugin, Redis plugin, `ai_service` (Root: `ai_service`), `web` (Root: `backend`, `CELERY_ENABLED=True`), và `worker` (Root: `backend`, Start Command: `celery -A insighthub worker --loglevel=info`).
- **Trên VPS bằng Docker Compose**:
  ```bash
  cp .env.example .env
  docker compose up --build -d
  ```
  Hệ thống khởi chạy đủ 5 container (`postgres`, `redis`, `ai_service`, `web`, `celery_worker`). Truy cập ngay tại `http://<server-ip>:8000`.
