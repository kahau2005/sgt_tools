# Kế hoạch chuyển đổi hệ thống Check Link sang ứng dụng Desktop Python & Odoo

## 1. Mục tiêu

Chuyển hệ thống check link hiện tại từ hướng Web App Flask sang ứng dụng chạy trực tiếp trên Windows bằng Python GUI dạng cửa sổ.

Ứng dụng desktop cần:

- Cho phép người dùng nhập thông tin kết nối Odoo.
- Xác thực tài khoản bằng XML-RPC.
- Lấy các bài đăng đã đăng thành công từ Odoo.
- Lọc dữ liệu theo khoảng thời gian.
- Chạy kiểm tra link Facebook bằng LibreWolf + Selenium ở tiến trình nền.
- Hiển thị tiến độ, log và kết quả ngay trên cửa sổ ứng dụng.
- Cập nhật trạng thái bài đăng/link group bị lỗi ngược lại Odoo.
- Không cần Flask, trình duyệt web giao diện, Celery hoặc Redis.

## 2. Kiến trúc ứng dụng mới

### 2.1. Công nghệ

- **Python 3**
- **Tkinter/ttk**: giao diện cửa sổ form, có sẵn trong Python.
- **Threading hoặc ThreadPoolExecutor**: chạy tác vụ check nền, không làm treo giao diện.
- **Queue**: truyền log, tiến độ và kết quả từ worker về GUI.
- **Selenium WebDriver**: điều khiển LibreWolf.
- **XML-RPC**: đăng nhập, đọc và ghi dữ liệu Odoo.
- **SQLite**: lưu cache lịch sử check, cấu hình cục bộ tùy chọn và log.
- **Cấu hình LibreWolf**: người dùng chọn thư mục trên giao diện; không cần `.env`.

### 2.2. Luồng module dự kiến

```text
main.py
├── gui/
│   ├── login_window.py       # Form kết nối Odoo
│   ├── dashboard_window.py   # Bảng dữ liệu, bộ lọc, nút thao tác
│   └── widgets.py            # Progress bar, log viewer, dialogs
├── services/
│   ├── odoo_client.py        # XML-RPC authenticate/search/read/write
│   ├── link_checker.py       # Logic Selenium/LibreWolf hiện có
│   ├── check_worker.py       # Worker chạy nền
│   └── cache_service.py      # SQLite
├── models/
│   └── data_models.py        # Dataclass cho credential, post, result
├── config.py                 # Đọc và kiểm tra cấu hình
└── storage/
    └── app.db                # SQLite, tạo tự động khi chạy
```

Có thể bắt đầu bằng ít file hơn, sau đó tách module khi chức năng ổn định. Logic `parse_link`, `is_viewable` và cấu hình LibreWolf trong `Sub_check_linkGB_TTS_v3.py` cần được tái sử dụng hoặc chuyển dần vào `services/link_checker.py`.

## 3. Luồng hoạt động

### Bước 1: Mở ứng dụng và đăng nhập Odoo

1. Chạy `python main.py`.
2. Hiển thị cửa sổ Login.
3. Form gồm:
   - Odoo URL.
   - Database name.
   - User/login hoặc email.
   - Password.
4. Khi bấm **Connect**:
   - Chuẩn hóa Odoo URL.
   - Gọi `common.authenticate` qua XML-RPC.
   - Nếu thất bại, hiển thị lỗi rõ ràng trên form.
   - Nếu thành công, lưu credential trong bộ nhớ phiên hiện tại.
5. Không ghi password dạng rõ vào file log hoặc SQLite. Nếu cần lưu cho lần chạy sau, chỉ lưu URL/database/user và yêu cầu nhập lại password.

### Bước 2: Tải dữ liệu từ Odoo

Sau khi đăng nhập thành công, mở Dashboard và gọi model:

```text
sgt.social.publish.history
```

Module `sgt_gb_submit` dùng trạng thái thành công là:

```text
status = published
```

Các trường dự kiến:

- `id`
- `external_post_url`
- `status`
- `posted_at`
- `group_link_id`
- `content_title`
- `project_id`
- `is_free_group`
- `free_group_url`
- `external_post_id`
- `error_message`

Dashboard hiển thị các bản ghi trong bảng, có trạng thái tải dữ liệu và thông báo lỗi nếu Odoo không phản hồi.

### Bước 3: Lọc dữ liệu và tạo phiên check

Dashboard có:

- Ngày bắt đầu.
- Ngày kết thúc.
- Nút **Load/Refresh**.
- Nút **Check Again**.
- Nút **Stop** nếu worker đang chạy.

