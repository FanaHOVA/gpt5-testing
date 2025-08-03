#!/usr/bin/env python3
"""
Code Migration Assistant Tool

Assists with framework migrations by analyzing code patterns and providing
automated transformations. Initially focused on Flask to FastAPI migrations
but designed to be extensible to other framework pairs.
"""

import ast
import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass
from collections import defaultdict
import textwrap
import json


@dataclass
class MigrationIssue:
    """Represents a code pattern that needs migration"""
    file_path: str
    line_number: int
    issue_type: str
    original_code: str
    suggested_code: str
    description: str
    confidence: float  # 0.0 to 1.0
    auto_fixable: bool = True
    
    
@dataclass 
class MigrationContext:
    """Context information for migration"""
    source_framework: str
    target_framework: str
    project_root: Path
    files_to_migrate: List[Path]
    dependencies: Dict[str, str]  # Current dependencies
    new_dependencies: Dict[str, str]  # Dependencies to add
    removed_dependencies: Set[str]  # Dependencies to remove
    

class FrameworkMigrator:
    """Base class for framework migrators"""
    
    def analyze(self, context: MigrationContext) -> List[MigrationIssue]:
        """Analyze code and return migration issues"""
        raise NotImplementedError
        
    def generate_migration_plan(self, issues: List[MigrationIssue]) -> str:
        """Generate a detailed migration plan"""
        raise NotImplementedError
        
    def apply_fixes(self, issues: List[MigrationIssue], dry_run: bool = True) -> Dict[str, str]:
        """Apply automatic fixes and return modified files"""
        raise NotImplementedError
        

