from flask import Flask, request, render_template, jsonify, send_file
from flask_cors import CORS
import processor
import os
import tempfile
import json
import traceback

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize Firebase when server starts
firebase_init_success = processor.initialize_firebase()
if not firebase_init_success:
    print("ERROR: Firebase initialization failed - this will cause processing to fail")

@app.route('/', methods=['GET'])
def home():
    return """
    <h1>Certificate Verification System</h1>
    <p>Server is running!</p>
    <p>Firebase Status: {}</p>
    <p>Endpoints:</p>
    <ul>
        <li>POST /process - Process and upload certificate</li>
        <li>POST /verify - Verify certificate</li>
        <li>GET /verify - Verification page</li>
    </ul>
    """.format("Connected" if firebase_init_success else "Failed to connect")

@app.route('/process', methods=['POST'])
def process_certificate():
    """Process certificate upload with enhanced error logging"""
    try:
        print("=== Starting certificate processing ===")
        
        # Check Firebase status first
        if not firebase_init_success:
            print("ERROR: Firebase not initialized - cannot process certificates")
            return jsonify({
                'success': False,
                'error': 'Firebase connection failed - service unavailable'
            }), 503
        
        # Check if request has file
        if 'pdfFile' not in request.files:
            print("ERROR: No PDF file provided in request")
            return jsonify({
                'success': False,
                'error': 'No PDF file provided'
            }), 400
        
        file = request.files['pdfFile']
        serial_number = request.form.get('serialNumber')
        
        print(f"Serial number: {serial_number}")
        print(f"File name: {file.filename}")
        print(f"File size: {len(file.read())} bytes")
        file.seek(0)  # Reset file pointer after reading size
        
        if not serial_number:
            print("ERROR: No serial number provided")
            return jsonify({
                'success': False,
                'error': 'Serial number is required'
            }), 400
        
        if file.filename == '':
            print("ERROR: No file selected")
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        if not file.filename.lower().endswith('.pdf'):
            print("ERROR: File is not a PDF")
            return jsonify({
                'success': False,
                'error': 'Only PDF files are allowed'
            }), 400
        
        print("Creating temporary file...")
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            file.save(temp_file.name)
            temp_file_path = temp_file.name
        
        print(f"Temporary file created: {temp_file_path}")
        print(f"Temp file size: {os.path.getsize(temp_file_path)} bytes")
        
        try:
            print("Calling processor.process_certificate...")
            # Process certificate with enhanced error handling
            qr_code_path = processor.process_certificate(serial_number, temp_file_path)
            
            if qr_code_path:
                print("Certificate processing successful!")
                return jsonify({
                    'success': True,
                    'message': 'Certificate processed successfully',
                    'qr_code_path': qr_code_path
                }), 200
            else:
                print("Certificate processing failed - no QR code path returned")
                return jsonify({
                    'success': False,
                    'error': 'Certificate processing failed - check server logs for details'
                }), 500
                
        finally:
            # Clean up temporary file
            try:
                print(f"Cleaning up temporary file: {temp_file_path}")
                os.unlink(temp_file_path)
            except Exception as cleanup_error:
                print(f"Error cleaning up temp file: {cleanup_error}")
        
    except Exception as e:
        print(f"ERROR in /process endpoint: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/verify', methods=['GET'])
def verify_page():
    """Serve verification page"""
    try:
        return render_template("verify.html")
    except Exception as e:
        print(f"Error serving verify page: {str(e)}")
        return f"""
        <h1>Verification Page</h1>
        <p>Error loading verification page: {str(e)}</p>
        """, 500

@app.route('/verify', methods=['POST'])
def verify_certificate():
    """Verify certificate with enhanced error handling"""
    try:
        print("=== Starting certificate verification ===")
        
        # Check Firebase status first
        if not firebase_init_success:
            print("ERROR: Firebase not initialized - cannot verify certificates")
            return jsonify({
                'success': False,
                'error': 'Firebase connection failed - service unavailable'
            }), 503
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400
        
        serial_number = data.get('serialNumber')
        dob = data.get('dob')
        
        print(f"Verification request - Serial: {serial_number}, DOB: {dob}")
        
        if not serial_number or not dob:
            return jsonify({
                'success': False,
                'error': 'Serial number and date of birth are required'
            }), 400
        
        # Validate DOB format (DD-MM-YYYY)
        import re
        if not re.match(r'^\d{2}-\d{2}-\d{4}$', dob):
            return jsonify({
                'success': False,
                'error': 'Date of birth must be in DD-MM-YYYY format'
            }), 400
        
        # Verify certificate
        decrypted_pdf = processor.verify_certificate(serial_number, dob)
        
        if decrypted_pdf:
            print("Certificate verification successful!")
            # Create temporary file for decrypted PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(decrypted_pdf)
                temp_file_path = temp_file.name
            
            try:
                # Return decrypted PDF
                return send_file(temp_file_path, mimetype='application/pdf')
            finally:
                # Schedule cleanup of temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
        else:
            print("Certificate verification failed")
            return jsonify({
                'success': False,
                'error': 'Certificate verification failed. Please check your credentials.'
            }), 401
            
    except Exception as e:
        print(f"Error in /verify: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Verification error: {str(e)}'
        }), 500

@app.route('/admin', methods=['GET'])
def admin_page():
    """Serve admin page"""
    try:
        return render_template("admin.html")
    except Exception as e:
        print(f"Error serving admin page: {str(e)}")
        return f"""
        <h1>Admin Page</h1>
        <p>Error loading admin page: {str(e)}</p>
        """, 500

@app.route('/debug', methods=['GET'])
def debug_info():
    """Debug endpoint to check system status"""
    try:
        script_dir = os.path.dirname(__file__)
        csv_path = os.path.join(script_dir, "certificates.csv")
        
        debug_info = {
            'firebase_initialized': firebase_init_success,
            'csv_exists': os.path.exists(csv_path),
            'firebase_key_exists': os.path.exists('firebase_key.json'),
            'environment_vars': {
                'FIREBASE_KEY_PATH': os.getenv('FIREBASE_KEY_PATH'),
                'PORT': os.getenv('PORT')
            },
            'current_directory': os.getcwd(),
            'files_in_directory': os.listdir('.'),
            'csv_path': csv_path
        }
        
        return jsonify(debug_info), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    print("="*50)
    print("Certificate Verification System Server")
    print("="*50)
    print("Server starting...")
    print("Admin Interface: https://secure-cert.onrender.com/admin")
    print("Verify Interface: https://secure-cert.onrender.com/verify")
    print("Debug Interface: https://secure-cert.onrender.com/debug")
    print("API Endpoints:")
    print("  POST /process - Process certificates")
    print("  POST /verify - Verify certificates")
    print("  GET /debug - Debug information")
    print("="*50)
    
    # Check required files
    script_dir = os.path.dirname(__file__)
    csv_path = os.path.join(script_dir, "certificates.csv")
    
    required_files = [csv_path, 'firebase_key.json']
    for file in required_files:
        if not os.path.exists(file):
            print(f"WARNING: {file} not found!")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)