Khi bấm **Check Again**:

1. Kiểm tra ngày hợp lệ và ngày bắt đầu không lớn hơn ngày kết thúc.
2. Lọc các bài đăng theo `posted_at`.
3. Bỏ qua bản ghi không có URL hợp lệ.
4. Hiển thị số lượng link sẽ kiểm tra.
5. Hỏi xác nhận trước khi chạy.
6. Gửi danh sách công việc vào worker nền.

### Bước 4: Worker kiểm tra LibreWolf

Worker thực hiện tuần tự hoặc theo số lượng worker được cấu hình:

1. Khởi chạy Selenium với LibreWolf binary, profile và geckodriver từ `.env`.
2. Phân tích URL bằng logic hiện tại:
   - Link bài viết/permalink.
   - Link có post ID trong query.
   - Link chỉ trỏ đến group.
   - Link không xác định.
3. Với link hợp lệ, gọi logic `is_viewable()` để kiểm tra DOM.
4. Ghi kết quả, lý do và thời gian kiểm tra vào queue để GUI cập nhật.
5. Đóng driver an toàn khi hoàn tất hoặc khi người dùng bấm Stop.

Không chạy Selenium trực tiếp trong main GUI thread để cửa sổ luôn phản hồi.

### Bước 5: Cập nhật trạng thái Odoo

Sau mỗi kết quả hoặc theo batch nhỏ:

- Nếu bài viết không còn tồn tại:

```python
{"status": "failed"}
```

ghi vào `sgt.social.publish.history`.

- Nếu bài viết còn tồn tại: giữ `published`, chỉ lưu log/cache nội bộ.
- Nếu lỗi do group không còn khả dụng: cập nhật bản ghi tương ứng trong `sgt.social.group.link`:

```python
{"status": "unavailable"}
```

Lưu ý quyền Odoo của module: đọc lịch sử/group link được cấp cho người dùng nội bộ, nhưng cập nhật `sgt.social.publish.history.status` cần nhóm `All Documents` hoặc Manager; cập nhật group link cần nhóm `GB Submit Manager`.

Nếu cập nhật Odoo thất bại, phải ghi rõ lỗi vào log và đánh dấu kết quả là `update_failed`, không được hiển thị như đã cập nhật thành công.

### Bước 6: Hiển thị kết quả

Dashboard cần hiển thị:

- Tổng số link.
- Số đã xử lý.
- Số link sống.
- Số link chết.
- Số lỗi kiểm tra.
- Số lỗi cập nhật Odoo.
- Progress bar.
- Log theo thời gian thực.
- Bảng kết quả có thể lọc theo trạng thái.

Sau khi hoàn tất, cho phép xuất kết quả ra CSV hoặc xem lại lịch sử trong SQLite.

## 4. Giao diện cửa sổ

### 4.1. Login Window

- Tiêu đề ứng dụng.
- Header màu tím theo giao diện tham khảo.
- Card/form trắng bo góc nếu dùng `ttk` theme hoặc custom frame.
- Ô nhập Odoo URL, database, user và password.
- Nút **Connect**.
- Nhãn trạng thái kết nối.
- Checkbox tùy chọn ghi nhớ URL/database/user, không ghi nhớ password dạng rõ.

### 4.2. Dashboard Window

- Khu vực thông tin user/Odoo đang kết nối.
- Bộ lọc ngày.
- Nút Refresh.
- Nút Check Again.
- Nút Stop.
- Bảng dữ liệu bài đăng.
- Progress bar.
- Khung log có scrollbar.
- Dialog xác nhận khi cập nhật hàng loạt.

## 5. Cấu hình `.env`

Cấu hình hiện tại cần được chuẩn hóa để dùng đường dẫn tương đối hoặc đường dẫn Windows hợp lệ:

```env
LIBREWOLF_CORE=...
LIBREWOLF_PROFILE_PATH=...
GECKODRIVER_PATH=...

# Tùy chọn
SQLITE_PATH=app.db
HEADLESS=true
PAGE_LOAD_TIMEOUT=30
VERDICT_TIMEOUT=15
MAX_WORKERS=1
```

Không đưa password Odoo vào `.env` hoặc source code.

## 6. SQLite cache

Các bảng dự kiến:

### `check_history`

- `id`
- `odoo_record_id`
- `external_post_url`
- `group_link_id`
- `posted_at`
- `checked_at`
- `result`
- `reason`
- `odoo_update_status`

