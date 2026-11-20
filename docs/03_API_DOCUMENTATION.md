# TÀI LIỆU ROUTES & REST API — INSIGHTHUB AI

Tài liệu đặc tả **Web Routes (Django Templates)**, **REST API (Django + DRF)** và **FastAPI AI Microservice**.

---

## 1. Web Application Routes (`apps.web` — Django Templates + Session Auth)

| Route | View | Quyền truy cập | Mô tả |
|---|---|---|---|
| `/` | `landing_view` | Public | Trang giới thiệu tổng quan quy trình Product Discovery. |
| `/login/` | `login_view` | Public | Đăng nhập bằng username hoặc email (hỗ trợ chọn nhanh tài khoản demo). |
| `/register/` | `register_view` | Public | Đăng ký tài khoản mới (tự động gán vai trò `CUSTOMER`). |
| `/logout/` | `logout_view` | `POST` | Đăng xuất session hiện tại. |
| `/public-roadmap/` | `public_roadmap_view` | Public | Lộ trình sản phẩm công khai (chỉ `visibility=PUBLIC`, ẩn thông tin nội bộ). |
| `/portal/` | `portal_view` | `login_required` | Cổng khách hàng: gửi feedback, xem tiến trình 4 bước và thông báo. |
| `/dashboard/` | `dashboard_view` | `dashboard` | KPIs, 5 biểu đồ Chart.js, Top 5 vấn đề & Insight khẩn cấp. |
| `/inbox/` | `inbox_view` | `inbox` | Danh sách feedback, lọc đa chiều, tìm kiếm, phân trang, tạo mới, vote, xóa. |
| `/inbox/<id>/` | `feedback_detail_view` | `inbox` / `kanban` | Chi tiết feedback, tóm tắt AI, quét tương đồng Cosine, đánh dấu trùng, gán người xử lý, tag. |
| `/sources/` | `sources_hub_view` | `sources` | Giả lập tiếp nhận đa nguồn (Website Form, Email, Live Chat, Community). |
| `/insights/` | `insights_view` | `insights` | Chạy AI Clustering (Sync/Celery polling), duyệt Insight, kiểm duyệt trùng lặp (Xác nhận/Bỏ qua), gom nhóm thủ công. |
| `/insights/ai-task/<task_id>/` | `ai_task_status_view` | `ai_run` / `insights` | JSON polling trạng thái Celery task. |
| `/insights/<id>/` | `insight_detail_view` | `insights` | Chi tiết Insight, nguyên nhân, đề xuất, nháp phản hồi (3 tone), chỉnh sửa & ưu tiên tay, gộp/tách nhóm, đưa lên Roadmap. |
| `/kanban/` | `kanban_view` | `kanban` | Bảng Kanban 4 cột (`NEW`, `REVIEWING`, `PLANNED`, `DONE`) cho Insight & Feedback (hỗ trợ Drag & Drop). |
| `/roadmap/` | `roadmap_view` | `roadmap` | Quản trị Product Roadmap (Public & Private) và liên kết Insight. |
| `/notifications/` | `notifications_view` | `login_required` | Trung tâm thông báo, lọc chưa đọc, đánh dấu đã đọc & điều hướng. |
| `/users/` | `users_view` | `users` (Admin ghi) | Quản lý user & bảng ma trận phân quyền chức năng động cho từng Role. |
| `/settings/` | `settings_view` | `login_required` | Hồ sơ cá nhân, đổi mật khẩu, quản lý Sản phẩm & Tag (Admin/PM). |

---

## 2. Quy ước REST API & Xác thực (`/api/...`)

### 2.1. Base URL
| Service | Local Development | Docker Compose | Cloud Production (Render/Railway) |
|---|---|---|---|
| **Web & Backend API** | `http://localhost:8000/api` | `http://localhost:8000/api` | `https://<web-domain>/api` |
| **AI Service** | `http://localhost:8001` | `http://ai_service:8001` | `https://<ai-service-domain>` |

### 2.2. Headers xác thực
1. **JWT Bearer Authentication** (cho REST API `/api/...`):
   ```http
   Authorization: Bearer <access_token>
   ```
   - `ACCESS_TOKEN_LIFETIME`: `60` phút; `REFRESH_TOKEN_LIFETIME`: `7` ngày (xoay vòng + blacklist khi logout).
2. **Internal Service Key** (Django gọi FastAPI AI Service):
   ```http
   X-API-Key: <AI_SERVICE_API_KEY>
   ```

### 2.3. Phân trang & Định dạng lỗi chuẩn
- **Pagination mặc định**: `PAGE_SIZE = 20` (`page`, `page_size`). Response: `{ "count", "next", "previous", "results" }`.
- **Định dạng lỗi (`custom_exception_handler`)**:
  ```json
  {
    "detail": "Dữ liệu không hợp lệ hoặc thao tác bị từ chối.",
    "errors": {
      "field_name": ["Thông báo lỗi chi tiết."]
    }
  }
  ```

---

