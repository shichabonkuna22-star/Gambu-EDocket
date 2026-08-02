# SAPS eDocket Management System

A secure, web-based docket management system for South African Police Services (SAPS) to replace manual paper-based systems.

## Features

- 🔐 **Secure Authentication**: Role-based access control with @saps.gov.za email validation
- 👤 **Officer Management**: Auto-generated badge numbers and comprehensive officer profiles
- 📁 **Digital Docket System**: Create, track, and manage criminal cases digitally
- 🎯 **Smart Suspect Verification**: ID number validation and facial recognition proof-of-concept
- 🔍 **Duplicate Detection**: Automatic suspect matching using face recognition
- 📊 **Case Management**: Complete workflow from open to closed status
- 🔒 **RBAC Security**: Officers only access their assigned cases

## Tech Stack

- **Backend**: Python Flask
- **Database**: SQLite (Development), PostgreSQL (Production)
- **ORM**: SQLAlchemy
- **Authentication**: Flask-Login
- **Face Recognition**: OpenCV + face-recognition library
- **Frontend**: Bootstrap 5 + Jinja2 templates

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/saps-edocket.git
   cd saps-edocket