import os
import csv
import qrcode
from cryptography.fernet import Fernet
import base64
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, storage
import tempfile
from dotenv import load_dotenv
import traceback

def convert_date_format(date_str):
    """Convert date from DD-MM-YYYY to YYYY-MM-DD"""
    try:
        parts = date_str.split('-')
        if len(parts) == 3:
            day, month, year = parts
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        return date_str
    except Exception as e:
        print(f"Error converting date format: {str(e)}")
        return date_str

def create_easy_password(dob):
    """Convert DOB to an easier password format"""
    try:
        print(f"Creating password from DOB: {dob}")
        # Convert DD-MM-YYYY to YYYY-MM-DD
        dob_ymd = convert_date_format(dob)
        print(f"Converted DOB format: {dob_ymd}")
        
        year, month, day = dob_ymd.split('-')
        
        # Define month mapping
        month_map = {
            '01': 'jan', '02': 'feb', '03': 'mar', '04': 'apr',
            '05': 'may', '06': 'jun', '07': 'jul', '08': 'aug',
            '09': 'sep', '10': 'oct', '11': 'nov', '12': 'dec'
        }
        
        password = f"{year}{month_map[month]}{day}"
        print(f"Generated password: {password}")
        return password
    except Exception as e:
        print(f"Error creating password: {str(e)}")
        traceback.print_exc()
        return None