## 3. Chi tiết REST API Endpoints (`backend/`)

### 3.1. Health Check
| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/health/` | `AllowAny` | Kiểm tra backend & kết nối PostgreSQL (`SELECT 1`). |

### 3.2. Auth, Roles & User Management (`apps.accounts`)
| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| `POST` | `/api/auth/register/` | `AllowAny` | Đăng ký tài khoản mới (ép role `CUSTOMER`), trả về `access`, `refresh`, `user`. |
| `POST` | `/api/auth/login/` | `AllowAny` | Đăng nhập bằng `identifier` (email hoặc username) + `password`. |
| `POST` | `/api/auth/logout/` | `IsAuthenticated` | Blacklist `refresh` token. |
| `POST` | `/api/auth/token/refresh/` | `AllowAny` | Làm mới JWT token. |
| `GET/PATCH` | `/api/auth/me/` | `IsAuthenticated` | Xem / cập nhật `full_name`, `job_title`, danh sách `permissions`. |
| `POST` | `/api/auth/change-password/` | `IsAuthenticated` | Đổi mật khẩu (`old_password`, `new_password`). |
| `GET` | `/api/roles/` | `IsAuthenticated` | Danh sách 5 role kèm `permissions` và `user_count`. |
| `PATCH/PUT` | `/api/roles/{id}/` | `IsAdmin` | Cập nhật danh sách `permissions` cho vai trò. |
| `GET` | `/api/roles/features/` | `IsAuthenticated` | Danh sách 8 feature modules có thể phân quyền. |
| `POST` | `/api/roles/reset_defaults/` | `IsAdmin` | Khôi phục quyền mặc định cho cả 5 role. |
| `GET/POST/PATCH/DELETE` | `/api/users/` | `UserManagementPermission` | Đọc: có quyền `users` (hoặc `?internal_only=true` cho team nội bộ); Ghi: `IsAdmin`. |
| `POST` | `/api/users/{id}/toggle_active/` | `IsAdmin` | Bật/tắt trạng thái `is_active`. |

### 3.3. Dashboard, Products, Sources & Tags (`apps.feedbacks`)
| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/dashboard/` | `require_feature("dashboard")` | Query `product`, `days` (7..90). Trả `kpis`, `feedbacks_by_date`, `feedbacks_by_source`, `feedbacks_by_status`, `feedbacks_by_tag`, `by_priority`, `top_5_issues`, `urgent_insights`. |
| `GET/POST/PATCH/DELETE` | `/api/products/` | Đọc: `AllowAny`; Ghi: `IsPMOrAdmin` | Quản lý sản phẩm (`name`, `slug`, `description`, `is_active`). |
| `GET/POST/PATCH/DELETE` | `/api/sources/` | Đọc: `IsAuthenticated`; Ghi: `IsPMOrAdmin` | Quản lý kênh tiếp nhận (`WEB_FORM`, `EMAIL`, `LIVE_CHAT`, `COMMUNITY`). |
| `GET/POST/PATCH/DELETE` | `/api/tags/` | Đọc: `IsAuthenticated`; Ghi: `IsPMOrAdmin` | Quản lý nhãn (`name`, `slug`, `color`). |

### 3.4. Feedback Inbox & Multi-source Hub (`apps.feedbacks`)
- Row-level RBAC: `CUSTOMER` chỉ xem phản hồi của mình; `DEVELOPER` chỉ xem mục được gán trực tiếp hoặc thuộc insight được gán cho mình.

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| `POST` | `/api/sources/ingest/` | `require_feature("sources")` | Tiếp nhận phản hồi đa nguồn (`WEB_FORM`, `EMAIL`, `LIVE_CHAT`, `COMMUNITY`). |
| `GET/POST` | `/api/feedbacks/` | `require_feature("inbox", "kanban")` | Lọc (`search`, `status`, `source`, `impact_level`, `priority_level`, `product`, `assigned_to`, `tag`, `date_from`, `date_to`, `unclustered_only`, `duplicate_only`, `mine_only`), sắp xếp và tạo mới. |
| `GET/PATCH/DELETE` | `/api/feedbacks/{id}/` | `require_feature("inbox", "kanban")` + RBAC theo role | Xem, sửa (Customer chỉ sửa được title/content/impact khi `NEW`), hoặc xóa theo quyền. |
| `POST` | `/api/feedbacks/{id}/assign/` | `ADMIN`, `PM`, `CS` | `{ "assigned_to": user_id \| null }`. |
| `POST` | `/api/feedbacks/{id}/tags/` | `IsInternalTeam` | `{ "tag_ids": [1, 2] }`. |
| `POST` | `/api/feedbacks/{id}/summarize/` | `IsInternalTeam` | Gọi AI Service tạo & lưu `ai_summary` cho 1 feedback. |
| `GET` | `/api/feedbacks/{id}/similar/` | `IsInternalTeam` | Gọi AI `/similarity/search` tìm các feedback tương tự nhất. |
| `POST` | `/api/feedbacks/{id}/mark_duplicate/` | `ADMIN`, `PM`, `CS` | Đánh dấu trùng lặp với `duplicate_of_id`. |
| `POST` | `/api/feedbacks/{id}/unmark_duplicate/` | `IsInternalTeam` | Gỡ đánh dấu / gợi ý trùng lặp. |
| `POST` | `/api/feedbacks/{id}/vote/` | `require_feature("inbox", "kanban")` | Bật/tắt vote cho feedback. |

