#!/usr/bin/env python3
"""
Dependency Analyzer Tool

Analyzes Python imports across a codebase and cross-references with requirements files
to identify missing dependencies, version conflicts, and unused packages.
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class ImportInfo:
    """Information about a Python import"""
    module: str
    source_file: str
    line_number: int
    is_local: bool = False
    is_stdlib: bool = False


@dataclass
class DependencyIssue:
    """Represents a dependency-related issue"""
    type: str  # 'missing', 'version_conflict', 'unused', 'local_import_error'
    package: str
    details: str
    severity: str  # 'error', 'warning', 'info'
    files: List[str] = None


class DependencyAnalyzer:
    """Analyzes Python dependencies and cross-references with requirements"""
    
    # Common Python standard library modules (Python 3.8+)
    STDLIB_MODULES = {
        'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
        'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins',
        'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs',
        'codeop', 'collections', 'colorsys', 'compileall', 'concurrent', 'configparser',
        'contextlib', 'contextvars', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv',
        'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib',
        'dis', 'distutils', 'doctest', 'email', 'encodings', 'ensurepip', 'enum',
        'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'formatter',
        'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob',
        'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr',
        'imp', 'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword',
        'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 'mailbox', 'mailcap',
        'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder', 'multiprocessing',
        'netrc', 'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev',
        'parser', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil',
        'platform', 'plistlib', 'poplib', 'posix', 'pprint', 'profile', 'pstats',
        'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random',
        're', 'readline', 'reprlib', 'resource', 'rlcompleter', 'runpy', 'sched',
        'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil', 'signal',
        'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd',
        'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct',
        'subprocess', 'sunau', 'symbol', 'symtable', 'sys', 'sysconfig', 'syslog',
        'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios', 'test', 'textwrap',
        'threading', 'time', 'timeit', 'tkinter', 'token', 'tokenize', 'trace',
        'traceback', 'tracemalloc', 'tty', 'turtle', 'types', 'typing', 'unicodedata',
        'unittest', 'urllib', 'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref',
        'webbrowser', 'winreg', 'winsound', 'wsgiref', 'xdrlib', 'xml', 'xmlrpc',
        'zipapp', 'zipfile', 'zipimport', 'zlib', '_thread'
    }
    
    # Package name mappings (import name -> package name)
    PACKAGE_MAPPINGS = {
        'cv2': 'opencv-python',
        'sklearn': 'scikit-learn',
        'PIL': 'Pillow',
        'yaml': 'PyYAML',
        'OpenSSL': 'pyOpenSSL',
        'dateutil': 'python-dateutil',
        'dotenv': 'python-dotenv',
        'jose': 'python-jose',
        'multipart': 'python-multipart',
        'bs4': 'beautifulsoup4',
        'lxml': 'lxml',
        'werkzeug': 'Werkzeug',
        'flask': 'Flask',
        'django': 'Django',
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn',
        'pydantic': 'pydantic',
        'sqlalchemy': 'SQLAlchemy',
        'psycopg2': 'psycopg2-binary',
        'mysqldb': 'mysqlclient',
        'redis': 'redis',
        'celery': 'celery',
        'pytest': 'pytest',
        'nose': 'nose2',
        'mock': 'mock',
        'faker': 'Faker',
        'factory': 'factory-boy',
        'jwt': 'PyJWT',
        'cryptography': 'cryptography',
        'bcrypt': 'bcrypt',
        'passlib': 'passlib',
        'requests': 'requests',
        'httpx': 'httpx',
        'aiohttp': 'aiohttp',
        'tornado': 'tornado',
        'bottle': 'bottle',
        'cherrypy': 'CherryPy',
        'matplotlib': 'matplotlib',
        'seaborn': 'seaborn',
        'plotly': 'plotly',
        'bokeh': 'bokeh',
        'altair': 'altair',
        'streamlit': 'streamlit',
        'gradio': 'gradio',
        'dash': 'dash',
        'joblib': 'joblib',
        'dask': 'dask',
        'ray': 'ray',
        'airflow': 'apache-airflow',
        'mlflow': 'mlflow',
        'wandb': 'wandb',
        'tensorboard': 'tensorboard',
        'transformers': 'transformers',
        'datasets': 'datasets',
        'tokenizers': 'tokenizers',
        'sentence_transformers': 'sentence-transformers',
        'langchain': 'langchain',
        'openai': 'openai',
        'anthropic': 'anthropic',
        'cohere': 'cohere',
        'pinecone': 'pinecone-client',
        'chromadb': 'chromadb',
        'qdrant': 'qdrant-client',
        'weaviate': 'weaviate-client',
        'motor': 'motor',
        'pymongo': 'pymongo',
        'cassandra': 'cassandra-driver',
        'elasticsearch': 'elasticsearch',
        'kafka': 'kafka-python',
        'pika': 'pika',
        'kombu': 'kombu',
        'graphene': 'graphene',
        'strawberry': 'strawberry-graphql',
        'ariadne': 'ariadne',
        'grpc': 'grpcio',
        'grpcio': 'grpcio',
        'protobuf': 'protobuf',
        'avro': 'avro-python3',
        'thrift': 'thrift',
        'msgpack': 'msgpack',
        'orjson': 'orjson',
        'ujson': 'ujson',
        'simplejson': 'simplejson',
        'toml': 'toml',
        'configobj': 'configobj',
        'dynaconf': 'dynaconf',
        'hydra': 'hydra-core',
        'click': 'click',
        'typer': 'typer',
        'fire': 'fire',
        'docopt': 'docopt',
        'rich': 'rich',
        'tqdm': 'tqdm',
        'colorama': 'colorama',
        'termcolor': 'termcolor',
        'tabulate': 'tabulate',
        'prettytable': 'prettytable',
        'jinja2': 'Jinja2',
        'mako': 'Mako',
        'markdown': 'Markdown',
        'textile': 'textile',
        'docutils': 'docutils',
        'sphinx': 'Sphinx',
        'mkdocs': 'mkdocs',
        'pelican': 'pelican',
        'nikola': 'nikola',
        'lektor': 'Lektor',
        'wagtail': 'wagtail',
        'mezzanine': 'Mezzanine',
        'feincms': 'FeinCMS',
        'alembic': 'alembic',
        'peewee': 'peewee',
        'tortoise': 'tortoise-orm',
        'pony': 'pony',
        'orator': 'orator',
        'mongoengine': 'mongoengine',
        'pymodm': 'pymodm',
        'beanie': 'beanie',
        'odmantic': 'odmantic',
        'pydantic_settings': 'pydantic-settings',
        'attrs': 'attrs',
        'cattrs': 'cattrs',
        'marshmallow': 'marshmallow',
        'colander': 'colander',
        'cerberus': 'Cerberus',
        'voluptuous': 'voluptuous',
        'schema': 'schema',
        'jsonschema': 'jsonschema',
        'phonenumbers': 'phonenumbers',
        'email_validator': 'email-validator',
        'validators': 'validators',
        'wtforms': 'WTForms',
        'django_crispy_forms': 'django-crispy-forms',
        'flask_wtf': 'Flask-WTF',
        'deform': 'deform',
        'formencode': 'FormEncode',
        'rq': 'rq',
        'huey': 'huey',
        'dramatiq': 'dramatiq',
        'apscheduler': 'APScheduler',
        'schedule': 'schedule',
        'pendulum': 'pendulum',
        'arrow': 'arrow',
        'maya': 'maya',
        'delorean': 'Delorean',
        'freezegun': 'freezegun',
        'humanize': 'humanize',
        'babel': 'Babel',
        'pytz': 'pytz',
        'tzlocal': 'tzlocal',
        'iso8601': 'iso8601',
        'isodate': 'isodate',
        'gevent': 'gevent',
        'eventlet': 'eventlet',
        'asyncpg': 'asyncpg',
        'aiopg': 'aiopg',
        'aiomysql': 'aiomysql',
        'aioredis': 'aioredis',
        'aiofiles': 'aiofiles',
        'anyio': 'anyio',
        'trio': 'trio',
        'curio': 'curio',
        'twisted': 'Twisted',
        'channels': 'channels',
        'websocket': 'websocket-client',
        'websockets': 'websockets',
        'socketio': 'python-socketio',
        'engineio': 'python-engineio',
        'paramiko': 'paramiko',
        'fabric': 'fabric',
        'ansible': 'ansible',
        'salt': 'salt',
        'supervisor': 'supervisor',
        'circus': 'circus',
        'honcho': 'honcho',
        'docker': 'docker',
        'kubernetes': 'kubernetes',
        'boto3': 'boto3',
        'google': 'google-cloud',
        'azure': 'azure',
        'digitalocean': 'python-digitalocean',
        'linode_api4': 'linode_api4',
        'vultr': 'vultr',
        'hcloud': 'hcloud',
        'pyrogram': 'Pyrogram',
        'telethon': 'Telethon',
        'python_telegram_bot': 'python-telegram-bot',
        'discord': 'discord.py',
        'slack_sdk': 'slack-sdk',
        'tweepy': 'tweepy',
        'facebook': 'facebook-sdk',
        'instagram': 'instagram-private-api',
        'praw': 'praw',
        'prawcore': 'prawcore',
        'stripe': 'stripe',
        'paypal': 'paypalrestsdk',
        'braintree': 'braintree',
        'square': 'squareup',
        'authorize': 'authorizenet',
        'twilio': 'twilio',
        'vonage': 'vonage',
        'plivo': 'plivo',
        'sendgrid': 'sendgrid',
        'mailgun': 'mailgun',
        'postmark': 'postmarker',
        'sparkpost': 'sparkpost',
        'mandrill': 'mandrill',
        'sentry_sdk': 'sentry-sdk',
        'rollbar': 'rollbar',
        'bugsnag': 'bugsnag',
        'raygun4py': 'raygun4py',
        'scout_apm': 'scout-apm',
        'newrelic': 'newrelic',
        'datadog': 'datadog',
        'prometheus_client': 'prometheus-client',
        'statsd': 'statsd',
        'pythonjsonlogger': 'python-json-logger',
        'structlog': 'structlog',
        'loguru': 'loguru',
        'eliot': 'eliot',
        'logbook': 'Logbook',
        'verboselogs': 'verboselogs',
        'coloredlogs': 'coloredlogs',
        'selenium': 'selenium',
        'playwright': 'playwright',
        'pyppeteer': 'pyppeteer',
        'mechanize': 'mechanize',
        'robobrowser': 'robobrowser',
        'scrapy': 'Scrapy',
        'parsel': 'parsel',
        'pyquery': 'pyquery',
        'feedparser': 'feedparser',
        'newspaper': 'newspaper3k',
        'pdfplumber': 'pdfplumber',
        'PyPDF2': 'PyPDF2',
        'pdfminer': 'pdfminer.six',
        'reportlab': 'reportlab',
        'fpdf': 'fpdf',
        'weasyprint': 'weasyprint',
        'cairosvg': 'CairoSVG',
        'svgwrite': 'svgwrite',
        'qrcode': 'qrcode',
        'barcode': 'python-barcode',
        'captcha': 'captcha',
        'face_recognition': 'face-recognition',
        'mediapipe': 'mediapipe',
        'pytesseract': 'pytesseract',
        'easyocr': 'easyocr',
        'paddleocr': 'paddleocr',
        'speech_recognition': 'SpeechRecognition',
        'pyttsx3': 'pyttsx3',
        'gtts': 'gTTS',
        'pydub': 'pydub',
        'moviepy': 'moviepy',
        'imageio': 'imageio',
        'scikit-image': 'scikit-image',
        'mahotas': 'mahotas',
        'SimpleITK': 'SimpleITK',
        'nibabel': 'nibabel',
        'dicom': 'pydicom',
        'pydicom': 'pydicom',
        'hl7': 'hl7',
        'fhir': 'fhir.resources',
        'bioinformatics': 'biopython',
        'Bio': 'biopython',
        'rdkit': 'rdkit',
        'pymol': 'pymol-open-source',
        'mdanalysis': 'MDAnalysis',
        'ase': 'ase',
        'pymatgen': 'pymatgen',
        'cclib': 'cclib',
        'openbabel': 'openbabel',
        'pubchempy': 'pubchempy',
        'chempy': 'chempy',
        'periodictable': 'periodictable',
        'mendeleev': 'mendeleev',
        'molmass': 'molmass',
        'chembl_webresource_client': 'chembl-webresource-client',
        'pysmiles': 'pysmiles',
        'mordred': 'mordred',
        'descriptastorus': 'descriptastorus'
    }
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.imports: List[ImportInfo] = []
        self.requirements: Dict[str, Optional[str]] = {}  # package -> version
        self.local_modules: Set[str] = set()
        self.issues: List[DependencyIssue] = []
        
    def analyze(self, source_pattern: str = "**/*.py", 
                requirements_files: List[str] = None) -> List[DependencyIssue]:
        """
        Analyze dependencies in the project
        
        Args:
            source_pattern: Glob pattern for Python files
            requirements_files: List of requirements files to check
            
        Returns:
            List of dependency issues found
        """
        if requirements_files is None:
            requirements_files = self._find_requirements_files()
            
        # Collect all imports
        self._collect_imports(source_pattern)
        
        # Identify local modules
        self._identify_local_modules()
        
        # Parse requirements files
        for req_file in requirements_files:
            self._parse_requirements(req_file)
            
        # Analyze for issues
        self._check_missing_dependencies()
        self._check_unused_dependencies()
        self._check_version_conflicts()
        self._check_local_import_issues()
        
        return self.issues
        
    def _find_requirements_files(self) -> List[str]:
        """Find all requirements files in the project"""
        patterns = [
            "requirements.txt",
            "requirements*.txt",
            "requirements/*.txt",
            "reqs.txt",
            "reqs/*.txt",
            "deps.txt",
            "deps/*.txt",
            "Pipfile",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "poetry.lock",
            "pip-requirements.txt",
            "**/requirements.txt",
            "**/requirements*.txt"
        ]
        
        files = []
        for pattern in patterns:
            files.extend(self.project_root.glob(pattern))
            
        return [str(f) for f in files if f.is_file()]
        
    def _collect_imports(self, pattern: str):
        """Collect all imports from Python files"""
        for py_file in self.project_root.glob(pattern):
            if py_file.is_file() and not self._should_ignore_file(py_file):
                self._extract_imports_from_file(py_file)
                
    def _should_ignore_file(self, file_path: Path) -> bool:
        """Check if file should be ignored"""
        ignore_patterns = [
            "__pycache__",
            ".git",
            ".tox",
            ".venv",
            "venv",
            "env",
            ".env",
            "virtualenv",
            ".pytest_cache",
            ".mypy_cache",
            "build",
            "dist",
            "*.egg-info",
            "migrations",
            "tests",
            "test",
            "testing",
            "docs",
            "doc",
            "documentation",
            "examples",
            "example",
            "samples",
            "sample",
            "benchmarks",
            "benchmark",
            ".eggs"
        ]
        
        path_str = str(file_path)
        return any(pattern in path_str for pattern in ignore_patterns)
        
    def _extract_imports_from_file(self, file_path: Path):
        """Extract imports from a Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content, filename=str(file_path))
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.imports.append(ImportInfo(
                            module=alias.name.split('.')[0],
                            source_file=str(file_path.relative_to(self.project_root)),
                            line_number=node.lineno
                        ))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self.imports.append(ImportInfo(
                            module=node.module.split('.')[0],
                            source_file=str(file_path.relative_to(self.project_root)),
                            line_number=node.lineno
                        ))
        except Exception as e:
            # Log parsing errors but continue
            self.issues.append(DependencyIssue(
                type='parse_error',
                package=str(file_path),
                details=f"Failed to parse file: {str(e)}",
                severity='warning'
            ))
            
    def _identify_local_modules(self):
        """Identify local modules in the project"""
        # Find all Python packages (directories with __init__.py)
        for init_file in self.project_root.glob("**/__init__.py"):
            if not self._should_ignore_file(init_file):
                package_dir = init_file.parent
                rel_path = package_dir.relative_to(self.project_root)
                parts = rel_path.parts
                
                # Add all possible module paths
                for i in range(len(parts)):
                    self.local_modules.add(parts[i])
                    if i > 0:
                        self.local_modules.add('.'.join(parts[:i+1]))
                        
        # Find all standalone Python files
        for py_file in self.project_root.glob("**/*.py"):
            if not self._should_ignore_file(py_file) and py_file.name != "__init__.py":
                rel_path = py_file.relative_to(self.project_root)
                module_name = str(rel_path.with_suffix('')).replace('/', '.')
                self.local_modules.add(module_name.split('.')[0])
                
    def _parse_requirements(self, req_file: str):
        """Parse a requirements file"""
        req_path = Path(req_file)
        
        if req_path.name == "Pipfile":
            self._parse_pipfile(req_path)
        elif req_path.name == "pyproject.toml":
            self._parse_pyproject_toml(req_path)
        elif req_path.name == "setup.py":
            self._parse_setup_py(req_path)
        elif req_path.name == "setup.cfg":
            self._parse_setup_cfg(req_path)
        elif req_path.name == "poetry.lock":
            self._parse_poetry_lock(req_path)
        else:
            self._parse_requirements_txt(req_path)
            
    def _parse_requirements_txt(self, req_file: Path):
        """Parse a requirements.txt file"""
        try:
            with open(req_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('-'):
                        # Handle various requirement formats
                        if '==' in line:
                            package, version = line.split('==', 1)
                            self.requirements[package.strip()] = version.strip()
                        elif '>=' in line:
                            package = line.split('>=')[0]
                            self.requirements[package.strip()] = 'any'
                        elif '<=' in line:
                            package = line.split('<=')[0]
                            self.requirements[package.strip()] = 'any'
                        elif '>' in line:
                            package = line.split('>')[0]
                            self.requirements[package.strip()] = 'any'
                        elif '<' in line:
                            package = line.split('<')[0]
                            self.requirements[package.strip()] = 'any'
                        elif '~=' in line:
                            package = line.split('~=')[0]
                            self.requirements[package.strip()] = 'any'
                        elif '[' in line:
                            # Handle extras
                            package = line.split('[')[0]
                            self.requirements[package.strip()] = 'any'
                        else:
                            self.requirements[line.strip()] = None
        except Exception as e:
            self.issues.append(DependencyIssue(
                type='parse_error',
                package=str(req_file),
                details=f"Failed to parse requirements file: {str(e)}",
                severity='warning'
            ))
            
    def _parse_pipfile(self, pipfile: Path):
        """Parse a Pipfile"""
        try:
            import toml
            data = toml.load(pipfile)
            
            for section in ['packages', 'dev-packages']:
                if section in data:
                    for package, version in data[section].items():
                        if isinstance(version, dict):
                            self.requirements[package] = version.get('version', 'any')
                        else:
                            self.requirements[package] = version if version != '*' else None
        except ImportError:
            self.issues.append(DependencyIssue(
                type='parse_error',
                package=str(pipfile),
                details="toml package not available to parse Pipfile",
                severity='info'
            ))
        except Exception as e:
            self.issues.append(DependencyIssue(
                type='parse_error',
                package=str(pipfile),
                details=f"Failed to parse Pipfile: {str(e)}",
                severity='warning'
            ))
            
    def _parse_pyproject_toml(self, pyproject: Path):
        """Parse a pyproject.toml file"""
        try:
            import toml
            data = toml.load(pyproject)
            
            # Poetry dependencies
            if 'tool' in data and 'poetry' in data['tool']:
                poetry = data['tool']['poetry']
                for section in ['dependencies', 'dev-dependencies']:
                    if section in poetry:
                        for package, version in poetry[section].items():
                            if package != 'python':
                                if isinstance(version, dict):
                                    self.requirements[package] = version.get('version', 'any')
                                else:
                                    self.requirements[package] = version if version != '*' else None
                                    
            # PEP 517 dependencies
            if 'project' in data and 'dependencies' in data['project']:
                for dep in data['project']['dependencies']:
                    if '==' in dep:
                        package, version = dep.split('==', 1)
                        self.requirements[package.strip()] = version.strip()
                    else:
                        package = re.split(r'[<>=~!]', dep)[0]
                        self.requirements[package.strip()] = 'any'
                        
        except ImportError:
            self.issues.append(DependencyIssue(
                type='parse_error',
                package=str(pyproject),
                details="toml package not available to parse pyproject.toml",
                severity='info'
            ))
        except Exception as e:
            self.issues.append(DependencyIssue(
                type='parse_error',
                package=str(pyproject),
                details=f"Failed to parse pyproject.toml: {str(e)}",
                severity='warning'
            ))
            
    def _parse_setup_py(self, setup_py: Path):
        """Parse a setup.py file"""
        try:
            with open(setup_py, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Look for install_requires
            install_requires_match = re.search(
                r'install_requires\s*=\s*\[(.*?)\]',
                content,
                re.DOTALL
            )
            
            if install_requires_match:
                requires_str = install_requires_match.group(1)
                requires_list = re.findall(r'["\']([^"\']+)["\']', requires_str)
                
                for req in requires_list:
                    if '==' in req:
                        package, version = req.split('==', 1)
                        self.requirements[package.strip()] = version.strip()
                    else:
                        package = re.split(r'[<>=~!]', req)[0]
                        self.requirements[package.strip()] = 'any'
                        
        except Exception as e:
            self.issues.append(DependencyIssue(
                type='parse_error',
                package=str(setup_py),
                details=f"Failed to parse setup.py: {str(e)}",
                severity='warning'
            ))
            
    def _parse_setup_cfg(self, setup_cfg: Path):
        """Parse a setup.cfg file"""
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(setup_cfg)
            
            if 'options' in config and 'install_requires' in config['options']:
                requires_str = config['options']['install_requires']
                for req in requires_str.strip().split('\n'):
                    req = req.strip()
                    if req:
                        if '==' in req:
                            package, version = req.split('==', 1)
                            self.requirements[package.strip()] = version.strip()
                        else:
                            package = re.split(r'[<>=~!]', req)[0]
                            self.requirements[package.strip()] = 'any'
                            
        except Exception as e:
            self.issues.append(DependencyIssue(
                type='parse_error',
                package=str(setup_cfg),
                details=f"Failed to parse setup.cfg: {str(e)}",
                severity='warning'
            ))
            
    def _parse_poetry_lock(self, poetry_lock: Path):
        """Parse a poetry.lock file"""
        try:
            import toml
            data = toml.load(poetry_lock)
            
            if 'package' in data:
                for package in data['package']:
                    name = package.get('name', '')
                    version = package.get('version', 'any')
                    if name:
                        self.requirements[name] = version
                        
        except ImportError:
            self.issues.append(DependencyIssue(
                type='parse_error',
                package=str(poetry_lock),
                details="toml package not available to parse poetry.lock",
                severity='info'
            ))
        except Exception as e:
            self.issues.append(DependencyIssue(
                type='parse_error',
                package=str(poetry_lock),
                details=f"Failed to parse poetry.lock: {str(e)}",
                severity='warning'
            ))
            
    def _check_missing_dependencies(self):
        """Check for imports that are not in requirements"""
        imported_modules = set()
        
        for imp in self.imports:
            # Skip stdlib and local imports
            if imp.module not in self.STDLIB_MODULES and imp.module not in self.local_modules:
                imported_modules.add(imp.module)
                
        # Get package names from requirements (lowercase for comparison)
        required_packages = {pkg.lower() for pkg in self.requirements.keys()}
        
        # Check each imported module
        for module in imported_modules:
            # Get the package name for this import
            package_name = self.PACKAGE_MAPPINGS.get(module, module)
            
            # Check if it's in requirements (case-insensitive)
            if package_name.lower() not in required_packages:
                # Find all files that import this module
                files = [imp.source_file for imp in self.imports if imp.module == module]
                unique_files = list(set(files))
                
                self.issues.append(DependencyIssue(
                    type='missing',
                    package=package_name,
                    details=f"Module '{module}' is imported but '{package_name}' is not in requirements",
                    severity='error',
                    files=unique_files[:5]  # Limit to 5 files for readability
                ))
                
    def _check_unused_dependencies(self):
        """Check for requirements that are not imported"""
        # Get all imported modules (including mapped package names)
        imported_packages = set()
        
        for imp in self.imports:
            if imp.module not in self.STDLIB_MODULES and imp.module not in self.local_modules:
                # Add both the module name and its package mapping
                imported_packages.add(imp.module.lower())
                package_name = self.PACKAGE_MAPPINGS.get(imp.module, imp.module)
                imported_packages.add(package_name.lower())
                
        # Also add reverse mappings (package -> import name)
        reverse_mappings = {v.lower(): k.lower() for k, v in self.PACKAGE_MAPPINGS.items()}
        
        # Check each requirement
        for package in self.requirements:
            package_lower = package.lower()
            import_name = reverse_mappings.get(package_lower, package_lower)
            
            # Skip some special cases
            if package_lower in ['pip', 'setuptools', 'wheel', 'pip-tools', 'pipdeptree']:
                continue
                
            # Check if neither the package nor its import name is used
            if package_lower not in imported_packages and import_name not in imported_packages:
                self.issues.append(DependencyIssue(
                    type='unused',
                    package=package,
                    details=f"Package '{package}' is in requirements but not imported",
                    severity='warning'
                ))
                
    def _check_version_conflicts(self):
        """Check for version conflicts in requirements"""
        # Group requirements by package name
        package_versions = defaultdict(list)
        
        for package, version in self.requirements.items():
            if version:
                package_versions[package.lower()].append((package, version))
                
        # Check for conflicts
        for package_lower, versions in package_versions.items():
            if len(versions) > 1:
                version_set = set(v[1] for v in versions)
                if len(version_set) > 1 and 'any' not in version_set:
                    self.issues.append(DependencyIssue(
                        type='version_conflict',
                        package=versions[0][0],
                        details=f"Multiple versions specified: {', '.join(f'{v[0]}=={v[1]}' for v in versions)}",
                        severity='error'
                    ))
                    
    def _check_local_import_issues(self):
        """Check for potential issues with local imports"""
        for imp in self.imports:
            if imp.module in self.local_modules:
                imp.is_local = True
                
                # Check for common issues
                source_parts = Path(imp.source_file).parts
                module_parts = imp.module.split('.')
                
                # Check if trying to import from parent directory
                if len(module_parts) > len(source_parts):
                    self.issues.append(DependencyIssue(
                        type='local_import_error',
                        package=imp.module,
                        details=f"Potential import error: importing '{imp.module}' from '{imp.source_file}'",
                        severity='warning',
                        files=[imp.source_file]
                    ))
                    
    def generate_report(self) -> str:
        """Generate a detailed report of the analysis"""
        report = []
        report.append("=" * 80)
        report.append("DEPENDENCY ANALYSIS REPORT")
        report.append("=" * 80)
        report.append(f"\nProject Root: {self.project_root}")
        report.append(f"Total Imports Analyzed: {len(self.imports)}")
        report.append(f"Total Requirements Found: {len(self.requirements)}")
        report.append(f"Total Issues Found: {len(self.issues)}")
        
        # Group issues by type
        issues_by_type = defaultdict(list)
        for issue in self.issues:
            issues_by_type[issue.type].append(issue)
            
        # Report each type of issue
        if 'missing' in issues_by_type:
            report.append("\n" + "-" * 60)
            report.append("MISSING DEPENDENCIES (Imported but not in requirements)")
            report.append("-" * 60)
            for issue in sorted(issues_by_type['missing'], key=lambda x: x.package):
                report.append(f"\n• {issue.package}")
                report.append(f"  {issue.details}")
                if issue.files:
                    report.append(f"  Used in: {', '.join(issue.files[:3])}")
                    if len(issue.files) > 3:
                        report.append(f"  ... and {len(issue.files) - 3} more files")
                        
        if 'unused' in issues_by_type:
            report.append("\n" + "-" * 60)
            report.append("UNUSED DEPENDENCIES (In requirements but not imported)")
            report.append("-" * 60)
            for issue in sorted(issues_by_type['unused'], key=lambda x: x.package):
                report.append(f"\n• {issue.package}")
                report.append(f"  {issue.details}")
                
        if 'version_conflict' in issues_by_type:
            report.append("\n" + "-" * 60)
            report.append("VERSION CONFLICTS")
            report.append("-" * 60)
            for issue in issues_by_type['version_conflict']:
                report.append(f"\n• {issue.package}")
                report.append(f"  {issue.details}")
                
        if 'local_import_error' in issues_by_type:
            report.append("\n" + "-" * 60)
            report.append("LOCAL IMPORT ISSUES")
            report.append("-" * 60)
            for issue in issues_by_type['local_import_error']:
                report.append(f"\n• {issue.package}")
                report.append(f"  {issue.details}")
                
        if 'parse_error' in issues_by_type:
            report.append("\n" + "-" * 60)
            report.append("PARSE ERRORS")
            report.append("-" * 60)
            for issue in issues_by_type['parse_error']:
                report.append(f"\n• {issue.package}")
                report.append(f"  {issue.details}")
                
        # Summary and recommendations
        report.append("\n" + "=" * 80)
        report.append("SUMMARY")
        report.append("=" * 80)
        
        error_count = len([i for i in self.issues if i.severity == 'error'])
        warning_count = len([i for i in self.issues if i.severity == 'warning'])
        info_count = len([i for i in self.issues if i.severity == 'info'])
        
        report.append(f"\nErrors: {error_count}")
        report.append(f"Warnings: {warning_count}")
        report.append(f"Info: {info_count}")
        
        if error_count > 0:
            report.append("\n⚠️  Critical issues found that should be fixed!")
            
        return '\n'.join(report)
        
    def suggest_requirements_update(self) -> str:
        """Suggest updates to requirements.txt"""
        suggestions = []
        
        # Get missing dependencies
        missing = [issue for issue in self.issues if issue.type == 'missing']
        
        if missing:
            suggestions.append("# Add these missing dependencies to your requirements.txt:")
            for issue in sorted(missing, key=lambda x: x.package):
                suggestions.append(f"{issue.package}")
                
        # Get unused dependencies
        unused = [issue for issue in self.issues if issue.type == 'unused']
        
        if unused:
            suggestions.append("\n# Consider removing these unused dependencies:")
            for issue in sorted(unused, key=lambda x: x.package):
                suggestions.append(f"# {issue.package}")
                
        return '\n'.join(suggestions) if suggestions else "No updates needed."


def main():
    """CLI interface for the dependency analyzer"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze Python project dependencies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze current directory
  python dependency_analyzer.py .
  
  # Analyze specific directory with custom pattern
  python dependency_analyzer.py /path/to/project --pattern "src/**/*.py"
  
  # Analyze with specific requirements files
  python dependency_analyzer.py . --requirements requirements.txt requirements-dev.txt
  
  # Generate requirements update suggestions
  python dependency_analyzer.py . --suggest-updates
  
  # Output results in JSON format
  python dependency_analyzer.py . --json
        """
    )
    
    parser.add_argument('project_path', help='Path to the project root directory')
    parser.add_argument('--pattern', default='**/*.py',
                       help='Glob pattern for Python files (default: **/*.py)')
    parser.add_argument('--requirements', nargs='+',
                       help='Specific requirements files to check')
    parser.add_argument('--json', action='store_true',
                       help='Output results in JSON format')
    parser.add_argument('--suggest-updates', action='store_true',
                       help='Suggest requirements.txt updates')
    parser.add_argument('--ignore-warnings', action='store_true',
                       help='Only show errors, not warnings')
    
    args = parser.parse_args()
    
    # Run analysis
    analyzer = DependencyAnalyzer(args.project_path)
    issues = analyzer.analyze(args.pattern, args.requirements)
    
    # Filter issues if requested
    if args.ignore_warnings:
        issues = [i for i in issues if i.severity == 'error']
        analyzer.issues = issues
        
    # Output results
    if args.json:
        import json
        result = {
            'project_root': str(analyzer.project_root),
            'total_imports': len(analyzer.imports),
            'total_requirements': len(analyzer.requirements),
            'issues': [
                {
                    'type': issue.type,
                    'package': issue.package,
                    'details': issue.details,
                    'severity': issue.severity,
                    'files': issue.files or []
                }
                for issue in issues
            ]
        }
        print(json.dumps(result, indent=2))
    elif args.suggest_updates:
        print(analyzer.suggest_requirements_update())
    else:
        print(analyzer.generate_report())
        
    # Exit with error code if critical issues found
    error_count = len([i for i in issues if i.severity == 'error'])
    sys.exit(1 if error_count > 0 else 0)


if __name__ == '__main__':
    main()