class FlaskToFastAPIMigrator(FrameworkMigrator):
    """Migrates Flask applications to FastAPI"""
    
    # Common Flask imports and their FastAPI equivalents
    IMPORT_MAPPINGS = {
        'flask': {
            'Flask': 'from fastapi import FastAPI',
            'request': 'from fastapi import Request',
            'jsonify': None,  # Not needed in FastAPI
            'render_template': 'from fastapi.responses import HTMLResponse\nfrom fastapi.templating import Jinja2Templates',
            'redirect': 'from fastapi.responses import RedirectResponse', 
            'url_for': 'from fastapi import Request',  # Needs custom implementation
            'session': None,  # Needs different approach
            'make_response': 'from fastapi.responses import Response',
            'abort': 'from fastapi import HTTPException',
            'send_file': 'from fastapi.responses import FileResponse',
            'send_from_directory': 'from fastapi.responses import FileResponse',
            'Blueprint': 'from fastapi import APIRouter',
            'current_app': None,  # Needs dependency injection
            'g': None,  # Needs dependency injection
        },
        'flask_login': {
            'login_user': None,  # Needs JWT or session implementation
            'logout_user': None,
            'login_required': 'from fastapi import Depends',  # Custom dependency
            'current_user': 'from fastapi import Depends',  # Custom dependency
        },
        'flask_sqlalchemy': {
            'SQLAlchemy': None,  # Use SQLAlchemy directly
        },
        'flask_cors': {
            'CORS': 'from fastapi.middleware.cors import CORSMiddleware',
        },
        'werkzeug.security': {
            'generate_password_hash': 'from passlib.context import CryptContext',
            'check_password_hash': 'from passlib.context import CryptContext',
        },
        'werkzeug.utils': {
            'secure_filename': None,  # Implement custom or use python-multipart
        }
    }
    
    # HTTP method decorators mapping
    METHOD_MAPPINGS = {
        '@app.route': '@app',
        '@bp.route': '@router',
        '@blueprint.route': '@router',
    }
    
    # Response patterns
    RESPONSE_PATTERNS = [
        (r'return\s+jsonify\((.*?)\)', r'return \1'),
        (r'return\s+json\.dumps\((.*?)\)', r'return \1'),
        (r'return\s+make_response\(jsonify\((.*?)\),\s*(\d+)\)', r'raise HTTPException(status_code=\2, detail=\1)'),
        (r'abort\((\d+)\)', r'raise HTTPException(status_code=\1)'),
        (r'abort\((\d+),\s*["\'](.+?)["\']\)', r'raise HTTPException(status_code=\1, detail="\2")'),
    ]
    
    def __init__(self):
        self.issues: List[MigrationIssue] = []
        self.file_contents: Dict[str, str] = {}
        
    def analyze(self, context: MigrationContext) -> List[MigrationIssue]:
        """Analyze Flask code and identify migration issues"""
        self.issues = []
        
        for file_path in context.files_to_migrate:
            if file_path.suffix == '.py':
                self._analyze_python_file(file_path, context)
                
        # Analyze project structure
        self._analyze_project_structure(context)
        
        # Analyze dependencies
        self._analyze_dependencies(context)
        
        return self.issues
        
    def _analyze_python_file(self, file_path: Path, context: MigrationContext):
        """Analyze a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.file_contents[str(file_path)] = content
                
            # Parse AST
            tree = ast.parse(content, filename=str(file_path))
            
            # Analyze imports
            self._analyze_imports(tree, file_path, content)
            
            # Analyze route definitions
            self._analyze_routes(tree, file_path, content)
            
            # Analyze request handling
            self._analyze_request_handling(tree, file_path, content)
            
            # Analyze response handling
            self._analyze_response_handling(content, file_path)
            
            # Analyze database operations
            self._analyze_database_operations(tree, file_path, content)
            
            # Analyze authentication
            self._analyze_authentication(tree, file_path, content)
            
        except Exception as e:
            self.issues.append(MigrationIssue(
                file_path=str(file_path),
                line_number=0,
                issue_type='parse_error',
                original_code='',
                suggested_code='',
                description=f'Failed to parse file: {str(e)}',
                confidence=1.0,
                auto_fixable=False
            ))
            
    def _analyze_imports(self, tree: ast.AST, file_path: Path, content: str):
        """Analyze and convert imports"""
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ''
                
                # Check Flask imports
                if module.startswith('flask'):
                    base_module = module.split('.')[0]
                    if base_module in self.IMPORT_MAPPINGS:
                        mappings = self.IMPORT_MAPPINGS[base_module]
                        
                        for alias in node.names:
                            import_name = alias.name
                            if import_name in mappings:
                                original_line = lines[node.lineno - 1] if node.lineno <= len(lines) else ''
                                
                                if mappings[import_name]:
                                    self.issues.append(MigrationIssue(
                                        file_path=str(file_path),
                                        line_number=node.lineno,
                                        issue_type='import_change',
                                        original_code=original_line.strip(),
                                        suggested_code=mappings[import_name],
                                        description=f'Convert Flask import to FastAPI equivalent',
                                        confidence=0.9,
                                        auto_fixable=True
                                    ))
                                else:
                                    self.issues.append(MigrationIssue(
                                        file_path=str(file_path),
                                        line_number=node.lineno,
                                        issue_type='import_removal',
                                        original_code=original_line.strip(),
                                        suggested_code='# ' + original_line.strip() + ' # TODO: Implement alternative',
                                        description=f'{import_name} has no direct FastAPI equivalent',
                                        confidence=0.8,
                                        auto_fixable=False
                                    ))
                                    
    def _analyze_routes(self, tree: ast.AST, file_path: Path, content: str):
        """Analyze route decorators and functions"""
        lines = content.split('\n')
        
        class RouteVisitor(ast.NodeVisitor):
            def __init__(self, migrator):
                self.migrator = migrator
                self.current_class = None
                
            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class
                
            def visit_FunctionDef(self, node):
                # Check for route decorators
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        if decorator.func.attr == 'route':
                            self._process_route_decorator(node, decorator)
                self.generic_visit(node)
                
            def _process_route_decorator(self, func_node, decorator):
                # Extract route path and methods
                route_path = None
                methods = ['GET']  # Default
                
                if decorator.args:
                    route_path = ast.literal_eval(decorator.args[0])
                    
                for keyword in decorator.keywords:
                    if keyword.arg == 'methods':
                        methods = ast.literal_eval(keyword.value)
                        
                # Generate FastAPI route decorator
                if len(methods) == 1:
                    method = methods[0].lower()
                    new_decorator = f'@app.{method}("{route_path}")'
                else:
                    # Multiple methods need separate decorators in FastAPI
                    new_decorator = '\n'.join([f'@app.{m.lower()}("{route_path}")' for m in methods])
                    
                # Check function signature
                self._analyze_route_function(func_node, route_path, methods)
                
                # Create issue
                original_line = lines[decorator.lineno - 1] if decorator.lineno <= len(lines) else ''
                self.migrator.issues.append(MigrationIssue(
                    file_path=str(file_path),
                    line_number=decorator.lineno,
                    issue_type='route_decorator',
                    original_code=original_line.strip(),
                    suggested_code=new_decorator,
                    description='Convert Flask route to FastAPI route',
                    confidence=0.95,
                    auto_fixable=True
                ))
                
            def _analyze_route_function(self, func_node, route_path, methods):
                """Analyze route function for parameter handling"""
                # Check if function uses request object
                uses_request = False
                uses_form = False
                uses_files = False
                
                for node in ast.walk(func_node):
                    if isinstance(node, ast.Attribute):
                        if isinstance(node.value, ast.Name) and node.value.id == 'request':
                            if node.attr in ['json', 'get_json']:
                                uses_request = True
                            elif node.attr in ['form', 'values']:
                                uses_form = True
                            elif node.attr == 'files':
                                uses_files = True
                                
                # Generate new function signature
                params = []
                if uses_request:
                    params.append('request_body: dict')
                if uses_form:
                    params.append('form_data: dict = Form(...)')
                if uses_files:
                    params.append('file: UploadFile = File(...)')
                    
                if params:
                    # Get current function signature
                    func_line = lines[func_node.lineno - 1] if func_node.lineno <= len(lines) else ''
                    
                    # Extract function name and current params
                    match = re.match(r'def\s+(\w+)\s*\((.*?)\):', func_line)
                    if match:
                        func_name = match.group(1)
                        current_params = match.group(2).strip()
                        
                        # Build new signature
                        if current_params and current_params != 'self':
                            new_params = current_params + ', ' + ', '.join(params)
                        else:
                            new_params = ', '.join(params)
                            
                        new_signature = f'def {func_name}({new_params}):'
                        
                        self.migrator.issues.append(MigrationIssue(
                            file_path=str(file_path),
                            line_number=func_node.lineno,
                            issue_type='function_signature',
                            original_code=func_line.strip(),
                            suggested_code=new_signature,
                            description='Update function signature for FastAPI',
                            confidence=0.85,
                            auto_fixable=True
                        ))
                        
        visitor = RouteVisitor(self)
        visitor.visit(tree)
        
    def _analyze_request_handling(self, tree: ast.AST, file_path: Path, content: str):
        """Analyze request object usage"""
        lines = content.split('\n')
        
        request_patterns = [
            (r'request\.json', 'request_body'),
            (r'request\.get_json\(\)', 'request_body'),
            (r'request\.form', 'form_data'),
            (r'request\.values', 'form_data'),
            (r'request\.files', 'uploaded_files'),
            (r'request\.args\.get\(["\'](\w+)["\']\)', r'query_param: Optional[str] = Query(None)'),
            (r'request\.args\[["\'](\w+)["\']\]', r'query_param: str = Query(...)'),
            (r'request\.headers\.get\(["\'](\w+)["\']\)', r'header_param: Optional[str] = Header(None)'),
            (r'request\.cookies\.get\(["\'](\w+)["\']\)', r'cookie_param: Optional[str] = Cookie(None)'),
        ]
        
        for i, line in enumerate(lines):
            for pattern, replacement in request_patterns:
                if re.search(pattern, line):
                    self.issues.append(MigrationIssue(
                        file_path=str(file_path),
                        line_number=i + 1,
                        issue_type='request_handling',
                        original_code=line.strip(),
                        suggested_code=re.sub(pattern, replacement, line).strip(),
                        description='Convert Flask request handling to FastAPI pattern',
                        confidence=0.8,
                        auto_fixable=True
                    ))
                    
    def _analyze_response_handling(self, content: str, file_path: Path):
        """Analyze response patterns"""
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            for pattern, replacement in self.RESPONSE_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    new_line = re.sub(pattern, replacement, line)
                    self.issues.append(MigrationIssue(
                        file_path=str(file_path),
                        line_number=i + 1,
                        issue_type='response_handling',
                        original_code=line.strip(),
                        suggested_code=new_line.strip(),
                        description='Convert Flask response to FastAPI pattern',
                        confidence=0.9,
                        auto_fixable=True
                    ))
                    
    def _analyze_database_operations(self, tree: ast.AST, file_path: Path, content: str):
        """Analyze database operations and SQLAlchemy usage"""
        lines = content.split('\n')
        
        # Look for Flask-SQLAlchemy patterns
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == 'db':
                    line = lines[node.lineno - 1] if node.lineno <= len(lines) else ''
                    
                    if node.attr == 'session':
                        self.issues.append(MigrationIssue(
                            file_path=str(file_path),
                            line_number=node.lineno,
                            issue_type='database_session',
                            original_code=line.strip(),
                            suggested_code='# TODO: Use dependency injection for database session',
                            description='Flask-SQLAlchemy db.session needs to be replaced with dependency injection',
                            confidence=0.7,
                            auto_fixable=False
                        ))
                        
    def _analyze_authentication(self, tree: ast.AST, file_path: Path, content: str):
        """Analyze authentication patterns"""
        lines = content.split('\n')
        
        # Look for Flask-Login patterns
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == 'current_user':
                line = lines[node.lineno - 1] if node.lineno <= len(lines) else ''
                self.issues.append(MigrationIssue(
                    file_path=str(file_path),
                    line_number=node.lineno,
                    issue_type='authentication',
                    original_code=line.strip(),
                    suggested_code='# TODO: Implement current_user as a FastAPI dependency',
                    description='Flask-Login current_user needs FastAPI dependency implementation',
                    confidence=0.7,
                    auto_fixable=False
                ))
                
    def _analyze_project_structure(self, context: MigrationContext):
        """Analyze overall project structure"""
        # Check for application factory pattern
        app_py = context.project_root / 'app.py'
        init_py = context.project_root / '__init__.py'
        
        if app_py.exists():
            self.issues.append(MigrationIssue(
                file_path=str(app_py),
                line_number=0,
                issue_type='project_structure',
                original_code='app = Flask(__name__)',
                suggested_code='app = FastAPI()',
                description='Replace Flask app initialization with FastAPI',
                confidence=0.95,
                auto_fixable=True
            ))
            
        # Check for blueprints
        for file_path in context.files_to_migrate:
            if 'blueprint' in str(file_path).lower() or 'bp' in str(file_path).lower():
                self.issues.append(MigrationIssue(
                    file_path=str(file_path),
                    line_number=0,
                    issue_type='project_structure',
                    original_code='Blueprint',
                    suggested_code='APIRouter',
                    description='Convert Flask Blueprint to FastAPI APIRouter',
                    confidence=0.9,
                    auto_fixable=True
                ))
                
    def _analyze_dependencies(self, context: MigrationContext):
        """Analyze and update dependencies"""
        # Remove Flask dependencies
        flask_deps = ['Flask', 'flask', 'Flask-Login', 'Flask-SQLAlchemy', 'Flask-CORS', 'Flask-WTF']
        for dep in flask_deps:
            if dep in context.dependencies or dep.lower() in context.dependencies:
                context.removed_dependencies.add(dep)
                
        # Add FastAPI dependencies
        context.new_dependencies.update({
            'fastapi': 'latest',
            'uvicorn': 'latest',
            'python-multipart': 'latest',  # For form data
            'pydantic': 'latest',
            'python-jose[cryptography]': 'latest',  # For JWT
            'passlib[bcrypt]': 'latest',  # For password hashing
            'sqlalchemy': 'latest',  # Direct SQLAlchemy instead of Flask-SQLAlchemy
        })
        
    def generate_migration_plan(self, issues: List[MigrationIssue]) -> str:
        """Generate a detailed migration plan"""
        plan = []
        plan.append("# Flask to FastAPI Migration Plan\n")
        plan.append("## Overview")
        plan.append(f"Total issues identified: {len(issues)}\n")
        
        # Group issues by type
        issues_by_type = defaultdict(list)
        for issue in issues:
            issues_by_type[issue.issue_type].append(issue)
            
        # Auto-fixable vs manual
        auto_fixable = [i for i in issues if i.auto_fixable]
        manual = [i for i in issues if not i.auto_fixable]
        
        plan.append(f"- Auto-fixable issues: {len(auto_fixable)}")
        plan.append(f"- Manual intervention required: {len(manual)}\n")
        
        # Detailed breakdown
        plan.append("## Issue Breakdown\n")
        
        for issue_type, type_issues in issues_by_type.items():
            plan.append(f"### {issue_type.replace('_', ' ').title()}")
            plan.append(f"**Count:** {len(type_issues)}\n")
            
            # Show examples (up to 3)
            for issue in type_issues[:3]:
                plan.append(f"**File:** `{issue.file_path}` (line {issue.line_number})")
                plan.append(f"**Original:** `{issue.original_code}`")
                plan.append(f"**Suggested:** `{issue.suggested_code}`")
                plan.append(f"**Note:** {issue.description}\n")
                
            if len(type_issues) > 3:
                plan.append(f"... and {len(type_issues) - 3} more\n")
                
        # Migration steps
        plan.append("## Recommended Migration Steps\n")
        plan.append("1. **Backup your code** - Create a new branch for migration")
        plan.append("2. **Update dependencies** - Replace Flask packages with FastAPI equivalents")
        plan.append("3. **Run automatic fixes** - Use `--apply-fixes` to apply auto-fixable changes")
        plan.append("4. **Update application structure**:")
        plan.append("   - Replace Flask() with FastAPI()")
        plan.append("   - Convert Blueprints to APIRouters")
        plan.append("   - Update import statements")
        plan.append("5. **Update route handlers**:")
        plan.append("   - Convert route decorators")
        plan.append("   - Update function signatures")
        plan.append("   - Replace request handling")
        plan.append("6. **Implement missing features**:")
        plan.append("   - Authentication (JWT or session-based)")
        plan.append("   - Database session management")
        plan.append("   - Template rendering (if needed)")
        plan.append("7. **Update tests** - Modify tests to use FastAPI test client")
        plan.append("8. **Test thoroughly** - Ensure all endpoints work as expected\n")
        
        # Additional notes
        plan.append("## Important Notes\n")
        plan.append("- FastAPI uses type hints extensively - add them for better validation")
        plan.append("- Request validation is automatic with Pydantic models")
        plan.append("- Async functions are supported but not required")
        plan.append("- CORS middleware configuration differs from Flask-CORS")
        plan.append("- Session handling requires additional implementation")
        
        return '\n'.join(plan)
        
    def apply_fixes(self, issues: List[MigrationIssue], dry_run: bool = True) -> Dict[str, str]:
        """Apply automatic fixes to files"""
        modified_files = {}
        files_to_update = defaultdict(list)
        
        # Group issues by file
        for issue in issues:
            if issue.auto_fixable:
                files_to_update[issue.file_path].append(issue)
                
        # Process each file
        for file_path, file_issues in files_to_update.items():
            if file_path in self.file_contents:
                content = self.file_contents[file_path]
                lines = content.split('\n')
                
                # Sort issues by line number (descending) to avoid offset issues
                file_issues.sort(key=lambda x: x.line_number, reverse=True)
                
                for issue in file_issues:
                    if issue.line_number > 0 and issue.line_number <= len(lines):
                        if issue.issue_type == 'import_change':
                            # Replace entire import line
                            lines[issue.line_number - 1] = issue.suggested_code
                        elif issue.issue_type in ['route_decorator', 'function_signature', 
                                                'request_handling', 'response_handling']:
                            # Replace line with suggested code
                            lines[issue.line_number - 1] = issue.suggested_code
                            
                modified_content = '\n'.join(lines)
                modified_files[file_path] = modified_content
                
                if not dry_run:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                        
        return modified_files


class CodeMigrationAssistant:
    """Main migration assistant that coordinates different migrators"""
    
    SUPPORTED_MIGRATIONS = {
        ('flask', 'fastapi'): FlaskToFastAPIMigrator,
        # Future: ('django', 'fastapi'): DjangoToFastAPIMigrator,
        # Future: ('express', 'fastapi'): ExpressToFastAPIMigrator,
    }
    
    def __init__(self, project_root: str, source_framework: str, target_framework: str):
        self.project_root = Path(project_root).resolve()
        self.source_framework = source_framework.lower()
        self.target_framework = target_framework.lower()
        
        # Get appropriate migrator
        migration_key = (self.source_framework, self.target_framework)
        if migration_key not in self.SUPPORTED_MIGRATIONS:
            raise ValueError(f"Migration from {source_framework} to {target_framework} is not supported")
            
        self.migrator = self.SUPPORTED_MIGRATIONS[migration_key]()
        
    def analyze_project(self, file_pattern: str = "**/*.py") -> MigrationContext:
        """Analyze the project and create migration context"""
        # Find all matching files
        files_to_migrate = list(self.project_root.glob(file_pattern))
        
        # Filter out common directories to ignore
        ignore_patterns = ['__pycache__', '.git', '.venv', 'venv', 'env', 
                         'build', 'dist', '.tox', '.pytest_cache']
        
        files_to_migrate = [
            f for f in files_to_migrate 
            if not any(pattern in str(f) for pattern in ignore_patterns)
        ]
        
        # Load current dependencies
        dependencies = self._load_dependencies()
        
        context = MigrationContext(
            source_framework=self.source_framework,
            target_framework=self.target_framework,
            project_root=self.project_root,
            files_to_migrate=files_to_migrate,
            dependencies=dependencies,
            new_dependencies={},
            removed_dependencies=set()
        )
        
        return context
        
    def _load_dependencies(self) -> Dict[str, str]:
        """Load current project dependencies"""
        dependencies = {}
        
        # Check requirements.txt
        req_file = self.project_root / 'requirements.txt'
        if req_file.exists():
            with open(req_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '==' in line:
                            pkg, version = line.split('==', 1)
                            dependencies[pkg.strip()] = version.strip()
                        else:
                            dependencies[line] = 'latest'
                            
        # Check pyproject.toml
        pyproject = self.project_root / 'pyproject.toml'
        if pyproject.exists():
            try:
                import toml
                data = toml.load(pyproject)
                if 'tool' in data and 'poetry' in data['tool']:
                    deps = data['tool']['poetry'].get('dependencies', {})
                    dependencies.update(deps)
            except ImportError:
                pass
                
        return dependencies
        
    def run_migration(self, apply_fixes: bool = False, output_format: str = 'text') -> Dict[str, Any]:
        """Run the migration analysis and optionally apply fixes"""
        # Create context
        context = self.analyze_project()
        
        # Run analysis
        issues = self.migrator.analyze(context)
        
        # Generate migration plan
        plan = self.migrator.generate_migration_plan(issues)
        
        # Apply fixes if requested
        modified_files = {}
        if apply_fixes:
            modified_files = self.migrator.apply_fixes(issues, dry_run=False)
            
        # Prepare results
        results = {
            'source_framework': self.source_framework,
            'target_framework': self.target_framework,
            'total_files': len(context.files_to_migrate),
            'total_issues': len(issues),
            'auto_fixable': len([i for i in issues if i.auto_fixable]),
            'manual_fixes': len([i for i in issues if not i.auto_fixable]),
            'issues': issues,
            'migration_plan': plan,
            'modified_files': list(modified_files.keys()) if modified_files else [],
            'new_dependencies': context.new_dependencies,
            'removed_dependencies': list(context.removed_dependencies)
        }
        
        return results
        
    def generate_report(self, results: Dict[str, Any], output_format: str = 'text') -> str:
        """Generate a migration report"""
        if output_format == 'json':
            # Convert issues to dict for JSON serialization
            results_copy = results.copy()
            results_copy['issues'] = [
                {
                    'file_path': issue.file_path,
                    'line_number': issue.line_number,
                    'issue_type': issue.issue_type,
                    'original_code': issue.original_code,
                    'suggested_code': issue.suggested_code,
                    'description': issue.description,
                    'confidence': issue.confidence,
                    'auto_fixable': issue.auto_fixable
                }
                for issue in results['issues']
            ]
            return json.dumps(results_copy, indent=2)
            
        else:  # text format
            report = []
            report.append("=" * 80)
            report.append(f"CODE MIGRATION REPORT: {results['source_framework'].upper()} → {results['target_framework'].upper()}")
            report.append("=" * 80)
            report.append(f"\nFiles analyzed: {results['total_files']}")
            report.append(f"Total issues found: {results['total_issues']}")
            report.append(f"Auto-fixable: {results['auto_fixable']}")
            report.append(f"Manual intervention required: {results['manual_fixes']}")
            
            if results['modified_files']:
                report.append(f"\nFiles modified: {len(results['modified_files'])}")
                for f in results['modified_files'][:10]:
                    report.append(f"  - {f}")
                if len(results['modified_files']) > 10:
                    report.append(f"  ... and {len(results['modified_files']) - 10} more")
                    
            report.append("\n" + "-" * 80)
            report.append("MIGRATION PLAN")
            report.append("-" * 80)
            report.append(results['migration_plan'])
            
            if results['new_dependencies']:
                report.append("\n" + "-" * 80)
                report.append("DEPENDENCIES TO ADD")
                report.append("-" * 80)
                for dep, version in results['new_dependencies'].items():
                    report.append(f"  {dep}=={version}")
                    
            if results['removed_dependencies']:
                report.append("\n" + "-" * 80)
                report.append("DEPENDENCIES TO REMOVE")
                report.append("-" * 80)
                for dep in results['removed_dependencies']:
                    report.append(f"  {dep}")
                    
            return '\n'.join(report)


def main():
    """CLI interface for the code migration assistant"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Code Migration Assistant - Helps migrate between frameworks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze Flask to FastAPI migration
  python code_migration_assistant.py /path/to/project flask fastapi
  
  # Apply automatic fixes
  python code_migration_assistant.py /path/to/project flask fastapi --apply-fixes
  
  # Output results as JSON
  python code_migration_assistant.py /path/to/project flask fastapi --json
  
  # Analyze specific files only
  python code_migration_assistant.py /path/to/project flask fastapi --pattern "src/**/*.py"
  
