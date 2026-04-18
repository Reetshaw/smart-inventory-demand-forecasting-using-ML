"""
Database Configuration
======================
This file lets you switch between SQLite (default / Replit) and MySQL (XAMPP / local).

HOW TO USE WITH XAMPP:
1. Open XAMPP Control Panel → Start Apache + MySQL
2. Open phpMyAdmin (http://localhost/phpmyadmin)
3. Create a database named: smartstock_db
4. Set XAMPP_MODE = True below (or set env var USE_MYSQL=1)
5. Update DB_HOST, DB_USER, DB_PASSWORD if needed
6. Run the app: python app.py
7. Tables are created automatically on first run.

SQL to create database (run in phpMyAdmin SQL tab):
    CREATE DATABASE IF NOT EXISTS smartstock_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

Required pip packages for MySQL:
    pip install PyMySQL cryptography
"""

import os

# ─── XAMPP / MySQL Settings ────────────────────────────────────────────────────
DB_HOST     = os.environ.get('DB_HOST', 'localhost')
DB_PORT     = os.environ.get('DB_PORT', '3306')
DB_USER     = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_NAME     = os.environ.get('DB_NAME', 'smartstock_db')


def get_database_uri(base_dir: str) -> str:
    """Return SQLAlchemy database URI for MySQL (XAMPP) only."""
    return (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )

