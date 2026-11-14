# HƯỚNG DẪN DEPLOY ONLINE & CHẠY PRODUCTION — INSIGHTHUB AI

Tài liệu này hướng dẫn từng bước triển khai **InsightHub AI** lên môi trường cloud công khai (có URL truy cập cho giảng viên chấm bài) cũng như đóng gói full-stack bằng Docker Compose.

> **Lưu ý quan trọng**: Dự án đã chuẩn bị sẵn đầy đủ mã nguồn và file cấu hình deploy (`render.yaml`, `frontend/vercel.json`, `docker-compose.yml`, `backend/Dockerfile`, `ai_service/Dockerfile`, `frontend/Dockerfile`). Tuy nhiên, việc **push mã nguồn lên GitHub cá nhân** và **kết nối tài khoản Render / Railway / Vercel** cần thực hiện trên tài khoản cloud của bạn.

---

## 1. Kiểm tra trước khi Deploy

1. Đảm bảo repository có đầy đủ các file cấu hình ở thư mục gốc:
   - `render.yaml` (Render Blueprint cho Free PostgreSQL + FastAPI + Django + React Static Site)
   - `frontend/vercel.json` (SPA rewrite cho Vercel)
   - `docker-compose.yml` (cho Docker / VPS)
   - `backend/requirements.txt`, `ai_service/requirements.txt`, `frontend/package.json`
2. Tuyệt đối **không** commit file `.env` thật hay mật khẩu/API key lên Git (`.gitignore` đã chặn `.env`, `.venv`, `node_modules`, `db.sqlite3`).
3. Hệ thống hỗ trợ sẵn 2 chế độ AI:
   - **Có `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`**: dùng OpenAI Embeddings (`text-embedding-3-small`) + GPT / Claude để tóm tắt và soạn nháp phản hồi khách hàng.
   - **Không nhập API key (Zero-cost Demo)**: tự động kích hoạt Local ML Pipeline (`scikit-learn` TF-IDF đa nhánh Word + Domain Concept + Char n-gram + `TruncatedSVD` + `DBSCAN`) giúp AI Engine chạy mượt trên gói miễn phí (512 MB RAM) mà không tốn chi phí API.

---

## 2. Phương án 1 (Khuyên dùng — Một lần Deploy toàn bộ): Render Blueprint

File `render.yaml` đã khai báo sẵn 4 thành phần:
1. `insighthub-db`: Managed **PostgreSQL** (`plan: free`).
2. `insighthub-ai-service`: **FastAPI** (`rootDir: ai_service`, `/health`).
3. `insighthub-backend`: **Django + Gunicorn + WhiteNoise** (`rootDir: backend`, tự chạy `migrate`, `seed_demo_data`, `gunicorn`). Đặt `CELERY_ENABLED=False` để phù hợp Render Free Tier (không yêu cầu gói Worker trả phí).
4. `insighthub-frontend`: **React + Vite Static Site** (`rootDir: frontend`, publish `dist`, rewrite `/* -> /index.html`).

### Các bước thực hiện:
1. **Push mã nguồn lên GitHub**:
   ```bash
   git add .
   git commit -m "Initial InsightHub AI platform"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
2. **Tạo Blueprint trên Render**:
   - Đăng nhập [Render Dashboard](https://dashboard.render.com) -> **New +** -> **Blueprint**.
   - Chọn repository GitHub vừa push -> Render tự đọc `render.yaml`.
   - Khi được hỏi các biến `sync: false`, tạm nhập hoặc cập nhật ngay sau khi sinh domain:
     - `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`: để trống nếu dùng Local ML fallback, hoặc dán key thật nếu muốn bật LLM cloud.
     - `DEMO_USER_PASSWORD`: mật khẩu dùng chung cho tài khoản demo khi seed (mặc định nếu để trống trong code là `InsightDemo!2026`).
3. **Đồng bộ URL giữa Frontend & Backend (Bước bắt buộc để không lỗi CORS)**:
   Sau khi Render tạo xong service và cấp URL thật (ví dụ `https://insighthub-backend-xxxx.onrender.com` và `https://insighthub-frontend-xxxx.onrender.com`):
   - Mở service **`insighthub-frontend`** -> **Environment**:
     - Đặt `VITE_API_BASE_URL` = `https://insighthub-backend-xxxx.onrender.com/api`
     - Nhấn **Manual Deploy** -> **Clear build cache & deploy** (vì Vite nhúng biến `VITE_*` vào bundle tại thời điểm build).
   - Mở service **`insighthub-backend`** -> **Environment**:
     - Đặt `CORS_ALLOWED_ORIGINS` = `https://insighthub-frontend-xxxx.onrender.com`
     - Đặt `CSRF_TRUSTED_ORIGINS` = `https://insighthub-frontend-xxxx.onrender.com,https://insighthub-backend-xxxx.onrender.com`
     - Nhấn **Manual Deploy** để backend nhận cấu hình mới.
