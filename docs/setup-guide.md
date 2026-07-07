# Raspberry Pi Zero 2 W setup guide

## Install project dependencies

Install the system packages needed for Bluetooth, WiFi management, the screen session, SQLite inspection and I2C
debugging:

```bash
sudo apt update
sudo apt install screen sqlite3 libcamera-apps
```

Enable and start NetworkManager, this is used by the app to scan and connect to WiFi:

```bash
sudo systemctl enable NetworkManager
sudo systemctl start NetworkManager
```

If you do not see .venv, create it:

```bash
cd ~/lifelog-capture
python3 -m venv --system-site-packages .venv
```

From the project root, install the Python dependencies:

```bash
source .venv/bin/activate
pip install fastapi uvicorn pydantic gpiozero
```

---

## Enable I2C for BMI160

The BMI160 is wired to the Raspberry Pi's main I2C pins:

| BMI160 | Raspberry Pi Zero 2 W  |
|--------|------------------------|
| VCC    | 3.3 V                  |
| GND    | GND                    |
| SDA    | GPIO 2, physical pin 3 |
| SCL    | GPIO 3, physical pin 5 |

These pins use I2C bus 1, which should appear as:

```bash
/dev/i2c-1
```

If `/dev/i2c-1` is missing, enable I2C in the Pi boot config.

### Check current config

```bash
grep -n "i2c" /boot/firmware/config.txt
```

If it shows this, I2C is disabled:

```bash
#dtparam=i2c_arm=on
```

### Enable I2C

Edit the config file:

```bash
sudo nano /boot/firmware/config.txt
```

Change this:

```bash
#dtparam=i2c_arm=on
```

to this:

```bash
dtparam=i2c_arm=on
```

Save and exit:

```plain text
Ctrl + O
Enter
Ctrl + X
```

Reboot:

```bash
sudo reboot
```

### Verify I2C bus exists

After reboot:

```bash
ls /dev/i2c*
```

Expected result should include:

```bash
/dev/i2c-1
```

---

## Start lifelog capture on boot in screen

Use a `systemd` service to start the capture app inside a detached `screen` session named `pi`. This lets you reconnect
later to see logs or stop the program manually.

### Create the systemd service

Create the service file:

```bash
sudo nano /etc/systemd/system/lifelog-capture.service
```

Add:

```plain text
[Unit]
Description=Lifelog Capture in screen
After=network.target

[Service]
Type=forking
User=martin
WorkingDirectory=/home/martin/lifelog-capture
ExecStart=/usr/bin/screen -dmS pi /home/martin/lifelog-capture/start_lifelog.sh
ExecStop=/usr/bin/screen -S pi -X quit
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable lifelog-capture.service
sudo systemctl start lifelog-capture.service
```

Check status:

```bash
sudo systemctl status lifelog-capture.service
```

### Reconnect to the screen session

List screen sessions:

```bash
screen -ls
```

Attach to the running session:

```bash
screen -r pi
```

Detach without stopping the app:

```plain text
Ctrl + A
D
```

Stop manually while inside screen:

```plain text
Ctrl + C
```

Or stop through systemd:

```bash
sudo systemctl stop lifelog-capture.service
```

### Restart behaviour

For standalone use, keep:

```plain text
Restart=on-failure
```

For development, use:

```plain text
Restart=no
```

If you stop the program manually with `Ctrl + C` while `Restart=on-failure` is enabled, systemd may start it again.

---

## Inspect the SQLite database with sqlite3

Use `sqlite3` on the Pi to quickly view the database tables and rows from the terminal. This is lighter than using a
graphical database browser on the Pi Zero 2 W.

### Open the database

From the project folder:

```bash
cd ~/lifelog-capture
sqlite3 data/lifelog.db
```

If the database is stored somewhere else, replace `data/lifelog.db` with the correct path.

### Make output readable

Inside the `sqlite3` prompt:

```sql
.headers on
.mode box
```

If `.mode box` is not supported, use:

```sql
.mode column
```

### List tables

```sql
.tables
```

### Show the table structure

```sql
.schema footage_item
```

### View rows

```sql
SELECT *
FROM footage_item;
```

For a cleaner view:

```sql
SELECT id,
       type,
       created_at,
       file_path,
       size_bytes,
       state,
       attempt_count
FROM footage_item;
```

### Exit sqlite3

```sql
.quit
```
