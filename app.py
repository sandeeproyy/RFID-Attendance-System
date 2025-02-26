from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import firebase_config
import psutil
from datetime import datetime
import time
import threading
import RPi.GPIO as GPIO
from pyfingerprint.pyfingerprint import PyFingerprint
from mfrc522 import SimpleMFRC522

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Initialize hardware
fingerprint_scanner = None
rfid_reader = None
registration_active = False
attendance_active = False
current_registration = {'name': None, 'fingerprint': None, 'rfid': None}
attendance_mode = 'in'  # Default to clock-in

# Status variables for real-time updates
last_detected_worker = None
last_action = None

def initialize_hardware():
    global fingerprint_scanner, rfid_reader
    try:
        # Initialize fingerprint sensor
        fingerprint_scanner = PyFingerprint('/dev/ttyUSB0', 57600, 0xFFFFFFFF, 0x00000000)
        if not fingerprint_scanner.verifyPassword():
            raise ValueError('Fingerprint sensor password verification failed!')
        print('Fingerprint sensor initialized successfully!')
        
        # Initialize RFID reader
        rfid_reader = SimpleMFRC522()
        print('RFID reader initialized successfully!')
        
        # Set up GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        
        # Success indicator LED (optional)
        GPIO.setup(18, GPIO.OUT)  # Green LED
        GPIO.setup(17, GPIO.OUT)  # Red LED
        
        # Flash LEDs to indicate successful initialization
        for _ in range(3):
            GPIO.output(18, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(18, GPIO.LOW)
            GPIO.output(17, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(17, GPIO.LOW)
            
    except Exception as e:
        print('Error initializing hardware:', str(e))
        return False
    return True

def register_fingerprint():
    global current_registration
    try:
        print('Place finger on sensor for registration...')
        # Wait for finger placement
        while not fingerprint_scanner.readImage():
            time.sleep(0.1)
            
        # Convert and check if fingerprint already exists
        fingerprint_scanner.convertImage(0x01)
        result = fingerprint_scanner.searchTemplate()
        position_number, accuracy = result
        
        if position_number >= 0:
            print(f'Fingerprint already exists at position #{position_number} with accuracy {accuracy}!')
            current_registration['fingerprint'] = None
            return False, f'Fingerprint already registered (ID: {position_number})'
            
        # Create template
        fingerprint_scanner.convertImage(0x01)
        
        # Place finger second time
        print('Remove finger...')
        time.sleep(2)
        print('Place same finger again...')
        
        while not fingerprint_scanner.readImage():
            time.sleep(0.1)
            
        # Convert second scan
        fingerprint_scanner.convertImage(0x02)
        
        # Compare templates
        if fingerprint_scanner.compareCharacteristics() == 0:
            return False, 'Fingerprints do not match! Try again.'
            
        # Create and store template
        fingerprint_scanner.createTemplate()
        
        # Find free position
        position = fingerprint_scanner.getTemplateCount()
        
        # Store template at new position
        fingerprint_scanner.storeTemplate(position)
        
        print(f'Fingerprint stored at position #{position}')
        current_registration['fingerprint'] = position
        
        # Success indicator
        GPIO.output(18, GPIO.HIGH)  # Green LED
        time.sleep(1)
        GPIO.output(18, GPIO.LOW)
        
        return True, f'Fingerprint registered successfully (ID: {position})'
        
    except Exception as e:
        print('Error during fingerprint registration:', str(e))
        # Error indicator
        GPIO.output(17, GPIO.HIGH)  # Red LED
        time.sleep(1)
        GPIO.output(17, GPIO.LOW)
        return False, f'Error: {str(e)}'

def register_rfid():
    global current_registration
    try:
        print('Place RFID card near reader...')
        rfid_id, text = rfid_reader.read()
        
        # Check if RFID already exists
        worker_ref = firebase_config.db.collection('workers').document(str(rfid_id))
        worker = worker_ref.get()
        
        if worker.exists:
            print(f'RFID already registered: {rfid_id}')
            current_registration['rfid'] = None
            return False, f'RFID already registered (ID: {rfid_id})'
            
        current_registration['rfid'] = rfid_id
        
        # Success indicator
        GPIO.output(18, GPIO.HIGH)  # Green LED
        time.sleep(1)
        GPIO.output(18, GPIO.LOW)
        
        return True, f'RFID registered successfully (ID: {rfid_id})'
        
    except Exception as e:
        print('Error during RFID registration:', str(e))
        # Error indicator
        GPIO.output(17, GPIO.HIGH)  # Red LED
        time.sleep(1)
        GPIO.output(17, GPIO.LOW)
        return False, f'Error: {str(e)}'

def complete_registration():
    global current_registration
    try:
        if not current_registration['name']:
            return False, 'Worker name is required'
            
        if not current_registration['fingerprint'] and not current_registration['rfid']:
            return False, 'Either fingerprint or RFID is required'
            
        # Store in Firebase
        worker_data = {
            'name': current_registration['name'],
            'fingerprint_id': current_registration['fingerprint'],
            'rfid': current_registration['rfid'],
            'registered_at': firebase_config.firestore.SERVER_TIMESTAMP
        }
        
        # Use RFID as document ID if available, otherwise use fingerprint ID
        doc_id = str(current_registration['rfid']) if current_registration['rfid'] else f"fp_{current_registration['fingerprint']}"
        
        firebase_config.db.collection('workers').document(doc_id).set(worker_data)
        print('Worker registered successfully!')
        
        # Reset registration data
        temp_name = current_registration['name']
        current_registration = {'name': None, 'fingerprint': None, 'rfid': None}
        
        return True, f'Worker {temp_name} registered successfully!'
        
    except Exception as e:
        print('Error completing registration:', str(e))
        return False, f'Error: {str(e)}'

def identify_worker(identifier_type, identifier_value):
    try:
        if identifier_type == 'rfid':
            worker_ref = firebase_config.db.collection('workers').document(str(identifier_value))
            worker = worker_ref.get()
            if worker.exists:
                return worker.to_dict(), worker.id
        elif identifier_type == 'fingerprint':
            # Query workers with matching fingerprint ID
            workers = firebase_config.db.collection('workers').where('fingerprint_id', '==', identifier_value).limit(1).stream()
            for worker in workers:
                return worker.to_dict(), worker.id
                
        return None, None
    except Exception as e:
        print(f'Error identifying worker: {str(e)}')
        return None, None

def record_attendance(worker_id, worker_data):
    global last_detected_worker, last_action, attendance_mode
    
    try:
        # Get current time
        now = datetime.now()
        
        # Record attendance
        attendance_data = {
            'worker_id': worker_id,
            'worker_name': worker_data.get('name', 'Unknown'),
            'timestamp': firebase_config.firestore.SERVER_TIMESTAMP,
            'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
            'type': attendance_mode
        }
        
        # Add to attendance collection
        firebase_config.db.collection('attendance').add(attendance_data)
        
        # Update last detected worker for UI
        last_detected_worker = worker_data
        last_action = f"Clocked {attendance_mode} at {now.strftime('%H:%M:%S')}"
        
        # Success indicator
        GPIO.output(18, GPIO.HIGH)  # Green LED
        time.sleep(1)
        GPIO.output(18, GPIO.LOW)
        
        print(f'Attendance recorded successfully for {worker_data.get("name", "Unknown")}!')
        return True, f'{worker_data.get("name", "Unknown")} clocked {attendance_mode} successfully!'
        
    except Exception as e:
        print('Error recording attendance:', str(e))
        # Error indicator
        GPIO.output(17, GPIO.HIGH)  # Red LED
        time.sleep(1)
        GPIO.output(17, GPIO.LOW)
        return False, f'Error: {str(e)}'

# Hardware monitoring threads
def registration_process():
    global registration_active
    while registration_active:
        time.sleep(0.5)  # Short sleep to prevent CPU overuse
        # Registration is handled by API endpoints, not in this thread

def attendance_process():
    global attendance_active, last_detected_worker, last_action
    
    while attendance_active:
        try:
            # Try RFID first
            try:
                rfid_id, _ = rfid_reader.read_no_block()
                if rfid_id:
                    worker_data, worker_id = identify_worker('rfid', rfid_id)
                    if worker_data:
                        success, message = record_attendance(worker_id, worker_data)
                        time.sleep(3)  # Prevent multiple scans
            except Exception as rfid_err:
                pass
                
            # Try fingerprint
            try:
                if fingerprint_scanner.readImage():
                    fingerprint_scanner.convertImage(0x01)
                    result = fingerprint_scanner.searchTemplate()
                    position, accuracy = result
                    
                    if position >= 0:
                        worker_data, worker_id = identify_worker('fingerprint', position)
                        if worker_data:
                            success, message = record_attendance(worker_id, worker_data)
                            time.sleep(3)  # Prevent multiple scans
            except Exception as fp_err:
                pass
                
        except Exception as e:
            print('Attendance error:', str(e))
            
        time.sleep(0.5)  # Short sleep to prevent CPU overuse

# Routes
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Get battery percentage
    battery = psutil.sensors_battery()
    battery_percent = battery.percent if battery else 'N/A'
    
    # Get workers
    workers = firebase_config.db.collection('workers').stream()
    workers_list = [{'id': worker.id, **worker.to_dict()} for worker in workers]
    
    # Get attendance records
    attendance = firebase_config.db.collection('attendance').order_by('timestamp', direction='DESC').limit(50).stream()
    attendance_list = [record.to_dict() for record in attendance]
    
    return render_template('dashboard.html', 
                         battery_percent=battery_percent,
                         workers=workers_list,
                         attendance=attendance_list,
                         registration_active=registration_active,
                         attendance_active=attendance_active,
                         current_registration=current_registration,
                         attendance_mode=attendance_mode)

@app.route('/registration')
def registration():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('registration.html', 
                         current_registration=current_registration)

@app.route('/attendance')
def attendance():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('attendance.html', 
                         attendance_mode=attendance_mode,
                         last_detected_worker=last_detected_worker,
                         last_action=last_action)

@app.route('/api/set_worker_name', methods=['POST'])
def set_worker_name():
    global current_registration
    
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    data = request.json
    current_registration['name'] = data.get('name')
    
    return jsonify({
        'success': True, 
        'message': f'Worker name set to {current_registration["name"]}',
        'current_registration': current_registration
    })

@app.route('/api/register_fingerprint', methods=['POST'])
def api_register_fingerprint():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    success, message = register_fingerprint()
    
    return jsonify({
        'success': success, 
        'message': message,
        'current_registration': current_registration
    })

@app.route('/api/register_rfid', methods=['POST'])
def api_register_rfid():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    success, message = register_rfid()
    
    return jsonify({
        'success': success, 
        'message': message,
        'current_registration': current_registration
    })

@app.route('/api/complete_registration', methods=['POST'])
def api_complete_registration():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    success, message = complete_registration()
    
    return jsonify({
        'success': success, 
        'message': message,
        'current_registration': current_registration
    })

@app.route('/api/toggle_attendance_mode', methods=['POST'])
def toggle_attendance_mode():
    global attendance_mode
    
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    # Toggle between 'in' and 'out'
    attendance_mode = 'out' if attendance_mode == 'in' else 'in'
    
    return jsonify({
        'success': True, 
        'message': f'Attendance mode set to: {attendance_mode}',
        'attendance_mode': attendance_mode
    })

@app.route('/api/get_status')
def get_status():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    return jsonify({
        'success': True,
        'registration_active': registration_active,
        'attendance_active': attendance_active,
        'attendance_mode': attendance_mode,
        'last_detected_worker': last_detected_worker,
        'last_action': last_action,
        'current_registration': current_registration
    })

@app.route('/toggle_registration')
def toggle_registration():
    global registration_active
    
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    registration_active = not registration_active
    
    if registration_active:
        # Start registration thread if not already running
        for thread in threading.enumerate():
            if thread.name == 'registration_thread':
                break
        else:
            thread = threading.Thread(target=registration_process, name='registration_thread')
            thread.daemon = True
            thread.start()
    
    return redirect(url_for('dashboard'))

@app.route('/toggle_attendance')
def toggle_attendance():
    global attendance_active
    
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    attendance_active = not attendance_active
    
    if attendance_active:
        # Start attendance thread if not already running
        for thread in threading.enumerate():
            if thread.name == 'attendance_thread':
                break
        else:
            thread = threading.Thread(target=attendance_process, name='attendance_thread')
            thread.daemon = True
            thread.start()
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    if initialize_hardware():
        print("Hardware initialized successfully!")
    else:
        print("Hardware initialization failed! Some features may not work correctly.")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)