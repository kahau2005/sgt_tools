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
- Có công cụ **Check Group** riêng để tải Pool/Blacklist theo Project và kiểm tra thông tin group.

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
│   ├── mode_selection_window.py    # Chọn Check Post hoặc Check Group
│   ├── dashboard_window.py         # Dashboard Check Post
│   └── group_check_window.py       # Dashboard Check Group
├── services\
│   ├── odoo_client.py              # XML-RPC Odoo
│   ├── link_checker.py             # Selenium + LibreWolf
│   └── credential_store.py         # Lưu credential bảo mật trên Windows
├── tests\
│   └── test_librewolf_selection.py  # Test tự động chọn LibreWolf
├── sgt_gb_submit\                   # Odoo addon liên quan
├── requirements.txt                # Python dependencies
├── run_app.bat                     # Chạy source
├── build_exe.bat                   # Build bản EXE
├── build_exe.ps1                   # Logic build PyInstaller
├── build_installer.ps1              # Build bộ cài Windows
├── install_payload.ps1              # Cài ứng dụng và tạo shortcut
├── dist\GBSubmit\                  # Bản EXE sau khi build
└── dist\GBSubmit-Setup.exe          # Installer sau khi build
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
- **Thao tác:** Refresh, Stop, Check lại lỗi / timeout.
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

Có thể chọn `Check lại lỗi / timeout` hoặc bấm `Check lại` tại cột cuối của từng dòng (hoặc chuột phải chọn `Check lại dòng đã chọn`).

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
7. Kiểm tra nút `Check lại lỗi / timeout`.
8. Kiểm tra nút `Check lại` ở từng dòng.
9. Kiểm tra trạng thái và detail trên Odoo.
10. Bàn giao `dist\GBSubmit-Setup.exe` hoặc cả thư mục `dist\GBSubmit`.

## 11. Kiến trúc và luồng xử lý

Ứng dụng gồm hai cửa sổ kiểm tra riêng sau khi đăng nhập Odoo thành công:

- **Check Post Facebook** tải lịch sử bài đăng từ `sgt.social.publish.history`,
  lọc ngày và chạy Selenium ở worker nền.
- **Check Group** tải danh sách Project, sau đó tải Pool hoặc Blacklist của
  Project được chọn từ `sgt.social.group.link`.

Tkinter/ttk dựng giao diện. Thread và queue xử lý tác vụ nền, truyền trạng thái
và kết quả về giao diện. `OdooClient` giao tiếp với Odoo qua XML-RPC;
`LibreWolfChecker` điều khiển LibreWolf bằng Selenium. Không chạy Selenium hoặc
các lời gọi Odoo dài trực tiếp trong luồng giao diện.

Luồng Check Post:

1. Đăng nhập Odoo bằng URL, database, user và password.
2. Tải lịch sử bài đăng và áp dụng bộ lọc ngày/trạng thái.
3. Chia danh sách thành batch và kiểm tra bằng profile LibreWolf đã chọn.
4. Hiển thị tiến độ, trạng thái và lý do trên Dashboard.
5. Cập nhật trạng thái bài đăng về Odoo theo kết quả hiện tại của checker.

Luồng Check Group:

1. Tải danh sách Project khi mở màn hình Check Group.
2. Sau khi chọn Project và tab Pool/Blacklist, tải đúng danh sách đó.
3. Kiểm tra từng group hoặc các dòng trong danh sách bằng LibreWolf.
4. Cập nhật thông tin scrape theo batch lên Odoo; không ghi đè trường quản lý
   `status`.

## 12. Check Group

Check Group dùng các model và trường Odoo sau:

| Dữ liệu | Model/trường |
|---|---|
| Project | `sgt.social.destination`: `id`, `name` |
| Group link | `sgt.social.group.link`: `project_id`, `link_type`, `group_url`, `alt_url`, `group_name`, `member_count`, `group_type`, `info_updated_at`, `status` |
| Phân loại | `link_type = pool` hoặc `link_type = blacklist` |

Các link được sắp xếp theo `create_date desc, id desc`; client giới hạn mỗi lần
tải còn 200 bản ghi. Loại `new` chưa nằm trong phạm vi hiện tại.

