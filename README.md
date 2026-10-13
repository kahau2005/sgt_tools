# GB Submit - Check Link Facebook

Ứng dụng desktop Python/Tkinter dùng để đăng nhập Odoo, tải lịch sử bài đăng từ module `sgt_gb_submit`, kiểm tra link Facebook bằng LibreWolf + Selenium và cập nhật kết quả về Odoo.

Ứng dụng chạy trên Windows, không cần Flask, Redis hoặc Celery.

## 1. Chức năng chính

- Đăng nhập Odoo qua XML-RPC.
- Đọc dữ liệu từ model `sgt.social.publish.history`.
- Hiển thị bài đăng theo người đăng.
- Lọc theo ngày, nội dung/tên và trạng thái.
- Kiểm tra link Facebook bằng LibreWolf.
- Chạy nhiều trình duyệt song song.
- Cho phép chọn thư mục LibreWolf riêng của từng người dùng trên Dashboard.
- Chọn kích thước batch: kiểm tra xong một batch rồi mới cập nhật batch đó lên Odoo.
- Chọn thời gian timeout trên giao diện, mặc định 10 giây.
- Khi timeout, reload trên chính trình duyệt đang mở bài viết, tối đa 3 lượt.
- Hiển thị số lần reload trong cột `DETAIL`.
- Check lại toàn bộ dòng timeout hoặc check lại từng dòng.
- Cập nhật bài chết thành `failed`.
- Khi bài đã `failed` kiểm tra sống lại, cập nhật thành `published` và xóa detail lỗi cũ.
- Không tự động đổi trạng thái `sgt.social.group.link`.

## 2. Yêu cầu môi trường

### Chạy source

- Windows 10/11.
- Python 3.10 trở lên.
- LibreWolf portable.
- Tài khoản Odoo có quyền XML-RPC.
- Người dùng LibreWolf đã đăng nhập Facebook trong profile được cấu hình.

### Chạy bản EXE

Không cần cài Python hoặc Selenium. Sử dụng thư mục:

```text
dist\GBSubmit\
```

Phải giữ nguyên toàn bộ thư mục `_internal` cùng với `GBSubmit.exe`. Không chỉ copy riêng file `.exe`.

## 3. Cấu trúc project

```text
Sub_Check\
├── main.py                         # Entry point
├── gui\
│   ├── login_window.py             # Form đăng nhập Odoo
│   └── dashboard_window.py         # Dashboard và worker check
├── services\
│   ├── odoo_client.py              # XML-RPC Odoo
│   ├── link_checker.py             # Selenium + LibreWolf
│   └── credential_store.py         # Lưu credential bảo mật trên Windows
├── requirements.txt                # Python dependencies
├── run_app.bat                     # Chạy source
├── build_exe.bat                   # Build bản EXE
├── build_exe.ps1                   # Logic build PyInstaller
├── dist\GBSubmit\                  # Bản EXE sau khi build
└── PLAN.md                         # Kế hoạch và kiến trúc ban đầu
```

## 4. Cấu hình LibreWolf

Hai tool Check Post và Check Group không cần file `.env` để cấu hình LibreWolf.
Người dùng chọn thư mục LibreWolf trực tiếp trên giao diện trước khi chạy check;
nếu chưa chọn, ứng dụng sẽ yêu cầu chọn thư mục. `geckodriver.exe` được lấy cạnh
ứng dụng khi chạy source và được đóng gói cùng bản EXE.

Profile LibreWolf phải:

1. Tồn tại đúng đường dẫn.
2. Có phiên Facebook đã đăng nhập.
3. Không đang bị một LibreWolf khác sử dụng khi bắt đầu chạy nhiều browser.

Nếu mỗi người dùng có một thư mục LibreWolf riêng, không cần sửa code. Trên Dashboard,
nhấn **Chọn thư mục LibreWolf** và chọn thư mục chứa thư mục phiên bản, ví dụ:

```text
LSM6856_SR0302_Doris@SGT(Thanh Khánh CN)\
└── librewolf-148.0-1\
    ├── LibreWolf\librewolf.exe
    └── Profiles\Default\
```

Ứng dụng cũng chấp nhận chọn trực tiếp thư mục `librewolf-148.0-1`.

Không đưa password Odoo, token hoặc file credential riêng vào Git.

## 5. Cài dependency và chạy source

Mở PowerShell tại thư mục project:

```powershell
cd C:\HAU\Internship\Task\Sub_Check\Sub_Check
python -m venv ..\.venv
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe main.py
```

Hoặc chạy:

```text
run_app.bat
```

`run_app.bat` hiện đang dùng Python 3.10 tại:

```text
C:\Users\pmhau\AppData\Local\Programs\Python\Python310\python.exe
```

Nếu máy khác dùng Python ở vị trí khác, sửa biến `PYTHON_EXE` trong `run_app.bat`, hoặc chạy trực tiếp bằng lệnh PowerShell ở trên.

## 6. Sử dụng ứng dụng

### Đăng nhập

Nhập:

- Odoo URL.
- Database.
- User/login.
- Password.

Nhấn **Connect**. Ứng dụng gọi `common.authenticate` qua XML-RPC trước khi mở Dashboard.

