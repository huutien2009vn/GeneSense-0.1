# GeneSense AI Core

Web app/PWA hỗ trợ chẩn đoán sàng lọc và quản lý bệnh mạn tính chủ động theo ba tầng: **phả hệ PGRS × thể trạng BRS × biến thiên sinh hiệu**. Hệ thống kết hợp hồ sơ gia đình, Google Gemini, Web Bluetooth và luồng tài khoản riêng để theo dõi dài hạn.

> **Lưu ý y tế:** Đây là phần mềm minh họa, không phải thiết bị y tế. Kết quả không dùng để chẩn đoán, kê đơn hoặc thay thế nhân viên y tế. Với đau ngực, khó thở, lú lẫn, yếu liệt hoặc dấu hiệu cấp cứu, hãy liên hệ dịch vụ cấp cứu tại nơi bạn sống.

## Trải nghiệm người dùng

- Đăng nhập Google theo luồng OpenID Connect phía server; mỗi người dùng chỉ thấy hồ sơ và lịch sử của mình.
- Lần đăng nhập đầu tiên có hướng dẫn 3 bước: thông tin cá nhân, gia đình gần và dòng họ bên nội/bên ngoại.
- Dashboard ưu tiên ngôn ngữ dễ hiểu, trạng thái xanh/vàng/đỏ và không hiển thị dữ liệu giả khi chưa đo.
- Tab **Hôm nay** chỉ giữ trạng thái, chỉ số gần nhất và thao tác cần thiết; biểu đồ/lời khuyên nằm trong **Lịch sử**.
- Ảnh kết quả xét nghiệm, đơn thuốc hoặc giấy khám có thể được AI trích xuất; người dùng phải xem lại và xác nhận trước khi lưu. Ảnh gốc không được GeneSense lưu lại.
- Nhập số đo thủ công, kết nối thiết bị BLE hoặc chạy mô phỏng có gắn nhãn rõ ràng.
- Xem biểu đồ, lịch sử, lời khuyên và gửi phản hồi trên máy tính hoặc điện thoại.

## Cấu trúc dự án

```text
GeneSense/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI, API, bảo vệ request, phục vụ PWA
│   │   ├── auth.py                 # Google OIDC, phiên đăng nhập, đăng xuất
│   │   ├── config.py               # Cấu hình môi trường
│   │   ├── database.py             # SQLAlchemy async + Neon
│   │   ├── migrations.py           # Nâng cấp schema tối thiểu khi khởi động
│   │   ├── models.py               # User, phiên, lần đo, tài liệu sức khỏe
│   │   ├── schemas.py              # Kiểm tra request/response
│   │   └── services/
│   │       ├── risk_engine.py       # PGRS, BRS, sinh hiệu, ngưỡng động
│   │       └── ai_service.py        # Google Gemini JSON Schema + fallback quy tắc
│   ├── tests/
│   │   ├── test_accounts.py
│   │   └── test_risk_engine.py
│   └── requirements.txt
├── frontend/
│   ├── index.html                  # Đăng nhập, onboarding, dashboard, lịch sử
│   ├── assets/styles.css           # Medical UI responsive
│   ├── js/
│   │   ├── app.js                  # Tài khoản, UI, form, luồng đo
│   │   ├── api.js                  # API client có cookie phiên
│   │   ├── ble.js                  # BLE + Moving Average Filter
│   │   ├── chart.js                # Biểu đồ Canvas
│   │   └── icons.js                # Biểu tượng SVG nội tuyến
│   ├── manifest.webmanifest
│   └── sw.js
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

## Chạy demo nhanh bằng SQLite

Yêu cầu: Python 3.11+; Chrome hoặc Edge mới nếu thử Bluetooth.

### Windows PowerShell

```powershell
cd "C:\duong-dan\GeneSense"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### macOS/Linux

