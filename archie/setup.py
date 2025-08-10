"""
Setup configuration for ArchieOS
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read long description from README
long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="archie-os",
    version="2.0.0",
    author="The Council",
    author_email="council@archie.local",
    description="ArchieOS - Intelligent Storage Operating System for Personal Archives",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/the-council/archie-os",
    packages=find_packages(include=["archie_core", "archie_core.*", "api", "api.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: System :: Archiving",
        "Topic :: Text Processing :: Indexing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10", 
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        # Core dependencies
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.4.0",
        "python-multipart>=0.0.6",
        
        # Authentication and security
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4",
        "cryptography>=41.0.0",
        
        # Database
        "sqlite3",  # Built-in, but listed for clarity
        
        # Data processing
        "python-dateutil>=2.8.0",
        "pytz>=2023.3",
        
        # File handling
        "python-magic>=0.4.27",
        "Pillow>=10.0.0",
        
        # OCR capabilities
        "pytesseract>=0.3.10",
        
        # Job scheduling
        "python-crontab>=3.0.0",
        
        # HTTP requests
        "httpx>=0.25.0",
        "requests>=2.31.0",
        
        # Configuration
        "python-dotenv>=1.0.0",
        
        # Logging
        "structlog>=23.2.0",
    ],
    extras_require={
        "test": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.11.0",
            "pytest-benchmark>=4.0.0",
            "pytest-xdist>=3.3.0",
            "coverage[toml]>=7.3.0",
            "httpx>=0.25.0",
        ],
        "dev": [
            # Testing
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0", 
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.11.0",
            "coverage[toml]>=7.3.0",
            
            # Linting and formatting
            "flake8>=6.0.0",
            "black>=23.7.0",
            "isort>=5.12.0",
            "mypy>=1.5.0",
            
            # Security
            "bandit[toml]>=1.7.5",
            "safety>=2.3.0",
            
            # Documentation
            "sphinx>=7.1.0",
            "sphinx-rtd-theme>=1.3.0",
            "sphinx-autodoc-typehints>=1.24.0",
        ],
        "prod": [
            # Production optimizations
            "gunicorn>=21.2.0",
            "uvloop>=0.19.0",  # Faster event loop
            "orjson>=3.9.0",   # Faster JSON
        ]
    },
    entry_points={
        "console_scripts": [
            "archie=run_archie:main",
            "archie-test=run_tests:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.sql", "*.html", "*.css", "*.js", "*.json", "*.md"],
        "archie_core": ["*.sql"],
        "api": ["*.html"],
    },
    zip_safe=False,  # Required for static files
    keywords="archive storage ai memory database file-management",
    project_urls={
        "Bug Reports": "https://github.com/the-council/archie-os/issues",
        "Source": "https://github.com/the-council/archie-os/",
        "Documentation": "https://archie-os.readthedocs.io/",
    },
)