Credential được lưu cục bộ bằng Windows DPAPI nếu người dùng chọn ghi nhớ đăng nhập. Không dùng file này để chia sẻ credential sang máy khác.

### Dashboard

Các nhóm điều khiển:

- **Lọc dữ liệu:** lọc danh sách đang hiển thị.
- **Phạm vi kiểm tra:** chọn ngày bắt đầu và kết thúc của các bài cần check.
- **Chạy kiểm tra:**
  - `Trình duyệt`: số LibreWolf chạy song song, từ 1 đến 8.
  - `Batch`: số bài xử lý trong một đợt, từ 1 đến 500.
  - `Timeout (giây)`: thời gian chờ mỗi lượt, mặc định 10 giây.
  - `Hiện trình duyệt`: bật để nhìn thấy các cửa sổ LibreWolf.
- **Thao tác:** Refresh, Stop, Check lại timeout.
- **Tìm kiếm & lọc trạng thái:** lọc cả trạng thái Odoo và trạng thái check.

### Quy trình batch

Ví dụ `Batch = 10`:

1. Lấy 10 bài.
2. Kiểm tra 10 bài bằng số browser đã chọn.
3. Chờ cả 10 bài hoàn tất.
4. Gửi kết quả của 10 bài lên Odoo.
5. Tiếp tục batch kế tiếp.

### Xử lý timeout

Với timeout mặc định 10 giây:

1. Mở bài bằng browser hiện tại.
2. Nếu không có kết quả, reload chính browser đó.
3. Thử tối đa 3 lượt.
4. Nếu cả 3 lượt timeout, detail hiển thị `TIMEOUT_KHONG_XAC_DINH` và số lần reload.

Có thể chọn `Check lại timeout` hoặc bấm `Check lại` tại cột cuối của từng dòng.

Sau khi bài sống được đồng bộ thành công, detail sẽ hiển thị:

```text
OK
```

## 7. Quyền Odoo cần có

Tài khoản đăng nhập cần quyền đọc model:

```text
sgt.social.publish.history
```

Để cập nhật trạng thái lịch sử, tài khoản cần quyền ghi phù hợp với module `sgt_gb_submit`, thường là quyền quản lý tài liệu hoặc quyền được module cấp riêng.

Ứng dụng cập nhật:

```text
sgt.social.publish.history.status
sgt.social.publish.history.detail
```

Ứng dụng hiện không tự động cập nhật trạng thái của:

```text
sgt.social.group.link
```

## 8. Build bản EXE

Trước khi build, đóng toàn bộ các tiến trình GBSubmit, LibreWolf và geckodriver đang chạy.

Chạy:

```text
build_exe.bat
```

Script chạy PyInstaller ở chế độ `onedir` và tạo bản chạy tại:

```text
dist\GBSubmit\GBSubmit.exe
```

Khi phát hành, giữ toàn bộ thư mục `dist\GBSubmit`; ứng dụng cần thư mục `_internal`.

### Tạo installer

Sau khi build EXE, chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_installer.ps1
```

Installer được tạo tại `dist\GBSubmit-Setup.exe`. Khi chạy, nó cài ứng dụng cho
người dùng hiện tại vào `%LOCALAPPDATA%\Programs\GBSubmit` và tạo shortcut Desktop
và Start Menu.

## 9. Lỗi thường gặp

### Không tìm thấy LibreWolf

Chọn lại thư mục LibreWolf trên màn hình Check Post hoặc Check Group. Thư mục cần
chứa `LibreWolf\librewolf.exe` và `Profiles\Default`. Khi chạy source, kiểm tra
`geckodriver.exe` nằm cạnh ứng dụng.

### Facebook yêu cầu đăng nhập hoặc checkpoint

Mở LibreWolf bằng profile đã cấu hình, đăng nhập Facebook và xử lý checkpoint thủ công, sau đó chạy lại ứng dụng.

### Không cập nhật được Odoo

Kiểm tra:

- URL/database/user/password.
- Quyền ghi trên model `sgt.social.publish.history`.
- Kết nối mạng đến Odoo.
- Detail lỗi trong Dashboard.

### Build báo file đang được sử dụng

Đóng ứng dụng và toàn bộ LibreWolf/geckodriver. Có thể kiểm tra bằng PowerShell:

```powershell
Get-Process -Name GBSubmit,geckodriver,librewolf -ErrorAction SilentlyContinue
```

Sau đó chạy lại `build_exe.bat`.

### EXE không chạy được sau khi copy

Không copy riêng `GBSubmit.exe`. Hãy copy cả thư mục:

```text
dist\GBSubmit\
```

## 10. Kiểm tra nhanh trước khi bàn giao

1. Chạy được màn hình đăng nhập.
2. Đăng nhập Odoo thành công.
3. Refresh tải được lịch sử bài đăng.
4. LibreWolf mở đúng profile Facebook.
5. Chạy thử với `Trình duyệt = 1`, `Batch = 1`, `Timeout = 10`.
6. Kiểm tra bài sống, bài chết và bài timeout.
7. Kiểm tra nút `Check lại timeout`.
8. Kiểm tra nút `Check lại` ở từng dòng.
9. Kiểm tra trạng thái và detail trên Odoo.
10. Chỉ bàn giao cả thư mục `dist\GBSubmit`.