```bash
cd "/duong-dan/GeneSense"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp .env.example .env
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Mở duy nhất [http://localhost:8000](http://localhost:8000). Khi chưa cấu hình Google, chọn **Khám phá với tài khoản demo**, hoàn tất hồ sơ lần đầu rồi ghi một lần đo. API docs dành cho phát triển ở [http://localhost:8000/docs](http://localhost:8000/docs).

Nếu PowerShell báo không tìm thấy `Activate.ps1`, hãy kiểm tra terminal đang đứng đúng thư mục dự án và `.venv` đã được tạo ở đó. Không gửi thư mục `.venv` cho người khác; mỗi máy phải tự tạo môi trường Python.

## Cấu hình đăng nhập Google

> Khóa Google AI Studio **không phải** thông tin đăng nhập Google. OAuth bắt buộc có `GOOGLE_CLIENT_ID` và `GOOGLE_CLIENT_SECRET` riêng từ Google Cloud Console.

1. Trong [Google Cloud Console](https://console.cloud.google.com/apis/credentials), tạo project và cấu hình OAuth consent screen.
2. Tạo OAuth Client ID loại **Web application**.
3. Với máy local, thêm:
   - Authorized JavaScript origin: `http://localhost:8000`
   - Authorized redirect URI: `http://localhost:8000/api/auth/google/callback`
4. Sao chép `.env.example` thành `.env`, rồi điền:

```dotenv
APP_BASE_URL=http://localhost:8000
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
SESSION_SECRET=thay-bang-chuoi-ngau-nhien-dai-it-nhat-32-ky-tu
ENABLE_DEMO_LOGIN=true
```

Tạo `SESSION_SECRET` an toàn bằng:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

5. Khởi động lại backend và luôn truy cập đúng `http://localhost:8000`; không đổi sang `127.0.0.1` giữa luồng đăng nhập vì cookie OAuth gắn với hostname.

Khi triển khai thật, dùng domain HTTPS, đặt callback chính xác là `https://TEN-MIEN/api/auth/google/callback`, đồng thời đặt:

```dotenv
APP_ENV=production
APP_BASE_URL=https://TEN-MIEN
ENABLE_DEMO_LOGIN=false
```

Không commit `.env`, Google Client Secret, `SESSION_SECRET` hoặc API key. Nút Google tự bị vô hiệu hóa nếu server chưa có đủ thông tin OAuth.

## Kết nối Neon PostgreSQL

Tạo database Neon, rồi đặt trong `.env`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

Ứng dụng tự chuẩn hóa URL cho `asyncpg` và tạo năm bảng `users`, `login_sessions`, `assessments`, `feedback`, `medical_records`. Muốn dùng PostgreSQL local:

```powershell
docker compose up -d postgres
```

Sau đó đặt `DATABASE_URL=postgresql://healthpredict:healthpredict@localhost:5432/healthpredict`.

## Thuật toán ba tầng

1. **PGRS:** tổng gánh nặng bệnh F1/F2 theo bệnh và khoảng cách thế hệ, chuẩn hóa bằng đường cong bão hòa. Đây là điểm phả hệ giải thích được, không phải Polygenic Risk Score từ xét nghiệm gene.
2. **BRS:** tuổi, BMI, hút thuốc, vận động và bệnh đã được chẩn đoán.
3. **Sinh hiệu:** độ lệch khỏi khoảng tham chiếu demo và hệ số biến thiên của tối đa 60 mẫu đã lọc.
4. **Kết hợp:** `((1 + PGRS/100) × (1 + BRS/100) × (1 + Vitals/100) - 1) / 7 × 100`.
5. **Ngưỡng động:** PGRS cao làm ngưỡng chú ý/cảnh báo thấp hơn. SpO₂ dưới 90% hoặc huyết áp từ 180/120 trở lên luôn ghi đè điểm tổng.

AI chỉ diễn giải kết quả đã khóa. Nếu thiếu API key, người dùng vẫn nhận lời khuyên theo quy tắc.

## Bật trợ lý Google Gemini

Chỉ đặt khóa ở file `.env` phía backend; không chèn vào HTML/JavaScript và không gửi `.env` cho người khác:

```dotenv
AI_PROVIDER=google
GOOGLE_AI_API_KEY=your-google-ai-studio-key
GOOGLE_AI_MODEL=gemini-3.6-flash
```

`ai_service.py` gọi Gemini API từ backend, yêu cầu đầu ra JSON theo schema, timeout 45 giây và fallback an toàn. Nếu AI lỗi, thuật toán nguy cơ ba tầng vẫn hoạt động bằng bộ quy tắc. Hồ sơ chỉ được gửi để diễn giải khi người dùng đã bật đồng ý AI trong hồ sơ.