### `app_settings`

- `key`
- `value`

Chỉ lưu các thiết lập không nhạy cảm. Credential phiên làm việc giữ trong RAM và xóa khi đóng ứng dụng.

## 7. Xử lý lỗi và an toàn

- Kiểm tra đầy đủ các biến đường dẫn trước khi khởi chạy Selenium.
- Kiểm tra Odoo URL, database, user và password trước khi authenticate.
- Timeout rõ ràng cho XML-RPC, tải trang và xác định trạng thái DOM.
- Không nuốt exception; ghi lỗi vào log GUI và file log nếu có.
- Khi đóng cửa sổ, yêu cầu dừng worker rồi mới thoát.
- Không để nhiều phiên Selenium dùng chung một profile LibreWolf cùng lúc.
- Không log password, XML-RPC credential hoặc token.
- Nếu mất mạng trong khi check, giữ kết quả local và cho phép retry cập nhật Odoo.

## 8. Lộ trình triển khai

### Giai đoạn 1: Tách logic hiện có

1. Xác định các hàm Selenium/LibreWolf cần tái sử dụng.
2. Tách cấu hình, parse link và `is_viewable()` khỏi script hiện tại.
3. Bổ sung kiểu dữ liệu cho post và check result.
4. Kiểm tra lại đường dẫn LibreWolf/profile/geckodriver trên máy hiện tại.

### Giai đoạn 2: Xây dựng Odoo client

1. Tạo `OdooClient`.
2. Implement `authenticate`.
3. Implement `search_read` cho `sgt.social.publish.history` với domain `status = published`.
4. Implement `write` cho publish history và group link.
5. Thêm timeout, lỗi kết nối và kiểm tra quyền truy cập.

### Giai đoạn 3: Xây dựng GUI Login

1. Tạo cửa sổ Login bằng Tkinter/ttk.
2. Kết nối Odoo trong background thread để GUI không bị treo.
3. Chỉ mở Dashboard khi authenticate thành công.
4. Thêm validation và thông báo lỗi.

### Giai đoạn 4: Xây dựng Dashboard

1. Tạo bảng dữ liệu và date range filter.
2. Tải dữ liệu Odoo và hiển thị trên bảng.
3. Thêm nút Refresh, Check Again và Stop.
4. Thêm progress bar và log viewer.

### Giai đoạn 5: Worker check link

1. Tạo worker dùng `threading`/`ThreadPoolExecutor`.
2. Đưa logic LibreWolf vào worker.
3. Gửi progress/result qua `queue.Queue`.
4. Đảm bảo Stop đóng driver và kết thúc an toàn.

### Giai đoạn 6: Đồng bộ kết quả và cache

1. Cập nhật Odoo sau từng kết quả hoặc theo batch.
2. Ghi lịch sử vào SQLite.
3. Xử lý retry khi Odoo tạm thời mất kết nối.
4. Thêm export CSV nếu cần.

### Giai đoạn 7: Kiểm thử và đóng gói

1. Test đăng nhập đúng/sai.
2. Test Odoo không kết nối được.
3. Test lọc khoảng ngày.
4. Test link sống, link chết, link group-only và URL lỗi.
5. Test Stop khi đang chạy.
6. Test cập nhật `failed` và `unavailable`.
7. Chạy kiểm tra trên Windows thực tế với LibreWolf profile hiện có.
8. Đóng gói bằng PyInstaller thành file `.exe` nếu cần.

## 9. Tiêu chí hoàn thành

- Ứng dụng chạy bằng một lệnh `python main.py` hoặc file `.exe`.
- Người dùng đăng nhập Odoo thành công từ cửa sổ form.
- Dashboard chỉ hiển thị bài đăng `published`.
- Có thể lọc theo ngày và chạy check nền.
- Giao diện không bị treo trong lúc Selenium hoạt động.
- Link chết được cập nhật thành `failed` trên Odoo.
- Group không khả dụng được cập nhật thành `unavailable`.
- Có log/progress và kết quả lỗi rõ ràng.
- Không cần Flask, web browser UI, Celery hoặc Redis.
- Password không bị lưu hoặc ghi log dưới dạng rõ.

---

# Kế hoạch phát triển tính năng Check Group

## 1. Phạm vi

Phát triển màn hình **Check Group** riêng, không làm thay đổi luồng **Check Post Facebook** hiện tại.

Luồng sử dụng:

