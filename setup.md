# VisionDesk Setup Guide

## 1. Chuẩn bị môi trường

Yêu cầu tối thiểu:

- Python `3.10+`
- `pip`
- Windows/Linux/macOS cho chế độ development
- Raspberry Pi OS Desktop cho chế độ triển khai thiết bị thật

Di chuyển vào thư mục dự án:

```bash
cd "Raspberry Pi AI Vision Desk Assistant"
```

## 2. Chạy local để develop/demo

Cài dependency Python:

```bash
pip install -r requirements.txt
```

Chạy app ở chế độ mock hardware, mở cửa sổ desktop bình thường:

```bash
python -m qt_app.main --windowed --mock-hardware
```

Nếu muốn chạy trực tiếp Qt app không dùng mock:

```bash
python -m qt_app.main
```

Chạy test:

```bash
pytest -q
```

## 3. Các path local mặc định

Ở chế độ development, project sẽ dùng:

- `config/device.yaml`
- `.env`
- `data/`
- `logs/`

Nếu cần override path, có thể dùng các biến môi trường:

- `VISIONDESK_PATH_MODE`
- `DEVICE_CONFIG_PATH`
- `VISIONDESK_ENV_FILE`
- `VISIONDESK_DATA_DIR`
- `VISIONDESK_LOG_DIR`

## 4. Cài lên Raspberry Pi

VisionDesk production dùng một service duy nhất là `visiondesk.service`.

Chạy cài đặt:

```bash
sudo ./install.sh
```

Các option hỗ trợ:

```bash
sudo ./install.sh --non-interactive
sudo ./install.sh --skip-hardware-check
sudo ./install.sh --reset-config
sudo ./install.sh --force
```

Installer sẽ:

- tạo user `visiondesk`
- cài package hệ thống cần thiết
- stage release vào `/opt/visiondesk/releases/<version>`
- tạo symlink `/opt/visiondesk/current`
- seed config vào `/etc/visiondesk`
- tạo data/log ở `/var/lib/visiondesk` và `/var/log/visiondesk`
- cài `deployment/visiondesk.service`

## 5. Các path production

Khi cài kiểu appliance, các path chính là:

- `/opt/visiondesk/current`
- `/opt/visiondesk/releases/<version>`
- `/etc/visiondesk/device.yaml`
- `/etc/visiondesk/visiondesk.env`
- `/var/lib/visiondesk/setup_state.json`
- `/var/lib/visiondesk/result_history.json`
- `/var/lib/visiondesk/private/`
- `/var/log/visiondesk/`

## 6. Quản lý service

Start service:

```bash
sudo systemctl start visiondesk.service
```

Restart service:

```bash
sudo systemctl restart visiondesk.service
```

Xem trạng thái:

```bash
sudo systemctl status visiondesk.service
```

Xem log:

```bash
journalctl -u visiondesk.service -f
```

## 7. Update phiên bản

Kiểm tra cài đặt hiện tại:

```bash
sudo ./update.sh --check
```

Update từ archive local:

```bash
sudo ./update.sh --local /path/to/visiondesk-release.tar.gz
```

Chỉ validate trước khi update:

```bash
sudo ./update.sh --local /path/to/visiondesk-release.tar.gz --dry-run
```

Rollback về bản trước:

```bash
sudo ./update.sh --rollback
```

## 8. Gỡ cài đặt

Gỡ app nhưng giữ config, data, logs:

```bash
sudo ./uninstall.sh
```

Xem trước những gì sẽ bị xóa:

```bash
sudo ./uninstall.sh --dry-run
```

Gỡ sạch cả config/data/log:

```bash
sudo ./uninstall.sh --purge
```

## 9. Reset thiết bị

Xóa dữ liệu người dùng nhưng giữ setup/config:

```bash
sudo ./factory-reset.sh --mode user_data
```

Reset cấu hình và quay lại Setup Wizard:

```bash
sudo ./factory-reset.sh --mode configuration
```

Factory reset đầy đủ:

```bash
sudo ./factory-reset.sh --mode factory_reset --phrase "ERASE VISIONDESK"
```

Nếu muốn xóa luôn Wi-Fi profile đã lưu:

```bash
sudo ./factory-reset.sh --mode factory_reset --remove-wifi --phrase "ERASE VISIONDESK"
```

## 10. Luồng chạy khuyến nghị

Cho dev:

1. `pip install -r requirements.txt`
2. `python -m qt_app.main --windowed --mock-hardware`
3. `pytest -q`

Cho Raspberry Pi production:

1. copy source project lên Pi
2. chạy `sudo ./install.sh`
3. kiểm tra `sudo systemctl status visiondesk.service`
4. xem log bằng `journalctl -u visiondesk.service -f`
5. update sau này bằng `sudo ./update.sh --local ...`