Supported migrations:
  - Flask → FastAPI
  
Future support planned for:
  - Django → FastAPI
  - Express.js → FastAPI
  - Rails → FastAPI
        """
    )
    
    parser.add_argument('project_path', help='Path to the project root')
    parser.add_argument('source_framework', help='Source framework (e.g., flask)')
    parser.add_argument('target_framework', help='Target framework (e.g., fastapi)')
    parser.add_argument('--pattern', default='**/*.py',
                       help='File pattern to analyze (default: **/*.py)')
    parser.add_argument('--apply-fixes', action='store_true',
                       help='Apply automatic fixes to files')
    parser.add_argument('--json', action='store_true',
                       help='Output results in JSON format')
    parser.add_argument('--output', '-o', help='Write report to file instead of stdout')
    
    args = parser.parse_args()
    
    try:
        # Create migration assistant
        assistant = CodeMigrationAssistant(
            args.project_path,
            args.source_framework,
            args.target_framework
        )
        
        # Run migration analysis
        results = assistant.run_migration(
            apply_fixes=args.apply_fixes,
            output_format='json' if args.json else 'text'
        )
        
        # Generate report
        report = assistant.generate_report(results, 'json' if args.json else 'text')
        
        # Output report
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"Report written to: {args.output}")
        else:
            print(report)
            
        # Exit with error if manual fixes are required
        if results['manual_fixes'] > 0 and args.apply_fixes:
            sys.exit(1)
            
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()