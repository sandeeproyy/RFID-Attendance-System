import time
from pyfingerprint.pyfingerprint import PyFingerprint
from mfrc522 import SimpleMFRC522
import firebase_config

# Initialize fingerprint scanner
try:
    f = PyFingerprint('/dev/ttyUSB0', 57600, 0xFFFFFFFF, 0x00000000)
    if (f.verifyPassword() == False):
        raise ValueError('Fingerprint sensor not found!')
except Exception as e:
    print('Error initializing fingerprint sensor:', str(e))
    exit(1)

# Initialize RFID reader
rfid = SimpleMFRC522()

# Attendance process
def record_attendance(worker_id):
    try:
        # Get worker details
        worker_ref = firebase_config.db.collection('workers').document(str(worker_id))
        worker = worker_ref.get()
        if not worker.exists:
            print('Worker not found!')
            return

        # Display worker details
        worker_data = worker.to_dict()
        print(f'\nWorker: {worker_data["name"]}')
        print('1. Clock In')
        print('2. Clock Out')
        choice = input('Select option: ')

        # Record attendance
        attendance_data = {
            'worker_id': worker_id,
            'timestamp': firebase_config.firestore.SERVER_TIMESTAMP,
            'type': 'in' if choice == '1' else 'out'
        }
        firebase_config.db.collection('attendance').add(attendance_data)
        print('Attendance recorded successfully!')
    except Exception as e:
        print('Error recording attendance:', str(e))

# Main loop
if __name__ == '__main__':
    print('Waiting for worker identification...')
    while True:
        try:
            # Try RFID first
            print('Place RFID card near reader...')
            rfid_id, _ = rfid.read()
            record_attendance(rfid_id)
            continue
        except:
            pass

        try:
            # Try fingerprint
            print('Place finger on sensor...')
            if (f.readImage() == True):
                f.convertImage(0x01)
                result = f.searchTemplate()
                if (result >= 0):
                    record_attendance(result)
        except Exception as e:
            print('Error:', str(e))

        time.sleep(1)
