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
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
from PyPDF2 import PdfReader, PdfWriter

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
            if upload_to_firebase(qr_data, qr_filename, content_type='image/png'):
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

def upload_to_firebase(data, filename, content_type=None):
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
            if content_type:
                blob.upload_from_string(data, content_type=content_type)
            else:
                blob.upload_from_string(data)
        else:
            blob.upload_from_string(data, content_type=content_type or 'application/octet-stream')
        
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
    """Main processing function with QR code embedding"""
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
        
        # Generate QR code with verification URL
        print("Step 3: Generating QR code...")
        qr_url = f'https://secure-cert.onrender.com/verify?serial={serial_number}'
        qr_code_data = generate_qr_code_data(qr_url, serial_number)
        
        if not qr_code_data:
            print("ERROR: Could not generate QR code")
            return None
        
        print("QR code generated successfully")
        
        # Embed QR code in PDF
        print("Step 4: Embedding QR code in PDF...")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf_path = temp_pdf.name
        
        try:
            if not embed_qr_in_pdf(pdf_path, qr_code_data, temp_pdf_path):
                print("ERROR: Could not embed QR code in PDF")
                return None
            
            print("QR code embedded successfully")
            
            # Encrypt the modified PDF
            print("Step 5: Encrypting PDF with embedded QR code...")
            encrypted_data, key = encrypt_pdf(temp_pdf_path, easy_password)
            if not encrypted_data or not key:
                print("ERROR: Could not encrypt PDF")
                return None
            
            print("PDF encrypted successfully")
            
            # Upload encrypted PDF to Firebase
            print("Step 6: Uploading encrypted PDF to Firebase...")
            if not upload_to_firebase(encrypted_data, f'{serial_number}.pdf', content_type='application/pdf'):
                print("ERROR: Could not upload encrypted PDF to Firebase")
                return None
            
            print("Encrypted PDF uploaded successfully")
            
            # Upload encryption key to Firebase
            print("Step 7: Uploading encryption key to Firebase...")
            if not upload_to_firebase(key, f'{easy_password}_key', content_type='application/octet-stream'):
                print("ERROR: Could not upload encryption key to Firebase")
                return None
            
            print("Encryption key uploaded successfully")
            
            # Upload QR code image to Firebase for reference
            print("Step 8: Uploading QR code image to Firebase...")
            qr_filename = f"qr_codes/{serial_number}.png"
            if not upload_to_firebase(qr_code_data, qr_filename, content_type='image/png'):
                print("WARNING: Could not upload QR code image to Firebase")
                # This is not a critical error, continue processing
            
            print(f"=== PROCESSING COMPLETED SUCCESSFULLY ===")
            print(f"QR Code embedded in PDF")
            print(f"Verification URL: {qr_url}")
            return qr_filename
            
        finally:
            # Clean up temporary PDF file
            try:
                os.unlink(temp_pdf_path)
            except:
                pass
                
    except Exception as e:
        print(f"ERROR in process_certificate: {str(e)}")
        traceback.print_exc()
        return None


def generate_qr_code_data(data, serial_number):
    """Generate QR code and return image data as bytes"""
    try:
        print(f"Generating QR code data for serial: {serial_number}")
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
        
        # Convert to bytes
        img_byte_arr = io.BytesIO()
        qr_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        qr_data = img_byte_arr.getvalue()
        print(f"QR code data generated: {len(qr_data)} bytes")
        
        return qr_data
        
    except Exception as e:
        print(f"Error generating QR code data: {str(e)}")
        traceback.print_exc()
        return None


def embed_qr_in_pdf(pdf_path, qr_image_data, output_path):
    """Embed QR code in top-right corner of PDF"""
    try:
        print(f"Embedding QR code in PDF: {pdf_path}")
        
        # Read the original PDF
        pdf_reader = PdfReader(pdf_path)
        pdf_writer = PdfWriter()
        
        # Create QR code overlay
        qr_overlay = create_qr_overlay(qr_image_data)
        
        if not qr_overlay:
            print("ERROR: Could not create QR overlay")
            return False
        
        # Process each page (or just the first page)
        for page_num, page in enumerate(pdf_reader.pages):
            if page_num == 0:  # Only add QR to first page
                # Merge QR overlay with the page
                page.merge_page(qr_overlay)
            pdf_writer.add_page(page)
        
        # Write the modified PDF
        with open(output_path, 'wb') as output_file:
            pdf_writer.write(output_file)
        
        print(f"QR code embedded successfully: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error embedding QR code: {str(e)}")
        traceback.print_exc()
        return False


def create_qr_overlay(qr_image_data):
    """Create QR code overlay for PDF"""
    try:
        # Create a BytesIO buffer for the overlay PDF
        packet = io.BytesIO()
        
        # Create canvas for overlay
        c = canvas.Canvas(packet, pagesize=letter)
        width, height = letter
        
        # Save QR image temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_qr:
            temp_qr.write(qr_image_data)
            temp_qr_path = temp_qr.name
        
        try:
            # Position QR code in top-right corner
            qr_size = 80  # Size of QR code
            x_position = width - qr_size - 20  # 20 pixels from right edge
            y_position = height - qr_size - 20  # 20 pixels from top
            
            # Draw QR code on canvas
            c.drawImage(temp_qr_path, x_position, y_position, qr_size, qr_size)
            c.save()
            
            # Move to beginning of BytesIO buffer
            packet.seek(0)
            
            # Create PDF from overlay
            overlay_pdf = PdfReader(packet)
            return overlay_pdf.pages[0]
            
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_qr_path)
            except:
                pass
                
    except Exception as e:
        print(f"Error creating QR overlay: {str(e)}")
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