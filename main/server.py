from flask import Flask, request, render_template, jsonify, send_file
from flask_cors import CORS
import processor
import os
import tempfile
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize Firebase when server starts
if not processor.initialize_firebase():
    print("Warning: Firebase initialization failed")

@app.route('/', methods=['GET'])
def home():
    return """
    <h1>Certificate Verification System</h1>
    <p>Server is running!</p>
    <p>Endpoints:</p>
    <ul>
        <li>POST /process - Process and upload certificate</li>
        <li>POST /verify - Verify certificate</li>
        <li>GET /verify - Verification page</li>
    </ul>
    """

@app.route('/process', methods=['POST'])
def process_certificate():
    """Process certificate upload"""
    try:
        # Check if request has file
        if 'pdfFile' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No PDF file provided'
            }), 400
        
        file = request.files['pdfFile']
        serial_number = request.form.get('serialNumber')
        
        if not serial_number:
            return jsonify({
                'success': False,
                'error': 'Serial number is required'
            }), 400
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({
                'success': False,
                'error': 'Only PDF files are allowed'
            }), 400
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            file.save(temp_file.name)
            temp_file_path = temp_file.name
        
        try:
            # Process certificate
            qr_code_path = processor.process_certificate(serial_number, temp_file_path)
            
            if qr_code_path:
                return jsonify({
                    'success': True,
                    'message': 'Certificate processed successfully',
                    'qr_code_path': qr_code_path
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Certificate processing failed'
                }), 500
                
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except:
                pass
        
    except Exception as e:
        print(f"Error in /process: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/verify', methods=['GET'])
def verify_page():
    """Serve verification page"""
    try:
        # Read and serve the verify.html file
       # with open('verify.html', 'r', encoding='utf-8') as file:
        #    html_content = file.read()
        
        #return html_content, 200, {'Content-Type': 'text/html'}
        return render_template("verify.html")
    except FileNotFoundError:
        return """
        <h1>Verification Page</h1>
        <p>verify.html file not found. Please make sure the file exists in the same directory as server.py</p>
        """, 404

@app.route('/verify', methods=['POST'])
def verify_certificate():
    """Verify certificate"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400
        
        serial_number = data.get('serialNumber')
        dob = data.get('dob')
        
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
            return jsonify({
                'success': False,
                'error': 'Certificate verification failed. Please check your credentials.'
            }), 401
            
    except Exception as e:
        print(f"Error in /verify: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin', methods=['GET'])
def admin_page():
    """Serve admin page"""
    try:
        # Read and serve the admin.html file
        #with open('admin.html', 'r', encoding='utf-8') as file:
           # html_content = file.read()
        
        #return html_content, 200, {'Content-Type': 'text/html'}
        return render_template("admin.html")
    except FileNotFoundError:
        return """
        <h1>Admin Page</h1>
        <p>admin.html file not found. Please make sure the file exists in the same directory as server.py</p>
        """, 404

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
    print("Admin Interface: https://secure-cert.onrender.com/admin")   #http://localhost:5000/admin
    print("Verify Interface: https://secure-cert.onrender.com/verify")            # http://localhost:5000/verify
    print("API Endpoints:")
    print("  POST /process - Process certificates")
    print("  POST /verify - Verify certificates")
    print("="*50)
    
    # Check required files
    # This gives the full path to the current file's directory (main/)
    script_dir = os.path.dirname(__file__)
    csv_path = os.path.join(script_dir, "certificates.csv")

    required_files = [csv_path, 'firebase_key.json']
    for file in required_files:
        if not os.path.exists(file):
            print(f"WARNING: {file} not found!")
    
    port = int(os.environ.get("PORT", 5000))  # 5000 is fallback for local
    app.run(host='0.0.0.0', port=port, debug=True)