Bảng hiển thị Group URL, Alt URL, Group Name, Members, Type, Information Updated
On, Status và Check Status. Nút **Tải lại** chỉ tải lại Project/tab đang chọn.
Nút **Check lại** trên một dòng chỉ chạy check cho group link đó. Khi check,
tool thử `group_url` trước và dùng `alt_url` làm phương án dự phòng; có thể lấy
URL thân thiện mới cùng thông tin group từ trang About.

Check Status có thể là `ALIVE`, `PARTIAL`, `DEAD`, `ERROR`, `TIMEOUT` hoặc
`STOPPED`. Kết quả Check Status hiện được giữ trong giao diện trong phiên làm
việc; Odoo được cập nhật các trường scrape được hỗ trợ (`alt_url`, `group_name`,
`member_count`, `group_type`). Trường `status` quản lý trên Odoo được giữ nguyên.

Project và group link được tải bất đồng bộ. Request cũ không được phép ghi đè
lựa chọn Project/tab mới hơn. Nhiều trình duyệt không dùng đồng thời chung một
profile vật lý; tool tạo bản sao profile tạm cho worker song song.

## 13. Quyền riêng tư Facebook và diễn giải kết quả

LibreWolf kiểm tra bằng tài khoản đã đăng nhập trong profile người dùng chọn.
Facebook có thể giới hạn nội dung theo đối tượng của bài hoặc quyền thành viên
nhóm. Vì vậy, tác giả nhìn thấy bài không đảm bảo tài khoản checker cũng xem được.

Ở Check Post, trạng thái `DEAD` hiện được đồng bộ thành `failed` trên Odoo.
Checker hiện chưa phân biệt chắc chắn bài đã bị xóa với bài còn tồn tại nhưng
không xem được bằng tài khoản kiểm tra. Nếu bài vẫn hiển thị cho tác giả, hãy
xác minh quyền xem của profile LibreWolf trước khi coi kết quả `DEAD` là bằng
chứng bài đã bị xóa.

## 14. An toàn và xử lý lỗi

- Password Odoo không được ghi vào log hoặc `.env`; credential phiên giữ trong
  bộ nhớ. Nếu bật ghi nhớ đăng nhập, ứng dụng dùng Windows DPAPI.
- Không đưa token hoặc credential riêng vào Git.
- Lỗi XML-RPC, Selenium, profile hoặc timeout phải hiện trong log/trạng thái;
  không tự coi lỗi kiểm tra là thành công.
- Nếu cập nhật Odoo thất bại, xem thông báo lỗi trên Dashboard trước khi chạy lại.
- Khi đóng ứng dụng hoặc cần dừng check, dùng nút **Stop** để yêu cầu worker dừng.

## 15. Kiểm thử tự động

Các testcase nằm trong `tests/test_librewolf_selection.py`, dùng `unittest` và
không cần Odoo, Facebook, LibreWolf đang mở hoặc màn hình đồ họa.

| Mã | Tình huống | Kết quả mong đợi |
|---|---|---|
| LW-01 | Chưa chọn thư mục khi khởi tạo checker | Báo lỗi rõ ràng; không đọc `.env`. |
| LW-02 | Chọn thư mục cha chứa thư mục phiên bản LibreWolf | Tìm đúng `librewolf.exe` và `Profiles/Default`. |
| LW-03 | Check Post chạy khi chưa chọn thư mục | Hiện cảnh báo; không chạy worker. |
| LW-04 | Check Group chạy khi chưa chọn thư mục | Hiện cảnh báo và không cho chạy. |
| LW-05 | Check Group đã có thư mục | Cho phép chạy mà không hiện cảnh báo. |

Chạy test từ thư mục project:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Kết quả ngày **2026-10-13**: **5/5 testcase đạt** (`Ran 5 tests in 0.032s`, `OK`).

## 16. Hạng mục dự kiến chưa có trong ứng dụng

Thiết kế ban đầu có đề xuất SQLite để lưu lịch sử check/cấu hình, xuất CSV,
retry đồng bộ Odoo khi mất mạng, và lưu Check Status/chi tiết lỗi của Check Group
trên Odoo. Các hạng mục này chưa được triển khai trong ứng dụng hiện tại. Kết quả
Check Status của Check Group chỉ tồn tại trong giao diện trong lúc phiên làm việc
còn mở.