### 3.5. AI Insight Engine & Kanban (`apps.insights`)
| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| `POST` | `/api/ai/analyze/` | `require_feature("ai_run")` | Chạy AI pipeline (`similarity_threshold`, `eps`, `min_samples`, `use_llm`, `include_clustered`). Trả `200` (sync) hoặc `202` `{ "status": "QUEUED", "task_id" }` (Celery). |
| `GET` | `/api/ai/tasks/{task_id}/` | `require_feature("ai_run", "insights")` | Kiểm tra trạng thái & kết quả task Celery (`PENDING`, `STARTED`, `SUCCESS`, `FAILURE`). |
| `GET` | `/api/ai/duplicates/` | `require_feature("insights")` | Danh sách cặp feedback nghi trùng lặp chưa xác nhận. |
| `GET` | `/api/ai/unassigned/` | `require_feature("insights")` | Danh sách tối đa 100 feedback chưa thuộc nhóm Insight nào. |
| `GET/POST/PATCH/DELETE` | `/api/insights/` | `require_feature("insights", "kanban", "roadmap")` / `IsPMOrAdmin` | Danh sách, chi tiết, tạo thủ công, chỉnh sửa `priority_score`/`title`/`description`. |
| `POST` | `/api/insights/{id}/confirm/` & `reject/` | `IsPMOrAdmin` | Xác nhận hoặc từ chối nhóm Insight đề xuất. |
| `POST` | `/api/insights/{id}/add_feedbacks/` & `remove_feedback/` | `IsPMOrAdmin` | Thêm/gỡ feedback khỏi nhóm & tự tính lại điểm. |
| `POST` | `/api/insights/{id}/merge/` & `split/` | `IsPMOrAdmin` | Gộp 2 nhóm Insight hoặc tách feedback sang nhóm mới. |
| `POST` | `/api/insights/{id}/move_kanban/` | `require_feature("kanban")` | Chuyển cột `NEW` / `REVIEWING` / `PLANNED` / `DONE` & phân công. |
| `POST` | `/api/insights/{id}/regenerate_reply/` | `IsInternalTeam` | Tạo lại nháp phản hồi khách hàng theo tone (`empathetic`, `update`, `resolved`). |
| `POST` | `/api/insights/{id}/vote/` | `require_feature("insights", "kanban", "roadmap")` | Bật/tắt vote cho nhóm Insight. |

### 3.6. Product Roadmap & Notifications (`apps.roadmap`, `apps.notifications`)
| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/roadmap/public/` | `AllowAny` | Chỉ trả item `PUBLIC` & trạng thái `PLANNED`/`IN_PROGRESS`/`COMPLETED` (dùng `PublicRoadmapItemSerializer`). |
| `GET/POST/PATCH/DELETE` | `/api/roadmap/` | `require_feature("roadmap")` / `IsPMOrAdmin` | Quản lý hạng mục Private & Public Roadmap. |
| `GET` | `/api/notifications/` | `IsAuthenticated` | Thông báo cá nhân (`recipient=request.user`), filter `unread_only`, `event_type`. |
| `GET` | `/api/notifications/unread_count/` | `IsAuthenticated` | `{ "unread_count": int }`. |
| `POST` | `/api/notifications/{id}/mark_read/` | `IsAuthenticated` | Đánh dấu 1 thông báo đã đọc. |
| `POST` | `/api/notifications/mark_all_read/` | `IsAuthenticated` | Đánh dấu tất cả thông báo đã đọc. |

---

## 4. FastAPI AI Microservice API (`ai_service/`)

| Method | Endpoint | Header | Mô tả |
|---|---|---|---|
| `GET` | `/health` | — | Kiểm tra trạng thái AI Service và cấu hình OpenAI/Anthropic. |
| `POST` | `/embed` | `X-API-Key` | Tạo embedding vectors chuẩn hóa L2 cho danh sách feedback. |
| `POST` | `/similarity/search` | `X-API-Key` | Tìm top-k feedback tương đồng theo Cosine Similarity. |
| `POST` | `/summarize` | `X-API-Key` | Tóm tắt vấn đề, nguyên nhân giả thuyết, đề xuất, nháp phản hồi & chấm điểm `0.4V + 0.35I + 0.25S`. |
| `POST` | `/draft-reply` | `X-API-Key` | Sinh nháp thư phản hồi khách hàng theo tone. |
| `POST` | `/analyze` | `X-API-Key` | Chạy toàn bộ pipeline 6 bước (Preprocess → Embed → Similarity → DBSCAN → Summarize → Scoring). |