1. Đăng nhập Odoo.
2. Chọn **Check Group** ở trang chọn tool.
3. Tải danh sách Project.
4. Người dùng chọn một Project.
5. Hiển thị hai lựa chọn **Pool** và **Blacklist**.
6. Người dùng chọn **Pool** hoặc **Blacklist**.
7. Chỉ sau khi chọn Pool/Blacklist, tool mới tải và hiển thị group link tương ứng
   của Project đó.
8. Nút **Tải lại** tải lại danh sách đang được chọn.
9. Nút **Check lại** ở cuối từng dòng dùng để kiểm tra lại đúng group link của dòng đó.

Không tải toàn bộ group link của tất cả Project ngay khi mở màn hình.

## 2. Cấu trúc Odoo sử dụng

### Project

- Model: `sgt.social.destination`
- Trường cần đọc: `id`, `name`, `active`

### Group link

- Model: `sgt.social.group.link`
- Quan hệ Project: `project_id`
- Trường hiển thị:
  - `group_url` - Group URL
  - `alt_url` - Alt URL
  - `group_name` - Group Name
  - `member_count` - Members
  - `group_type` - Type
  - `info_updated_at` - Information Updated On
- Trường trạng thái quản lý:
  - `status` - Status hiện có trên Odoo, phải giữ nguyên
- Trường phân loại:
  - `link_type = pool` - Pool
  - `link_type = blacklist` - Blacklist

Danh sách `new` chưa nằm trong phạm vi giai đoạn đầu.

## 3. Thiết kế giao diện

Màn hình Check Group gồm:

- Tiêu đề `CHECK GROUP`
- Tài khoản Odoo đang đăng nhập
- Nút `← Chọn tool`
- Combobox chọn `Project`
- Hai tab `Pool` và `Blacklist`
- Nút `Tải lại` để tải lại danh sách hiện tại từ Odoo
- Tùy chọn số trình duyệt, Batch, hiện/ẩn trình duyệt và thư mục LibreWolf,
  dùng chung cơ chế với Check Post Facebook
- Thanh trạng thái, progress và nhật ký ở phía trên bảng
- Bảng group link

Bảng hiển thị:

| Tên hiển thị | Trường Odoo |
|---|---|
| Group URL | `group_url` |
| Alt URL | `alt_url` |
| Group Name | `group_name` |
| Members | `member_count` |
| Type | `group_type` |
| Information Updated On | `info_updated_at` |
| Status | `status` |
| Check Status | Kết quả check mới nhất của tool |
| Action | Nút `Check lại` cho từng group link |

Nút `Check lại` là nút riêng ở cột cuối của mỗi dòng, tương tự nút
kiểm tra lại một bài cụ thể trong màn hình Check Post Facebook. Nút này không
phải là nút tải lại danh sách.

`Status` là trạng thái quản lý đọc từ Odoo và không được thay đổi bởi kết quả
Selenium. `Check Status` là cột riêng để hiển thị kết quả kiểm tra của tool.

## 4. API cần thêm vào Odoo client

Thêm dataclass riêng cho dữ liệu group link, ví dụ `GroupLink`.

```python
list_group_projects() -> list[tuple[int, str]]
list_group_links(project_id: int, link_type: str) -> list[GroupLink]
batch_update_group_links(updates: list[dict]) -> list[int]
```

`list_group_projects()` dùng `search_read` trên `sgt.social.destination`, sắp xếp theo tên Project.

`batch_update_group_links()` phải gọi một method batch trên model Odoo trong một
lần XML-RPC. Không gọi `write()` riêng qua mạng cho từng group; Odoo xử lý từng
bản ghi phía server và trả về các ID đã cập nhật.

Client phải có fallback tạm thời về `write()` chuẩn nếu server chưa được
upgrade và chưa đăng ký method batch. Fallback này chỉ đảm bảo tương thích với
module cũ; sau khi upgrade `sgt_gb_submit`, client sẽ tự dùng đường batch.

`list_group_links()` dùng domain:

```python
[
    ("project_id", "=", project_id),
    ("link_type", "=", "pool" hoặc "blacklist"),
]
```

Sắp xếp giống module Odoo: `create_date desc, id desc`.

Chỉ chấp nhận `pool` và `blacklist`; giá trị khác phải báo lỗi rõ ràng.

`batch_update_group_links()` phải cập nhật theo ID group link và chỉ gửi các
field được module Odoo cho phép ghi. Payload không được chứa `status`, trừ khi
có một yêu cầu nghiệp vụ riêng được xác nhận sau này.

## 5. Tải dữ liệu bất đồng bộ

