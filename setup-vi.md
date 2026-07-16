# Hướng dẫn cài đặt và demo VisionDesk

Áp dụng cho VisionDesk **1.0.3** (`v1.0.3`).

Tài liệu này phản ánh trạng thái hiện tại của dự án: một appliance Raspberry Pi
chạy ứng dụng native `PySide6 + Qt Quick/QML`, màn HDMI 11.6 inch không cảm ứng,
10 nút GPIO và thiết lập lần đầu bằng điện thoại qua Wi-Fi AP tạm thời.

## 1. Phạm vi hiện tại

- Mười một màn hình chính: Setup, Home, Camera, Review and Adjust, Processing,
  Result, History, History Detail, Error, Settings và Device Health.
- Năm workflow AI độc lập: Read Text, Summarize Document, Analyze Image,
  Professional Assistant và Solve Problem.
- Màn 11.6 inch không cảm ứng: điều hướng bằng GPIO Up/Down/Select; vẫn nên có
  keyboard/mouse cho recovery và tác vụ quản trị.
- Phone-first setup: QR, SSID/password tạm và pairing code xuất hiện khi setup
  chưa hoàn tất; điện thoại nhập Wi-Fi đích và OpenAI API key.
- Production chỉ chạy native Qt service `visiondesk.service`; Flask không nằm
  trong runtime sản phẩm. Portal điện thoại dùng HTTP server nội bộ ngắn hạn.

## 2. Phần cứng cần có

- Raspberry Pi 5 8GB, nguồn USB-C 5V/5A, microSD 32GB trở lên và quạt/case tản nhiệt.
- Webcam USB.
- Màn HDMI 11.6 inch landscape, không cảm ứng, cùng cáp HDMI phù hợp.
- Wi-Fi adapter do NetworkManager quản lý và hỗ trợ protected AP/hotspot mode
  nếu muốn dùng phone-first setup.
- Mười nút nhấn momentary, dây jumper và breadboard (khuyến nghị).

BCM GPIO mặc định:

| Chức năng | GPIO |
| --- | ---: |
| Capture | 17 |
| Read Text | 5 |
| Summarize Document | 6 |
| Analyze Image | 13 |
| Professional Assistant | 19 |
| Solve Problem | 26 |
| Back | 22 |
| Navigate Up | 23 |
| Navigate Down | 24 |
| Select / Confirm | 25 |

Dây LAN không bắt buộc. Mang theo LAN, keyboard/mouse và mobile hotspot làm
phương án dự phòng cho buổi demo.

## 3. Môi trường phát triển

Yêu cầu chung: Python 3.10 trở lên và một desktop session X11/Wayland nếu chạy
Qt/QML có cửa sổ. Môi trường Linux dưới đây dành cho máy phát triển Ubuntu/Debian
hoặc Raspberry Pi OS Desktop; nó không thay thế quy trình cài appliance ở mục 6.

### 3.1 Windows

Tại thư mục dự án:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3.2 Linux (Ubuntu/Debian/Raspberry Pi OS Desktop)

Cài Python, công cụ virtual environment và các thư viện Qt cần để PySide6 chạy
trên X11/Wayland. Không cần cài `python3-rpi.gpio` hoặc NetworkManager cho máy
phát triển không gắn GPIO/phone portal.

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv \
  libdbus-1-3 libegl1 libgl1 libopengl0 libx11-xcb1 libxcb-cursor0 \
  libxcb-keysyms1 libxcb-icccm4 libxcb-image0 libxcb-randr0 \
  libxcb-render-util0 libxcb-xfixes0 libxcb-xinerama0 libxkbcommon-x11-0

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Trên Linux headless/SSH, chỉ chạy test không cần cửa sổ bằng cách đặt Qt ở chế
độ offscreen:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

Các dependency Python runtime được quản lý trong `requirements.txt`: PySide6,
OpenAI SDK, Pillow, `python-dotenv`, `gpiozero`, PyYAML, NumPy và `qrcode`.
`pytest`/`pytest-qt` phục vụ kiểm thử. Không cần cài Flask để chạy ứng dụng hiện tại.

Tạo `.env` nếu cần override cấu hình local:

```powershell
Copy-Item .env.example .env
```

Trên Linux dùng:

```bash
cp .env.example .env
```

Để chạy phân tích OpenAI thật, thêm API key vào `.env`:

```dotenv
OPENAI_API_KEY=sk-your-real-key
```

Không commit `.env`, không gửi key vào chat, Git hoặc ảnh chụp màn hình.

## 4. Chạy và kiểm thử local

Chạy UI với camera/GPIO/pipeline giả lập:

```bash
python -m qt_app.main --windowed --mock-hardware
```

Chạy với phần cứng cục bộ:

```bash
python -m qt_app.main
```

Chạy regression suite trên Linux/Raspberry Pi OS:

```bash
python -m pytest -q
```

