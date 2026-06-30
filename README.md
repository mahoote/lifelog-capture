# Lifelog Capture

`lifelog-capture` is the Raspberry Pi Python project for the Lifelog smart glasses prototype. It is part of a master's
dissertation in Embedded Systems Engineering at the University of Leeds. The project controls the embedded capture unit,
records lifelog footage, stores metadata locally, and transfers footage to the phone when the glasses are ready to sync.

The project is built around a few main areas of logic rather than one large script:

1. capture logic
2. motion logic
3. storage and database logic
4. transfer logic
5. BLE setup logic
6. WiFi and HTTP communication logic
7. startup and reliability logic

## System overview

See the [schematic](docs/Glasses%20Camera%20Interconnect%20Rev%20D.pdf) for how the hardware components are connected.

```text
Glasses hardware
   |
   | camera + motion sensor
   v
Raspberry Pi capture app
   |
   | local files + SQLite metadata
   v
Pending footage queue
   |
   | BLE setup + WiFi HTTP transfer
   v
Phone app
```

The Raspberry Pi handles capture and local storage. The phone handles setup, receiving footage, and later processing or
organising the lifelog data.

BLE is used for small setup and status messages. WiFi HTTP is used for actual file transfer because video files are too
large for BLE.

## Project structure

```text
lifelog-capture/
├── .venv/
├── src/
│   ├── drivers/
│   ├── services/
│   ├── types/
│   ├── utils/
│   ├── workers/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   └── database.py
└── README.md
```

The folders separate low-level hardware access, application services, shared data types, utility helpers, and background
worker logic.

## Capture logic

The capture logic decides when the glasses should record footage and what kind of footage should be captured.

The intended behaviour is:

- capture still photos during normal use
- switch to short video clips when motion is detected
- attach metadata to every captured item
- save footage locally before any transfer happens

This means capture is not dependent on the phone being nearby. The glasses should be able to collect data independently
and transfer it later.

## Motion logic

The motion logic uses the onboard motion sensor to understand whether the glasses are still or moving.

This affects capture decisions. For example:

- when still, the device can capture less aggressively
- when moving, the device can capture short video clips
- motion state can be saved as part of the footage metadata

The goal is to avoid treating all moments the same. Movement can indicate that a short video clip is more useful than a
single photo.

## Storage and database logic

The storage logic keeps footage files and metadata together.

Each captured photo or video should have a database record describing it. The database acts as a manifest of what exists
on the Pi and what still needs to be transferred.

Important metadata includes:

- footage ID
- type, photo or video
- creation time
- file location
- file size
- motion state
- transfer state
- retry count
- checksum
- ack time

The storage logic should be reliable because the Pi may lose power or restart. Files should not be deleted just because
a transfer started. They should only be removed after the phone confirms that the file was received successfully.

## Transfer logic

The transfer logic manages the movement of footage from the Pi to the phone.

The key rule is:

> Footage should only be marked as complete after the phone sends an ack.

A typical transfer lifecycle is:

```text
pending -> uploading -> acked
       \-> failed -> pending retry
```

The transfer logic should support:

- listing files that are ready to transfer
- downloading individual files by ID
- retrying failed transfers
- resuming after interruption
- marking files as acked after successful phone import
- deleting or cleaning up only after ack

This makes the system safer if the phone disconnects, the app crashes, or the Pi loses power during sync.

## BLE setup logic

BLE is used before the phone knows how to reach the Pi over WiFi.

The BLE logic should support:

- advertising the Pi as the Lifelog glasses device
- allowing the phone to discover the device
- sending WiFi scan results to the phone
- receiving WiFi credentials from the phone
- reporting WiFi connection status
- reporting the Pi IP address
- telling the phone when files are ready to transfer

Example BLE setup flow:

```text
1. Phone discovers the Pi over BLE.
2. Phone asks the Pi to scan WiFi networks.
3. Pi returns available SSIDs.
4. User selects a network in the phone app.
5. Phone sends SSID and password over BLE.
6. Pi connects to WiFi.
7. Pi reports connected status and IP address.
8. Phone switches to HTTP for file transfer.
```

BLE should only carry small JSON messages. It should not carry the actual photo or video files.

## WiFi and HTTP communication logic

Once the Pi is connected to WiFi, the phone can communicate with it over HTTP.

The HTTP logic should expose a small local API for:

- checking health and connection status
- listing pending footage
- downloading footage files
- acknowledging successful transfer

Expected API shape:

```text
GET  /health
GET  /footage
GET  /footage/{file_id}
POST /ack
```

The HTTP manifest should not expose raw Pi filesystem paths. The phone should receive IDs and metadata, then use the ID
to request the actual file.

## Startup and mode logic

When the Pi boots, the app should decide what mode it should be in.

Possible modes:

- capture mode, used when the glasses are being worn or running from battery
- transfer mode, used when charging or syncing with the phone
- safe or error mode, used when hardware or storage is unavailable

Startup should be automatic. The project is intended to run as a `systemd` service so it starts on boot and restarts
after a crash.

The app should also handle missing or unreliable time at boot. If the Pi does not have valid wall-clock time yet, the
project should still avoid overwriting files or creating conflicting IDs.

## Reliability logic

The reliability logic is about making the project survive real-world embedded conditions.

Important goals:

- start automatically on boot
- restart after crashes
- recover after power loss
- write files safely
- keep transfer state in SQLite
- retry failed operations
- avoid deleting unacked footage
- log useful errors
- expose enough status for debugging

The project should assume that things can fail. Camera access may fail, storage may be full, WiFi may disconnect, BLE
may be unreliable, and the phone may stop mid-transfer.

## Privacy logic

The project captures personal real-world footage, so privacy is a core part of the design.

Important principles:

- keep data local by default
- avoid unnecessary cloud upload
- make deletion deliberate
- do not expose raw filesystem paths through the API
- only transfer to an expected phone app
- later add pairing, encryption, and physical setup mode
