# Hướng dẫn cài đặt và demo VisionDesk

Tài liệu này phản ánh trạng thái hiện tại của dự án: một appliance Raspberry Pi
chạy ứng dụng native `PySide6 + Qt Quick/QML`, màn HDMI 11.6 inch không cảm ứng,
10 nút GPIO và thiết lập lần đầu bằng điện thoại qua Wi-Fi AP tạm thời.

## 1. Phạm vi hiện tại

- Tám màn hình chính: Setup, Home, Camera, Processing, Result, History,
  History Detail và Error.
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

## 3. Môi trường phát triển Windows

Tại thư mục dự án:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Các dependency runtime được quản lý trong `requirements.txt`: PySide6,
OpenAI SDK, Pillow, `python-dotenv`, `gpiozero`, PyYAML, NumPy và `qrcode`.
`pytest`/`pytest-qt` phục vụ kiểm thử. Không cần cài Flask để chạy ứng dụng hiện tại.

Tạo `.env` nếu cần override cấu hình local:

```powershell
Copy-Item .env.example .env
```

Để chạy phân tích OpenAI thật, thêm API key vào `.env`:

```dotenv
OPENAI_API_KEY=sk-your-real-key
```

Không commit `.env`, không gửi key vào chat, Git hoặc ảnh chụp màn hình.

## 4. Chạy và kiểm thử local

Chạy UI với camera/GPIO/pipeline giả lập:

```powershell
python -m qt_app.main --windowed --mock-hardware
```

Chạy với phần cứng cục bộ:

```powershell
python -m qt_app.main
```

Chạy regression suite:

```powershell
python -m pytest -q
```

Chụp các UI Qt/QML bằng mock data:

```powershell
python tools/capture_ui_screenshots.py
```

Ảnh được ghi vào `debug/ui-screenshots/`; file `00-contact-sheet.png` là ảnh
tổng hợp Setup, Home, Camera, Processing, Result, History, History Detail và Error.

## 5. Cấu hình màn hình và setup portal

`display.size: 1200x800` trong `config/device.yaml` là canvas tham chiếu khi
chạy windowed. Ở kiosk production, ứng dụng fullscreen theo native resolution
của màn HDMI; giá trị này không đổi resolution phần cứng.

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

Lưu ý: profile repository hiện đánh dấu `setup.completed: true` vì đây là trạng
thái thiết bị đã setup. Để demo luồng first-boot trên Pi, dùng Configuration
Reset ở mục 9 hoặc triển khai một cấu hình thiết bị mới có `setup.completed: false`.

## 6. Cài đặt lên Raspberry Pi

Mục tiêu production là Raspberry Pi OS Desktop, LightDM autologin và user
`visiondesk` chuyên dụng.

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

Installer sẽ cài system packages, tạo release virtualenv, service, thư mục bền
vững và PolicyKit rule giới hạn quyền NetworkManager cho nhóm `visiondesk`.
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
7. Thiết bị restart vào Home.

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
sudo ./update.sh --local /path/to/visiondesk-release.tar.gz
sudo ./update.sh --rollback
```

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

Xem thêm vận hành và security boundary của portal tại
[docs/phone_setup.md](docs/phone_setup.md).
