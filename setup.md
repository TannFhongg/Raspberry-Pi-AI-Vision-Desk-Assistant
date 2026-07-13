# Hướng dẫn cài đặt VisionDesk

## 1. Yêu cầu

- Python `3.10+`
- `pip`
- Windows, Linux hoặc macOS cho môi trường phát triển
- Raspberry Pi OS Desktop cho thiết bị triển khai thực tế

Vào thư mục dự án:

```powershell
cd "Raspberry Pi AI Vision Desk Assistant"
```

## 2. Chạy local bằng `.venv`

Tạo môi trường ảo và cài toàn bộ thư viện, bao gồm `PySide6`:

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Mỗi terminal mới cần kích hoạt lại `.venv` trước khi chạy app hoặc test.

## 3. Cấu hình `.env`

Tạo file từ mẫu nếu muốn có toàn bộ giá trị cấu hình:

```powershell
Copy-Item .env.example .env
```

Khi chạy trong repository, chỉ biến này là bắt buộc cho chức năng phân tích OpenAI thực tế:

```dotenv
OPENAI_API_KEY=sk-your-real-key
```

Hai biến sau là tùy chọn vì ứng dụng đã có giá trị mặc định, nhưng có thể giữ để rõ ràng:

```dotenv
OPENAI_MODEL=gpt-5.4-mini
DEVICE_CONFIG_PATH=config/device.yaml
```

Chỉ cần copy toàn bộ `.env.example` khi bạn muốn override camera, GPIO, màn hình, retry, lưu trữ hoặc logging. Không commit `.env` và không gửi API key vào chat, Git hoặc ảnh chụp màn hình.

Nếu dùng Setup Wizard, key mới sẽ được kiểm tra trước khi lưu. UI chỉ hiển thị trạng thái đã/chưa cấu hình, không nhận API key hoặc chuỗi key đã che.

## 4. Chạy và kiểm thử local

Chạy UI desktop với mock camera/GPIO/pipeline:

```bash
python -m qt_app.main --windowed --mock-hardware
```

Chạy với phần cứng kết nối cục bộ:

```bash
python -m qt_app.main
```

Chạy test:

```bash
pytest -q
```

Đường dẫn mặc định ở chế độ development:

- `config/device.yaml`
- `.env`
- `data/`
- `logs/`

Các biến override được hỗ trợ: `VISIONDESK_PATH_MODE`, `DEVICE_CONFIG_PATH`, `VISIONDESK_ENV_FILE`, `VISIONDESK_DATA_DIR`, và `VISIONDESK_LOG_DIR`.

## 5. Cài lên Raspberry Pi

Production chỉ chạy một service là `visiondesk.service`.

```bash
sudo ./install.sh
```

Tùy chọn hỗ trợ:

```bash
sudo ./install.sh --non-interactive
sudo ./install.sh --skip-hardware-check
sudo ./install.sh --reset-config
sudo ./install.sh --force
```

Installer sẽ tạo user `visiondesk`, tạo `.venv` riêng cho release, cài service, và tạo các thư mục bền vững. Không tự tạo `.venv` thủ công trong thư mục source để thay thế môi trường production.

Các path chính trên Pi:

- `/opt/visiondesk/current`: release đang chạy
- `/opt/visiondesk/releases/<version>`: các release đã stage
- `/etc/visiondesk/device.yaml`: cấu hình thiết bị
- `/etc/visiondesk/visiondesk.env`: secret và override, quyền `0600`
- `/var/lib/visiondesk/`: setup state, history, media retry riêng tư, runtime marker
- `/var/log/visiondesk/`: log runtime và lifecycle

Trên Pi, dùng `DEVICE_CONFIG_PATH=/etc/visiondesk/device.yaml`; không dùng `config/device.yaml` trong `.env` production.

## 6. Quản lý service

```bash
sudo systemctl start visiondesk.service
sudo systemctl restart visiondesk.service
sudo systemctl status visiondesk.service
journalctl -u visiondesk.service -f
```

## 7. Update và rollback

Kiểm tra bản cài đặt:

```bash
sudo ./update.sh --check
```

Update từ archive local:

```bash
sudo ./update.sh --local /path/to/visiondesk-release.tar.gz
```

Chỉ kiểm tra archive, không thay đổi release đang chạy:

```bash
sudo ./update.sh --local /path/to/visiondesk-release.tar.gz --dry-run
```

Rollback về release trước đó:

```bash
sudo ./update.sh --rollback
```

Updater chỉ thành công khi app tạo marker readiness mới tại `/var/lib/visiondesk/runtime/readiness.json`, đúng version/PID, QML và storage đã sẵn sàng, rồi service ổn định hết khoảng thời gian kiểm tra. Nếu không đạt, updater tự rollback và kiểm tra lại release cũ.

Mặc định: chờ khởi động 60 giây và ổn định 20 giây. Có thể chỉnh `UPDATE_STARTUP_TIMEOUT_SECONDS`, `UPDATE_STABILITY_SECONDS`, và `READINESS_MAX_AGE_SECONDS` khi cần chẩn đoán thiết bị chậm.

## 8. Gỡ cài đặt và reset

Gỡ app nhưng giữ cấu hình, dữ liệu và log:

```bash
sudo ./uninstall.sh
```

Xem trước thao tác gỡ:

```bash
sudo ./uninstall.sh --dry-run
```

Gỡ sạch cả cấu hình, dữ liệu và log:

```bash
sudo ./uninstall.sh --purge
```

Xóa dữ liệu người dùng nhưng giữ setup/config:

```bash
sudo ./factory-reset.sh --mode user_data
```

Reset cấu hình và quay về Setup Wizard:

```bash
sudo ./factory-reset.sh --mode configuration
```

Factory reset đầy đủ:

```bash
sudo ./factory-reset.sh --mode factory_reset --phrase "ERASE VISIONDESK"
```

Xóa luôn Wi-Fi profile đã lưu:

```bash
sudo ./factory-reset.sh --mode factory_reset --remove-wifi --phrase "ERASE VISIONDESK"
```
