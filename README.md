# RFID & Fingerprint Attendance System for Raspberry Pi 4

A modern web-based attendance tracking system using RFID (RC522) and Fingerprint (R307) sensors on Raspberry Pi 4, with Firebase database integration.

## Features

- **Worker Registration**: Register workers with name, fingerprint, and/or RFID card
- **Attendance Tracking**: Clock in/out using fingerprint or RFID
- **Real-time Dashboard**: View attendance records and system status
- **Firebase Integration**: Store all data securely in the cloud
- **Modern Web Interface**: Beautiful and responsive design

## Hardware Requirements

- Raspberry Pi 4 (any model)
- R307 Fingerprint Sensor
- RC522 RFID Reader
- RFID Cards/Tags
- Jumper wires
- Optional: LEDs for status indication (green and red)

## Hardware Setup

### Wiring the R307 Fingerprint Sensor

The R307 fingerprint sensor uses UART communication. Connect it to the Raspberry Pi as follows:

| R307 Pin | Raspberry Pi Pin |
|----------|------------------|
| VCC (Red) | 3.3V (Pin 1) |
| GND (Black) | GND (Pin 6) |
| TX (Green) | RXD (Pin 10) |
| RX (White) | TXD (Pin 8) |

### Wiring the RC522 RFID Reader

The RC522 RFID reader uses SPI communication. Connect it to the Raspberry Pi as follows:

| RC522 Pin | Raspberry Pi Pin |
|-----------|------------------|
| SDA | GPIO8 (Pin 24) |
| SCK | GPIO11 (Pin 23) |
| MOSI | GPIO10 (Pin 19) |
| MISO | GPIO9 (Pin 21) |
| IRQ | Not connected |
| GND | GND (Pin 6) |
| RST | GPIO25 (Pin 22) |
| 3.3V | 3.3V (Pin 1) |

### Optional: Status LEDs

| LED | Raspberry Pi Pin |
|-----|------------------|
| Green LED | GPIO18 (Pin 12) |
| Red LED | GPIO17 (Pin 11) |

## Software Setup

### 1. Enable SPI and UART

```bash
sudo raspi-config
```

- Navigate to "Interface Options"
- Enable SPI
- Enable Serial Port (UART)
- Reboot the Raspberry Pi

### 2. Install Required Packages

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev libffi-dev libssl-dev
sudo pip3 install --upgrade pip
```

### 3. Clone the Repository

```bash
git clone https://github.com/yourusername/rfid-fingerprint-attendance.git
cd rfid-fingerprint-attendance
```

### 4. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

### 5. Set Up Firebase

1. Create a Firebase project at [firebase.google.com](https://firebase.google.com)
2. Set up Firestore Database
3. Generate a service account key:
   - Go to Project Settings > Service Accounts
   - Click "Generate New Private Key"
   - Save the JSON file as `serviceAccountKey.json` in the project root directory

### 6. Run the Application

```bash
python3 app.py
```

The web interface will be accessible at `http://raspberry-pi-ip:5000`

Default login credentials:
- Username: `admin`
- Password: `admin123`

## Usage

### Registration Process

1. Log in to the web interface
2. Navigate to the Registration page
3. Enter the worker's name
4. Register the worker's fingerprint
5. Register the worker's RFID card
6. Complete the registration

### Attendance Tracking

1. Navigate to the Attendance page
2. Select Clock In or Clock Out mode
3. Workers can scan their fingerprint or RFID card
4. The system will record their attendance and display their information

## Troubleshooting

### Fingerprint Sensor Issues

- Ensure the UART is properly enabled
- Check the wiring connections
- Try a different USB-to-TTL adapter if using one

### RFID Reader Issues

- Ensure SPI is properly enabled
- Check the wiring connections
- Try different RFID cards/tags

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [pyfingerprint](https://github.com/bastianraschke/pyfingerprint) library
- [MFRC522-python](https://github.com/mxgxw/MFRC522-python) library
- [Flask](https://flask.palletsprojects.com/) web framework
- [Firebase Admin SDK](https://firebase.google.com/docs/admin/setup) for Python
