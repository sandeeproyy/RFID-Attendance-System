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

# Registration process
def register_worker():
    try:
        # Get worker details
        name = input('Enter worker name: ')

        # Capture fingerprint
        print('Place finger on sensor...')
        while (f.readImage() == False):
            pass
        f.convertImage(0x01)
        result = f.searchTemplate()
        if (result >= 0):
            print('Fingerprint already registered!')
            return
        f.createTemplate()
        fingerprint_data = f.downloadCharacteristics(0x01)

        # Capture RFID
        print('Place RFID card near reader...')
        rfid_id, _ = rfid.read()

        # Store in Firebase
        worker_data = {
            'name': name,
            'fingerprint': fingerprint_data,
            'rfid': rfid_id,
            'registered_at': firebase_config.firestore.SERVER_TIMESTAMP
        }
        firebase_config.db.collection('workers').document(str(rfid_id)).set(worker_data)
        print('Worker registered successfully!')
    except Exception as e:
        print('Error during registration:', str(e))

# Main loop
if __name__ == '__main__':
    while True:
        print('\n1. Register new worker')
        print('2. Exit')
        choice = input('Select option: ')
        if choice == '1':
            register_worker()
        elif choice == '2':
            break