Trên Windows, chạy nhóm không Qt và nhóm Qt trong hai process riêng. OpenCV và
PySide có thể xung đột native khi cùng được nạp trong một process pytest dù cả
hai nhóm đều vượt qua khi chạy độc lập:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_QUICK_BACKEND = "software"
$env:QSG_RHI_BACKEND = "software"
python -m pytest -q --ignore=tests/test_qt_app.py
python -m pytest -q tests/test_qt_app.py
```

Chụp các UI Qt/QML bằng mock data:

```bash
python tools/capture_ui_screenshots.py
```

Ảnh được ghi vào `debug/ui-screenshots/`. Công cụ hiện tạo 27 ảnh riêng ở đúng
1366 x 768 và file tổng hợp `00-contact-sheet.png`, bao phủ các trạng thái
Setup/Finish Setup, Home/header, Settings, Large Text, Device Health, Camera,
Review and Adjust, Processing, Result, History, History Detail và Error. Bộ ảnh
đã duyệt nằm trong `docs/images/app-screens/`.

## 5. Cấu hình màn hình và setup portal

`display.size: 1366x768` trong `config/device.yaml` là kích thước chính khi chạy
windowed. Ở kiosk production, Qt dùng trực tiếp geometry fullscreen thực tế của
màn HDMI; VisionDesk không kéo giãn một canvas trung gian. Giá trị này không đổi
resolution phần cứng. Kích thước 1200x800 trước đây là giả định mục tiêu không đúng.

Installer cài Noto Sans và kiểm tra bằng fontconfig. Nếu font này không có,
VisionDesk lần lượt dùng Inter, DejaVu Sans hoặc Roboto OFL đi kèm. Thiết lập
`display.text_size` hỗ trợ `standard`, `large` và `extra_large`.

Finish Setup dùng các thẻ validation hai cột có chiều cao theo nội dung. Thông
báo dài tự xuống dòng trong thẻ và phần nội dung cuộn phía trên footer Back/Ready
cố định. Desktop mock mode ghi rõ giới hạn giả lập thay vì dùng raw exception
phần cứng làm thông báo chính.

Cấu hình phone-first portal:

```yaml
setup_portal:
  enabled: true
  auto_start_when_setup_incomplete: true
  session_timeout_minutes: 15
  interface: wlan0
  address: 192.168.4.1
  port: 80
  ssid_prefix: VisionDesk-Setup
```

Portal chỉ tự chạy trên thiết bị thật có setup chưa hoàn tất. Nó không chạy ở
`--mock-hardware`. QR chỉ chứa URL cục bộ, ví dụ `http://192.168.4.1`; password
Wi-Fi tạm và pairing code 8 số nằm trên màn VisionDesk.

Mẫu cấu hình phát hành đặt `setup.completed: false`, vì vậy một thiết bị mới sẽ
vào Welcome và hiển thị phone-first setup ngay sau lần cài đầu. Chỉ dùng
Configuration Reset ở mục 9 khi cần đưa một thiết bị đã vận hành trở lại luồng
first-boot.

## 6. Cài mới một thiết bị Raspberry Pi

Mục tiêu production là Raspberry Pi OS Desktop 64-bit, LightDM autologin và
user `visiondesk` chuyên dụng. Cần có bản mã nguồn/release trên Pi trước khi
chạy installer: `install.sh` đóng gói chính thư mục đó thành release đang chạy
ở `/opt/visiondesk`.

### 6.1 Chuẩn bị hệ điều hành

1. Dùng Raspberry Pi Imager ghi **Raspberry Pi OS Desktop 64-bit** vào microSD.
2. Trong Imager, đặt username/password, múi giờ và Wi-Fi; bật SSH nếu bạn sẽ
   thao tác từ máy khác.
3. Cắm HDMI 11.6 inch, webcam, keyboard/mouse và mạng; boot Pi rồi đăng nhập.
4. Cập nhật hệ điều hành và khởi động lại:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Sau khi Pi khởi động lại, mở Terminal hoặc SSH trở lại thiết bị.

### 6.2 Lấy đúng mã nguồn phát hành

Với repository hiện tại, clone về thư mục home của user quản trị (không clone
vào `/opt` và không dùng `sudo git clone`):

```bash
sudo apt install -y git
git clone --depth 1 --branch v1.0.3 \
  https://github.com/TannFhongg/Raspberry-Pi-AI-Vision-Desk-Assistant.git \
  ~/visiondesk
cd ~/visiondesk
git describe --tags --exact-match
chmod +x install.sh
```

Production cài từ tag cố định `v1.0.3`, không dùng `master`. `master` chỉ dành
cho development. Nếu Pi không có Internet, chép source đã checkout đúng tag
bằng USB hoặc `scp`, rồi `cd` vào thư mục đó trước khi cài.

Không cần tạo `.env` trong source hay đặt OpenAI API key trước khi cài một thiết
bị mới. API key sẽ được nhập và xác minh trong phone-first setup; installer tạo
file secret `/etc/visiondesk/visiondesk.env` với quyền hạn chế.

### 6.3 Cài appliance

```bash
sudo ./install.sh
```

Tùy chọn:

```bash
sudo ./install.sh --non-interactive
sudo ./install.sh --skip-hardware-check
sudo ./install.sh --reset-config
sudo ./install.sh --force
```