Các lời gọi XML-RPC chạy bằng thread để giao diện không bị treo.

Trạng thái cần hiển thị:

- Đang tải danh sách Project.
- Chọn Project để xem group link.
- Đang tải Pool hoặc Blacklist.
- Đã tải được bao nhiêu group link.
- Lỗi Odoo nếu request thất bại.

Dùng request ID hoặc cơ chế tương đương để response cũ không ghi đè lựa chọn mới khi người dùng đổi Project hoặc tab nhanh.

## 6. Luồng Selenium kiểm tra group

Tool dùng Selenium với LibreWolf và profile chung theo cùng cơ chế với Check
Post Facebook. Không tạo cơ chế đăng nhập hoặc profile riêng cho Check Group.

Với mỗi group link, quy trình là:

1. Mở `group_url` bằng LibreWolf.
2. Chờ trang group tải xong và xác định group Facebook hợp lệ.
3. Bấm/chuyển sang tab hoặc khu vực **Giới thiệu/About**.
4. Đọc URL hiện tại sau thao tác này. Facebook có thể đổi URL dạng ID sang URL
   thân thiện; URL mới hợp lệ được lưu vào `alt_url`.
5. Lấy các thông tin thực tế từ trang Giới thiệu:
   - Group Name.
   - Members.
   - Type.
   - URL hiện tại hoặc URL thay thế.
6. Giữ nguyên cột `Status` đọc từ Odoo.
7. Ghi kết quả vào cột `Check Status` riêng.

Kết quả check tối thiểu gồm:

- `ALIVE`: mở được group và lấy đủ dữ liệu cần thiết.
- `PARTIAL`: mở được group nhưng thiếu một hoặc nhiều trường.
- `DEAD`: group không tồn tại, không truy cập được hoặc bị chặn.
- `ERROR`: lỗi Selenium, profile, trình duyệt hoặc selector.
- `TIMEOUT`: quá thời gian chờ.
- `STOPPED`: người dùng dừng tiến trình.

Mỗi kết quả phải có lý do/chi tiết để hiển thị trên dòng và nhật ký; không biến
lỗi thành kết quả thành công hoặc âm thầm bỏ qua.

## 7. Hành vi nút Tải lại và Check lại

### Nút Tải lại danh sách

- Chưa chọn Project: thông báo yêu cầu chọn Project.
- Chưa chọn Pool hoặc Blacklist: thông báo yêu cầu chọn danh sách.
- Đã chọn đủ Project và danh sách: tải lại đúng `project_id` và `link_type` hiện tại.
- Không tải Pool và Blacklist cùng lúc.
- Xóa dữ liệu cũ trước khi hiển thị dữ liệu mới.
- Giữ nguyên Project và danh sách đang chọn.

### Nút Check lại trên từng dòng

- Chỉ kiểm tra group link được bấm, không kiểm tra toàn bộ danh sách.
- Dùng `group_url`; nếu không mở được thì thử `alt_url` theo fallback.
- Hiển thị dữ liệu scrape vào các cột tương ứng và kết quả vào `Check Status`.
- Không làm mất lựa chọn Project, Pool/Blacklist hoặc các dòng khác.
- Không thay đổi cột `Status`.

Logic mở LibreWolf và kiểm tra trực tiếp group Facebook được triển khai riêng;
không gộp logic này với chức năng **Tải lại** dữ liệu từ Odoo.

## 8. Batch, trình duyệt và cập nhật Odoo

1. Lấy các dòng hiện tại sau khi áp dụng Project, Pool/Blacklist và Status filter.
2. Chia danh sách theo kích thước Batch người dùng chọn.
3. Trong mỗi Batch, phân phối group cho số trình duyệt LibreWolf đã chọn.
4. Mỗi trình duyệt dùng profile chung đã đăng nhập; không để nhiều trình duyệt
   đồng thời sử dụng cùng một profile vật lý.
5. Cập nhật progress sau từng group và từng Batch, đồng thời hỗ trợ Stop.
6. Sau khi Batch hoàn thành, gửi dữ liệu scrape và kết quả lên Odoo.

Dữ liệu có thể cập nhật gồm `alt_url`, `group_name`, `member_count`,
`group_type`, `info_updated_at` và field ghi nhận Check Status/chi tiết nếu
module Odoo có hỗ trợ. Tuyệt đối không ghi đè `status`.

