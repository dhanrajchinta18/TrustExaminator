# TrustExaminator

TrustExaminator is a blockchain-based document verification and management system designed for educational institutions. It leverages encryption and blockchain technology to ensure the authenticity, integrity, and security of academic documents such as question papers and syllabi.

## Features
- **Blockchain Integration:** Secure and immutable record-keeping for document transactions.
- **Encryption:** Robust encryption for sensitive files and keys.
- **User Roles:** Supports multiple user roles (e.g., admin, superintendent, teacher).
- **Document Management:** Upload, encrypt, and verify academic documents.
- **Transaction History:** Track all document-related activities.

## Project Structure
- `clgproject/` – Django project settings and configuration
- `EMS/` – Main application logic (encryption, blockchain, models, views)
- `media/` – Uploaded and encrypted files
- `static/` – Static assets (CSS, images)
- `templates/` – HTML templates
- `manage.py` – Django management script
- `requirements.txt` – Python dependencies
- `TrusExaminatorBlockchain` - Blockchain contracts and logic.

## Getting Started

### Prerequisites
- Python 3.8+
- pip
- Django
- Ganache
- IPFS

### Installation
1. Clone the repository:
   ```sh
   git clone <repo-url>
   cd TrustExaminatorv1
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Run migrations:
   ```sh
   python manage.py migrate
   ```
4. Start the development server:
   ```sh
   python manage.py runserver
   ```

### Usage
- Access the web app at `http://127.0.0.1:8000/`
- Log in with your credentials (admin, superintendent, teacher)
- Upload, encrypt, and verify documents as per your role

## Security
- All sensitive documents are encrypted before storage.
- Blockchain ensures tamper-proof transaction records.

## License
This project is for educational purposes.

## Authors
- Dhanraj Chinta

---
Feel free to contact me for any further information required!
