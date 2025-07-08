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
        # Convert DD-MM-YYYY to YYYY-MM-DD
        dob_ymd = convert_date_format(dob)
        year, month, day = dob_ymd.split('-')
        
        # Define month mapping
        month_map = {
            '01': 'jan', '02': 'feb', '03': 'mar', '04': 'apr',
            '05': 'may', '06': 'jun', '07': 'jul', '08': 'aug',
            '09': 'sep', '10': 'oct', '11': 'nov', '12': 'dec'
        }
        
        return f"{year}{month_map[month]}{day}"
    except Exception as e:
        print(f"Error creating password: {str(e)}")
        return None

def load_dob(serial_number):
    """Load DOB from CSV"""
    try:
        # This gives the full path to the current file's directory (main/)
        script_dir = os.path.dirname(__file__)
        csv_path = os.path.join(script_dir, "certificates.csv")

        with open(csv_path, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['serial_number'].strip() == serial_number.strip():
                    return row['dob'].strip()
        
        print(f"Warning: Certificate {serial_number} not found in CSV")
        return None
    except FileNotFoundError:
        print("Error: certificates.csv file not found")
        return None
    except Exception as e:
        print(f"Error reading CSV: {str(e)}")
        return None

def encrypt_pdf(pdf_path, password):
    """Encrypt PDF using password and return encrypted data and key"""
    try:
        # Generate encryption key
        key = Fernet.generate_key()
        cipher_suite = Fernet(key)
        
        # Read PDF content
        with open(pdf_path, 'rb') as file:
            pdf_content = file.read()
        
        # Encrypt content
        encrypted_data = cipher_suite.encrypt(pdf_content)
        
        return encrypted_data, key
    except Exception as e:
        print(f"Error encrypting PDF: {str(e)}")
        return None, None

def decrypt_pdf(encrypted_data, key):
    """Decrypt PDF using key"""
    try:
        cipher_suite = Fernet(key)
        decrypted_data = cipher_suite.decrypt(encrypted_data)
        return decrypted_data
    except Exception as e:
        print(f"Error decrypting PDF: {str(e)}")
        return None

def generate_qr_code(data, serial_number):
    """Generate QR code and save as image file using serial number"""
    try:
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
        # Get base directory (i.e., project folder)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

        # Create full path to qr_codes directory outside main/
        output_dir = os.path.join(base_dir, 'qr_codes')
        os.makedirs(output_dir, exist_ok=True)

        # Use serial number as filename
        final_filename = os.path.join(output_dir, f"{serial_number}.png")

        # Save image
        qr_image.save(final_filename)
        
        # Create output directory if it doesn't exist
        #output_dir = "qr_codes"
        #os.makedirs(output_dir, exist_ok=True)
        
        # Use serial number as filename
        #final_filename = f"{output_dir}/{serial_number}.png"
        
        # Save image
        #qr_image.save(final_filename)


        print(f"QR code saved as: {final_filename}")
        return final_filename
    except Exception as e:
        print(f"Error generating QR code: {str(e)}")
        return None

def upload_to_firebase(data, filename):
    """Upload data to Firebase Storage"""
    try:
        bucket = storage.bucket()
        blob = bucket.blob(filename)
        
        if isinstance(data, bytes):
            blob.upload_from_string(data)
        else:
            blob.upload_from_string(data, content_type='application/octet-stream')
        
        print(f"Successfully uploaded {filename}")
        return True
    except Exception as e:
        print(f"Error uploading to Firebase: {str(e)}")
        return False

def download_from_firebase(filename):
    """Download data from Firebase Storage"""
    try:
        bucket = storage.bucket()
        blob = bucket.blob(filename)
        
        if not blob.exists():
            print(f"File {filename} not found in Firebase")
            return None
        
        return blob.download_as_bytes()
    except Exception as e:
        print(f"Error downloading from Firebase: {str(e)}")
        return None

def process_certificate(serial_number, pdf_path):
    """Main processing function"""
    try:
        # Load DOB from CSV
        dob = load_dob(serial_number)
        if not dob:
            print(f"Error: Certificate {serial_number} not found")
            return None
        
        # Convert DOB to easy password format
        easy_password = create_easy_password(dob)
        if not easy_password:
            print("Error: Could not create password")
            return None
        
        print(f"Generated password: {easy_password}")
        
        # Encrypt PDF
        encrypted_data, key = encrypt_pdf(pdf_path, easy_password)
        if not encrypted_data or not key:
            print("Error: Could not encrypt PDF")
            return None
        
        # Upload encrypted PDF to Firebase
        if not upload_to_firebase(encrypted_data, f'{serial_number}.pdf'):
            print("Error: Could not upload encrypted PDF")
            return None
        
        # Upload encryption key to Firebase
        if not upload_to_firebase(key, f'{easy_password}_key'):
            print("Error: Could not upload encryption key")
            return None
        
        # Generate QR code with verification URL
        qr_url = f'https://secure-cert.onrender.com/verify?serial={serial_number}'
        qr_filename = generate_qr_code(qr_url, serial_number)
        #qr_filename = generate_qr_code(qr_url, f"serial_{serial_number}")
        
        if qr_filename:
            print(f"Certificate processing completed successfully")
            print(f"QR Code: {qr_filename}")
            print(f"Verification URL: {qr_url}")
            return qr_filename
        else:
            print("Error: Could not generate QR code")
            return None
            
    except Exception as e:
        print(f"Error processing certificate: {str(e)}")
        return None

def verify_certificate(serial_number, dob):
    """Verify certificate and return decrypted PDF"""
    try:
        # Create password from DOB
        easy_password = create_easy_password(dob)
        if not easy_password:
            print("Error: Could not create password")
            return None
        
        # Download encrypted PDF from Firebase
        encrypted_data = download_from_firebase(f'{serial_number}.pdf')
        if not encrypted_data:
            print("Error: Could not download encrypted PDF")
            return None
        
        # Download encryption key from Firebase
        key = download_from_firebase(f'{easy_password}_key')
        if not key:
            print("Error: Could not download encryption key")
            return None
        
        # Decrypt PDF
        decrypted_data = decrypt_pdf(encrypted_data, key)
        if not decrypted_data:
            print("Error: Could not decrypt PDF")
            return None
        
        print("Certificate verified successfully")
        return decrypted_data
        
    except Exception as e:
        print(f"Error verifying certificate: {str(e)}")
        return None

def initialize_firebase():
    """Initialize Firebase"""
    try:
        if not firebase_admin._apps:
            # Load environment variables from .env
            load_dotenv()

            # Get the path from environment variable
            cred_path = os.getenv("FIREBASE_KEY_PATH")

            if not cred_path:
                raise ValueError("FIREBASE_KEY_PATH not set in .env file!")

            # Load Firebase credentials
            cred = credentials.Certificate(cred_path)
            #cred_path = os.environ.get("D:\Phind\firebase_key.json")
            #cred = credentials.Certificate(cred_path)
            #cred = credentials.Certificate('firebase_key.json')
            firebase_admin.initialize_app(cred, {
                'storageBucket': 'certificate-verify-7bab6.firebasestorage.app'
            })
        print("Firebase initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing Firebase: {str(e)}")
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