def load_dob(serial_number):
    """Load DOB from CSV with enhanced error handling"""
    try:
        print(f"Loading DOB for serial number: {serial_number}")
        
        # Get the current script directory
        script_dir = os.path.dirname(__file__)
        csv_path = os.path.join(script_dir, "certificates.csv")
        
        print(f"CSV path: {csv_path}")
        print(f"CSV exists: {os.path.exists(csv_path)}")
        
        if not os.path.exists(csv_path):
            print("ERROR: certificates.csv file not found")
            return None

        with open(csv_path, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            headers = reader.fieldnames
            print(f"CSV headers: {headers}")
            
            row_count = 0
            for row in reader:
                row_count += 1
                print(f"Row {row_count}: {row}")
                
                if row['serial_number'].strip() == serial_number.strip():
                    dob = row['dob'].strip()
                    print(f"Found matching certificate! DOB: {dob}")
                    return dob
            
            print(f"Warning: Certificate {serial_number} not found in CSV (checked {row_count} rows)")
            return None
            
    except FileNotFoundError:
        print("Error: certificates.csv file not found")
        return None
    except Exception as e:
        print(f"Error reading CSV: {str(e)}")
        traceback.print_exc()
        return None

def encrypt_pdf(pdf_path, password):
    """Encrypt PDF using password and return encrypted data and key"""
    try:
        print(f"Encrypting PDF: {pdf_path}")
        print(f"PDF exists: {os.path.exists(pdf_path)}")
        
        if not os.path.exists(pdf_path):
            print("ERROR: PDF file not found")
            return None, None
        
        # Generate encryption key
        key = Fernet.generate_key()
        cipher_suite = Fernet(key)
        
        # Read PDF content
        with open(pdf_path, 'rb') as file:
            pdf_content = file.read()
        
        print(f"PDF content size: {len(pdf_content)} bytes")
        
        # Encrypt content
        encrypted_data = cipher_suite.encrypt(pdf_content)
        print(f"Encrypted data size: {len(encrypted_data)} bytes")
        
        return encrypted_data, key
    except Exception as e:
        print(f"Error encrypting PDF: {str(e)}")
        traceback.print_exc()
        return None, None

def decrypt_pdf(encrypted_data, key):
    """Decrypt PDF using key"""
    try:
        print(f"Decrypting PDF data (size: {len(encrypted_data)} bytes)")
        cipher_suite = Fernet(key)
        decrypted_data = cipher_suite.decrypt(encrypted_data)
        print(f"Decrypted data size: {len(decrypted_data)} bytes")
        return decrypted_data
    except Exception as e:
        print(f"Error decrypting PDF: {str(e)}")
        traceback.print_exc()
        return None

def generate_qr_code(data, serial_number):
    """Generate QR code and upload to Firebase Storage"""
    try:
        print(f"Generating QR code for serial: {serial_number}")
        print(f"QR code data: {data}")
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # Create QR code image
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Save to temporary file first
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
            qr_image.save(temp_file.name)
            temp_file_path = temp_file.name
        
        print(f"QR code saved to temp file: {temp_file_path}")
        
        try:
            # Upload to Firebase Storage
            with open(temp_file_path, 'rb') as qr_file:
                qr_data = qr_file.read()
            
            print(f"QR code file size: {len(qr_data)} bytes")
            
            qr_filename = f"qr_codes/{serial_number}.png"
            if upload_to_firebase(qr_data, qr_filename):
                print(f"QR code uploaded to Firebase: {qr_filename}")
                return qr_filename
            else:
                print("Failed to upload QR code to Firebase")
                return None
                
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except:
                pass
                
    except Exception as e:
        print(f"Error generating QR code: {str(e)}")
        traceback.print_exc()
        return None

def upload_to_firebase(data, filename):
    """Upload data to Firebase Storage with enhanced error handling"""
    try:
        print(f"Uploading to Firebase: {filename}")
        print(f"Data size: {len(data)} bytes")
        
        if not firebase_admin._apps:
            print("ERROR: Firebase not initialized")
            return False
        
        bucket = storage.bucket()
        print(f"Got Firebase bucket: {bucket.name}")
        
        blob = bucket.blob(filename)
        
        if isinstance(data, bytes):
            blob.upload_from_string(data)
        else:
            blob.upload_from_string(data, content_type='application/octet-stream')
        
        print(f"Successfully uploaded {filename}")
        return True
        
    except Exception as e:
        print(f"Error uploading to Firebase: {str(e)}")
        traceback.print_exc()
        return False

def download_from_firebase(filename):
    """Download data from Firebase Storage with enhanced error handling"""
    try:
        print(f"Downloading from Firebase: {filename}")
        
        if not firebase_admin._apps:
            print("ERROR: Firebase not initialized")
            return None
        
        bucket = storage.bucket()
        blob = bucket.blob(filename)
        
        if not blob.exists():
            print(f"File {filename} not found in Firebase")
            return None
        
        data = blob.download_as_bytes()
        print(f"Downloaded {filename} ({len(data)} bytes)")
        return data
        
    except Exception as e:
        print(f"Error downloading from Firebase: {str(e)}")
        traceback.print_exc()
        return None

def process_certificate(serial_number, pdf_path):
    """Main processing function with enhanced error handling"""
    try:
        print(f"=== PROCESSING CERTIFICATE ===")
        print(f"Serial Number: {serial_number}")
        print(f"PDF Path: {pdf_path}")
        print(f"PDF exists: {os.path.exists(pdf_path)}")
        
        if not os.path.exists(pdf_path):
            print(f"ERROR: PDF file not found at {pdf_path}")
            return None
        
        # Check Firebase initialization
        if not firebase_admin._apps:
            print("ERROR: Firebase not initialized")
            return None
        
        # Load DOB from CSV
        print("Step 1: Loading DOB from CSV...")
        dob = load_dob(serial_number)
        if not dob:
            print(f"ERROR: Certificate {serial_number} not found in CSV")
            return None
        
        print(f"Found DOB: {dob}")
        
        # Convert DOB to easy password format
        print("Step 2: Creating password from DOB...")
        easy_password = create_easy_password(dob)
        if not easy_password:
            print("ERROR: Could not create password from DOB")
            return None
        
        print(f"Generated password: {easy_password}")
        
        # Encrypt PDF
        print("Step 3: Encrypting PDF...")
        encrypted_data, key = encrypt_pdf(pdf_path, easy_password)
        if not encrypted_data or not key:
            print("ERROR: Could not encrypt PDF")
            return None
        
        print("PDF encrypted successfully")
        
        # Upload encrypted PDF to Firebase
        print("Step 4: Uploading encrypted PDF to Firebase...")
        if not upload_to_firebase(encrypted_data, f'{serial_number}.pdf'):
            print("ERROR: Could not upload encrypted PDF to Firebase")
            return None
        
        print("Encrypted PDF uploaded successfully")
        
        # Upload encryption key to Firebase
        print("Step 5: Uploading encryption key to Firebase...")
        if not upload_to_firebase(key, f'{easy_password}_key'):
            print("ERROR: Could not upload encryption key to Firebase")
            return None
        
        print("Encryption key uploaded successfully")
        
        # Generate QR code with verification URL
        print("Step 6: Generating QR code...")
        qr_url = f'https://secure-cert.onrender.com/verify?serial={serial_number}'
        qr_filename = generate_qr_code(qr_url, serial_number)
        
        if qr_filename:
            print(f"=== PROCESSING COMPLETED SUCCESSFULLY ===")
            print(f"QR Code: {qr_filename}")
            print(f"Verification URL: {qr_url}")
            return qr_filename
        else:
            print("ERROR: Could not generate QR code")
            return None
            
    except Exception as e:
        print(f"ERROR in process_certificate: {str(e)}")
        traceback.print_exc()
        return None

def verify_certificate(serial_number, dob):
    """Verify certificate and return decrypted PDF with enhanced error handling"""
    try:
        print(f"=== VERIFYING CERTIFICATE ===")
        print(f"Serial Number: {serial_number}")
        print(f"DOB: {dob}")
        
        # Check Firebase initialization
        if not firebase_admin._apps:
            print("ERROR: Firebase not initialized")
            return None
        
        # Create password from DOB
        easy_password = create_easy_password(dob)
        if not easy_password:
            print("Error: Could not create password")
            return None
        
        # Download encrypted PDF from Firebase
        print("Step 1: Downloading encrypted PDF...")
        encrypted_data = download_from_firebase(f'{serial_number}.pdf')
        if not encrypted_data:
            print("Error: Could not download encrypted PDF")
            return None
        
        # Download encryption key from Firebase
        print("Step 2: Downloading encryption key...")
        key = download_from_firebase(f'{easy_password}_key')
        if not key:
            print("Error: Could not download encryption key")
            return None
        
        # Decrypt PDF
        print("Step 3: Decrypting PDF...")
        decrypted_data = decrypt_pdf(encrypted_data, key)
        if not decrypted_data:
            print("Error: Could not decrypt PDF")
            return None
        
        print("=== CERTIFICATE VERIFIED SUCCESSFULLY ===")
        return decrypted_data
        
    except Exception as e:
        print(f"Error verifying certificate: {str(e)}")
        traceback.print_exc()
        return None

def initialize_firebase():
    """Initialize Firebase with enhanced error handling"""
    try:
        print("=== INITIALIZING FIREBASE ===")
        
        if firebase_admin._apps:
            print("Firebase already initialized")
            return True
        
        # Load environment variables from .env
        load_dotenv()
        print("Environment variables loaded")

        # Get the path from environment variable
        cred_path = os.getenv("FIREBASE_KEY_PATH")
        print(f"Firebase key path from env: {cred_path}")

        if not cred_path:
            print("ERROR: FIREBASE_KEY_PATH not set in environment variables!")
            print("Available environment variables:")
            for key, value in os.environ.items():
                if 'FIREBASE' in key.upper():
                    print(f"  {key}: {value}")
            return False

        # Check if credentials file exists
        if not os.path.exists(cred_path):
            print(f"ERROR: Firebase credentials file not found at: {cred_path}")
            print(f"Current directory: {os.getcwd()}")
            print(f"Files in current directory: {os.listdir('.')}")
            return False

        print("Loading Firebase credentials...")
        # Load Firebase credentials
        cred = credentials.Certificate(cred_path)
        
        print("Initializing Firebase app...")
        firebase_admin.initialize_app(cred, {
            'storageBucket': 'certificate-verify-7bab6.firebasestorage.app'
        })
        
        print("=== FIREBASE INITIALIZED SUCCESSFULLY ===")
        return True
        
    except Exception as e:
        print(f"ERROR initializing Firebase: {str(e)}")
        traceback.print_exc()
        return False

# Test function
if __name__ == '__main__':
    try:
        # Initialize Firebase
        if not initialize_firebase():
            print("Failed to initialize Firebase")
            exit(1)
        
        # Test processing
        result = process_certificate('SERIAL0001', 'test.pdf')
        if result:
            print("Certificate processing completed successfully")
        else:
            print("Certificate processing failed")
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()