Trước khi code API cập nhật phải kiểm tra chính xác các field writable của
`sgt.social.group.link`. Nếu module chưa có field lưu Check Status hoặc chi tiết
lỗi, không tự ý ghi kết quả vào `status`; cần bổ sung field/API rõ ràng hoặc chỉ
lưu kết quả ở giao diện theo quyết định được xác nhận.

## 9. Tách biệt với Check Post Facebook

Không thay đổi chọn tuần/ngày, lọc bài viết, Start Check, LibreWolf checker và nút quay lại trang chọn tool của Check Post Facebook.

Check Group dùng cửa sổ, API, trạng thái và dữ liệu riêng.

## 10. Thứ tự triển khai

1. Kiểm tra lại tên model/field với module Odoo hiện tại.
2. Thêm `GroupLink` dataclass.
3. Thêm API tải Project.
4. Thêm API tải group link theo Project và `link_type`.
5. Dựng combobox Project và hai tab Pool/Blacklist.
6. Dựng bảng hiển thị các trường Group URL, Alt URL, Group Name, Members, Type,
   Information Updated On, Status và Check Status.
7. Thêm tải bất đồng bộ và chống response cũ.
8. Thêm nút **Tải lại** để refresh danh sách đang chọn.
9. Thêm cột cuối với nút **Check lại** cho từng group link.
10. Tạo checker Selenium/LibreWolf dùng chung cơ chế profile với Check Post.
11. Nối luồng mở group, chuyển sang Giới thiệu/About và lấy URL thay thế.
12. Trích xuất Group Name, Members, Type và kết quả Check Status.
13. Nối nút Check lại với logic kiểm tra một group cụ thể.
14. Nối Batch, số trình duyệt, hiện trình duyệt và Stop.
15. Thêm API cập nhật dữ liệu scrape theo Batch, không ghi đè Status.
16. Kiểm tra field writable và kiểm thử cập nhật trên Odoo thật.
17. Chạy kiểm tra cú pháp, lint và build lại EXE nếu cần.

## 11. Tiêu chí hoàn thành

- Mở Check Group chỉ tải danh sách Project.
- Chọn Project không hiển thị nhầm group của Project khác.
- Pool chỉ hiển thị bản ghi có `link_type = pool`.
- Blacklist chỉ hiển thị bản ghi có `link_type = blacklist`.
- Hiển thị đúng Group URL, Alt URL, Group Name, Members, Type,
  Information Updated On, Status và Check Status.
- Nút Tải lại chỉ tải đúng Project và danh sách hiện tại.
- Nút Check lại ở một dòng chỉ kiểm tra đúng group link của dòng đó.
- LibreWolf mở được group, chuyển sang Giới thiệu/About và lấy dữ liệu thực tế.
- URL dạng ID và URL thay thế được xử lý đúng; `alt_url` được cập nhật khi có
  URL mới hợp lệ.
- `Status` Odoo không bị thay đổi bởi kết quả Selenium.
- Check Status phân biệt được thành công, thiếu dữ liệu, không khả dụng, lỗi,
  timeout và stopped.
- Batch gửi đúng dữ liệu scrape và kết quả lên Odoo.
- Có thể tải lại danh sách mà không chạy kiểm tra group.
- Giao diện không bị treo khi Odoo tải dữ liệu.
- Lỗi Odoo được hiển thị rõ ràng.
- Check Post Facebook không bị ảnh hưởng.

## 12. Kiểm thử tự động cho chọn LibreWolf

Các kiểm thử nằm trong `tests/test_librewolf_selection.py` và chạy bằng thư viện
chuẩn `unittest`, không cần Odoo, Facebook, LibreWolf đang mở hoặc giao diện đồ họa.

| Mã | Tình huống | Kết quả mong đợi |
|---|---|---|
| LW-01 | Khởi tạo checker khi chưa chọn thư mục | Báo `ValueError` rõ ràng; không cần đọc `.env`. |
| LW-02 | Chọn thư mục cha chứa thư mục phiên bản LibreWolf | Tìm đúng `librewolf.exe` và `Profiles/Default`. |
| LW-03 | Check Post bắt đầu khi chưa chọn thư mục | Hiện hộp thoại cảnh báo và không khởi chạy worker. |
| LW-04 | Check Group bắt đầu khi chưa chọn thư mục | Hiện hộp thoại cảnh báo và không cho chạy. |
| LW-05 | Check Group đã có thư mục được chọn | Cho phép tiếp tục mà không hiện cảnh báo. |

Chạy bằng lệnh:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Kết quả chạy ngày **2026-10-13**: **5/5 testcase đạt**.

```text
Ran 5 tests in 0.032s
OK
```