4. **Kiểm tra sau Deploy**:
   - Gọi `GET https://insighthub-ai-service-xxxx.onrender.com/health` -> `{"status": "ok"}`.
   - Gọi `GET https://insighthub-backend-xxxx.onrender.com/api/health/` -> `{"status": "ok", "database": "connected"}`.
   - Truy cập `https://insighthub-frontend-xxxx.onrender.com`, đăng nhập thử bằng tài khoản PM (`pm@insighthub.vn`) hoặc Admin (`admin@insighthub.vn`).

> **Mẹo Free Tier Render**: Service free tự sleep sau 15 phút không có truy cập; request đầu tiên có thể mất ~30–50 giây để khởi động lại. Nên mở URL kiểm tra trước buổi demo khoảng 2 phút.

---

## 3. Phương án 2: Frontend trên Vercel + Backend/AI trên Railway hoặc Render + Neon PostgreSQL

Phù hợp khi muốn giao diện React tải nhanh toàn cầu qua CDN Vercel:

### Bước A — Database & Redis Cloud (tùy chọn Celery)
- Tạo PostgreSQL miễn phí trên **Neon** (`neon.tech`) hoặc **Supabase** / **Railway**, lấy chuỗi kết nối dạng:
  `postgresql://user:pass@host:5432/dbname?sslmode=require`
- (Tùy chọn nếu muốn chạy background jobs bất đồng bộ) Tạo Redis trên **Upstash** hoặc **Railway**, lấy `REDIS_URL`.

### Bước B — Deploy AI Service & Backend lên Railway (hoặc Render)
1. **Service 1 — AI Service**:
   - Root Directory: `ai_service`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Env vars: `AI_PROVIDER=auto`, `AI_SERVICE_API_KEY=<random-secret>`, (tùy chọn `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`).
2. **Service 2 — Backend**:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - Start Command: `python manage.py migrate --noinput && python manage.py seed_demo_data && gunicorn insighthub.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - Env vars:
     - `DJANGO_SECRET_KEY=<chuoi-ngau-nhien-50+-ky-tu>`
     - `DJANGO_DEBUG=False`
     - `DJANGO_ALLOWED_HOSTS=<backend-domain>`
     - `DATABASE_URL=<postgres-connection-string>`
     - `AI_SERVICE_URL=https://<ai-service-domain>`
     - `AI_SERVICE_API_KEY=<khop-voi-ai-service>`
     - `CELERY_ENABLED=False` (hoặc `True` nếu bạn deploy thêm Service thứ 3 chạy `celery -A insighthub worker --loglevel=info` trỏ cùng `DATABASE_URL` & `REDIS_URL`).
3. **Cập nhật CORS & CSRF** sau khi có domain Vercel ở Bước C:
   - `CORS_ALLOWED_ORIGINS=https://<your-app>.vercel.app`
   - `CSRF_TRUSTED_ORIGINS=https://<your-app>.vercel.app,https://<backend-domain>`

### Bước C — Deploy Frontend lên Vercel
1. Vào [Vercel](https://vercel.com) -> **Add New Project** -> chọn repo GitHub.
2. **Root Directory**: chọn `frontend` (đã có `vercel.json` cấu hình rewrite SPA).
3. **Framework Preset**: `Vite`.
4. **Environment Variables**:
   - `VITE_API_BASE_URL` = `https://<backend-domain>/api`
5. Nhấn **Deploy** và đợi nhận URL công khai `https://<your-app>.vercel.app`.

---

## 4. Phương án 3: Docker Compose (VPS / Máy cá nhân — Đầy đủ PostgreSQL + Redis + Celery Worker)

`docker-compose.yml` khởi chạy đủ 6 container: `postgres`, `redis`, `ai_service`, `backend`, `celery_worker`, và `frontend` (Nginx reverse proxy `/api/` -> `backend:8000`).

```bash
cp .env.example .env
# Chỉnh sửa .env nếu muốn thêm OPENAI_API_KEY / ANTHROPIC_API_KEY hoặc đổi DEMO_USER_PASSWORD
docker compose up --build -d
```

Sau khi container healthy:
- Frontend UI & Nginx API proxy: `http://localhost:3000`
- Backend REST API: `http://localhost:8000/api/health/`
- FastAPI AI Service docs: `http://localhost:8001/docs`

Xem log khởi tạo và seed dữ liệu:
```bash
docker compose logs -f backend celery_worker ai_service
```

Tắt hệ thống:
```bash
docker compose down
```