Với ảnh hồ sơ sức khỏe, ứng dụng chỉ nhận JPG/PNG/WebP tối đa 8 MB, kiểm tra chữ ký tệp, yêu cầu đồng ý riêng cho từng lần phân tích và không ghi ảnh vào cơ sở dữ liệu hay kho tệp ứng dụng. Ảnh được gửi đến Google Gemini cho lần phân tích đó; file tạm phía GeneSense được đóng ngay sau khi đọc. AI chỉ trích xuất nội dung nhìn thấy, không chẩn đoán. Kết quả được hiển thị để người dùng đối chiếu trước khi gọi API lưu. Chỉ JSON đã xác nhận được lưu theo `user_id`; người dùng có thể xóa từng bản ghi.

Model khả dụng phụ thuộc tài khoản Google AI Studio. Nếu Google thay model, gọi API danh sách model hoặc cập nhật `GOOGLE_AI_MODEL`. Có thể chuyển lại OpenAI bằng `AI_PROVIDER=openai` và các biến `OPENAI_*` trong `.env.example`.

## Web Bluetooth

| Chỉ số | Service | Characteristic |
|---|---:|---:|
| Nhịp tim | `0x180D` | `0x2A37` |
| Huyết áp | `0x1810` | `0x2A35` |
| Pulse Oximeter | `0x1822` | `0x2A5F` |
| Glucose | `0x1808` | `0x2A18` |

- Web Bluetooth cần HTTPS hoặc localhost và thao tác bấm kết nối của người dùng.
- iOS Safari chưa hỗ trợ trực tiếp; vẫn có thể nhập thủ công. Mobile app production nên dùng BLE native.
- Thiết bị dùng UUID riêng của hãng cần parser theo SDK chính thức.
- Mỗi luồng đo đi qua `MovingAverage(5)`; dữ liệu BLE cũ quá 30 giây không được dùng cho lần đánh giá mới.

## API chính

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/auth/config` | Trạng thái Google/demo |
| `GET` | `/api/auth/google` | Bắt đầu đăng nhập Google |
| `GET` | `/api/auth/me` | Tài khoản hiện tại |
| `POST` | `/api/auth/logout` | Thu hồi phiên hiện tại |
| `GET/PUT` | `/api/profile` | Đọc/cập nhật hồ sơ sức khỏe |
| `POST` | `/api/assessments` | Tính và lưu kết quả của tài khoản |
| `GET` | `/api/assessments` | Lịch sử của tài khoản |
| `GET` | `/api/assessments/{id}` | Chi tiết thuộc tài khoản |
| `POST` | `/api/feedback` | Lưu phản hồi thuộc tài khoản |
| `POST` | `/api/medical-records/analyze` | Phân tích ảnh trong bộ nhớ, chưa lưu |
| `GET/POST` | `/api/medical-records` | Xem hoặc lưu JSON đã xác nhận |
| `DELETE` | `/api/medical-records/{id}` | Xóa bản ghi thuộc tài khoản |

Các API thay đổi dữ liệu yêu cầu cookie phiên cùng header `X-Requested-With`; dữ liệu được giới hạn theo `user_id` ở backend.

## Kiểm thử

```powershell
python -m pytest backend\tests -q
```

Bộ test gồm thuật toán nguy cơ, trường hợp cấp cứu, tách dữ liệu giữa tài khoản, thu hồi/timeout phiên, validation hồ sơ, migration dữ liệu cũ và callback Google mô phỏng. Google thật vẫn cần kiểm thử trên OAuth Client/domain của bạn.

## Trước khi dùng thực tế

- Hiệu chuẩn bằng dữ liệu lâm sàng, đánh giá sai lệch theo nhóm dân số và có người chịu trách nhiệm chuyên môn.
- Bổ sung Alembic, rate limiting, audit log, monitoring, backup, mã hóa dữ liệu nhạy cảm và quản trị khóa bằng secret manager.
- Xây quy trình tải xuống/xóa tài khoản, retention policy, điều khoản và chính sách riêng tư phù hợp pháp luật nơi triển khai.
- Kiểm thử bảo mật độc lập và tích hợp riêng với từng model thiết bị BLE; không suy đoán định dạng byte.
- Xác nhận yêu cầu về thiết bị y tế và bảo vệ dữ liệu trước khi phát hành cho người dùng thật.