Dùng `--skip-hardware-check` khi camera hoặc GPIO chủ động chưa được kết nối.
Ứng dụng vẫn cần các phần cứng này để hoạt động bình thường sau khi cài đặt.

Installer sẽ cài system packages, tạo release virtualenv, service, thư mục bền
vững và PolicyKit rule giới hạn quyền NetworkManager cho nhóm `visiondesk`.
Sau khi hoàn tất, source ở `~/visiondesk` chỉ là bản dùng cho bảo trì/cập nhật;
service chạy release đã được cài ở `/opt/visiondesk/current`.

Sau khi cài, xác nhận:

```bash
nmcli device status
nmcli general permissions
sudo systemctl status NetworkManager
sudo systemctl status visiondesk.service
```

Các path production:

- `/opt/visiondesk/current`: release đang chạy.
- `/etc/visiondesk/device.yaml`: cấu hình thiết bị bền vững.
- `/etc/visiondesk/visiondesk.env`: secrets, quyền `0600`.
- `/var/lib/visiondesk/`: setup state, history và private retry media.
- `/var/log/visiondesk/`: log service và lifecycle.

Không chỉnh `config/device.yaml` trong source release để đổi cấu hình production;
dùng `/etc/visiondesk/device.yaml` và `/etc/visiondesk/visiondesk.env`.

## 7. Luồng phone-first setup

Điều kiện: `setup.completed: false`, portal được bật, `wlan0` hỗ trợ AP và
NetworkManager khả dụng.

1. Bật VisionDesk và chờ màn Welcome.
2. Trên màn xuất hiện thẻ **Phone setup** với SSID `VisionDesk-Setup-XXXX`,
   password tạm, QR, URL và pairing code 8 số.
3. Điện thoại kết nối SSID tạm, quét QR hoặc mở URL trên màn.
4. Nhập pairing code, chọn Wi-Fi đích, nhập password Wi-Fi và OpenAI API key.
5. VisionDesk phản hồi yêu cầu, xóa AP tạm, kết nối Wi-Fi đích, xác minh API key
   và kiểm tra camera.
6. Nhấn mỗi trong 10 nút GPIO một lần để hoàn tất wiring test.
7. Kiểm tra các gate ở Finish Setup. Lỗi dài vẫn đọc được bằng cách cuộn; nút
   Ready chỉ bật khi Wi-Fi, xác minh API, camera và GPIO đều đạt.
8. Hoàn tất setup để thiết bị restart vào Home.

Nếu AP không chạy, dùng keyboard/mouse với Setup Wizard trực tiếp. Kiểm tra
`nmcli device status`, `nmcli general permissions` và `journalctl -u visiondesk.service -b`.

## 8. Demo nhanh

1. Chuẩn bị một tài liệu in rõ, một ảnh mẫu và một bài toán ngắn.
2. Chuẩn bị Wi-Fi Internet ổn định hoặc mobile hotspot, cùng API key có quota.
3. Demo first-boot bằng QR nếu thiết bị đang ở trạng thái setup incomplete.
4. Demo lần lượt 5 mode AI và thao tác Capture/Back/Up/Down/Select bằng nút GPIO.
5. Mở Result và History để minh họa lưu kết quả text-only.

Không quảng bá “Hear printed text”/TTS như tính năng hoàn chỉnh: TTS chưa được
triển khai trong phiên bản hiện tại.

## 9. Service, update và reset

Quản lý service:

```bash
sudo systemctl restart visiondesk.service
sudo systemctl status visiondesk.service
journalctl -u visiondesk.service -f
```

Update và rollback:

```bash
sudo ./update.sh --check
sudo ./update.sh --local /path/to/visiondesk-1.0.3.tar.gz --version 1.0.3 --dry-run
sudo ./update.sh --local /path/to/visiondesk-1.0.3.tar.gz --version 1.0.3
sudo ./update.sh --rollback
```

Build/verify archive trên maintenance workstation, upload GitHub Release,
contract `manifest.json` và checksum được mô tả tại
[docs/release-packaging.md](docs/release-packaging.md).
Không dùng GitHub-generated Source code.zip/Source code.tar.gz trực tiếp cho
`update.sh`.

Reset dữ liệu hoặc quay lại Setup Wizard:

```bash
sudo ./factory-reset.sh --mode user_data --yes
sudo ./factory-reset.sh --mode configuration --yes
sudo ./factory-reset.sh --mode factory_reset --phrase "ERASE VISIONDESK"
```

`configuration` reset xóa API key và trạng thái setup, sau đó quay về Welcome
để có thể chạy phone-first setup lần nữa. Dùng `--remove-wifi` với factory reset
nếu cần xóa luôn profile Wi-Fi đã lưu.

Gỡ cài đặt nhưng giữ data/config mặc định:

```bash
sudo ./uninstall.sh
```

Xem trước hoặc gỡ sạch:

```bash
sudo ./uninstall.sh --dry-run
sudo ./uninstall.sh --purge
```

Xem thêm kiến trúc tại [docs/architecture.md](docs/architecture.md) và security
boundary của portal tại [docs/phone_setup.md](docs/phone_setup.md).
