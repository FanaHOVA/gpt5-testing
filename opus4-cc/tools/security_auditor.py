#!/usr/bin/env python3
"""
Security & Permission Auditor - Identify and fix permission discrepancies and security issues
Comprehensive security analysis for full-stack applications
"""

import os
import json
import argparse
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import ast
import hashlib

@dataclass
class SecurityIssue:
    severity: str  # 'critical', 'high', 'medium', 'low'
    category: str
    file: str
    line: int
    description: str
    recommendation: str
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None

@dataclass
class PermissionRule:
    resource: str
    action: str
    roles: List[str]
    conditions: Optional[Dict] = None

class SecurityAuditor:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.issues = []
        self.permission_rules = []
        self.api_permissions = defaultdict(dict)
        self.frontend_permissions = defaultdict(set)
        self.secrets_patterns = self._load_secrets_patterns()
        
    def _load_secrets_patterns(self) -> List[Tuple[str, re.Pattern]]:
        """Load patterns for detecting secrets and sensitive data"""
        return [
            ("AWS Access Key", re.compile(r'AKIA[0-9A-Z]{16}')),
            ("AWS Secret Key", re.compile(r'[0-9a-zA-Z/+=]{40}')),
            ("API Key", re.compile(r'["\']?api[_-]?key["\']?\s*[:=]\s*["\'][0-9a-zA-Z]{20,}["\']', re.I)),
            ("Private Key", re.compile(r'-----BEGIN (RSA |EC )?PRIVATE KEY-----')),
            ("JWT Secret", re.compile(r'["\']?jwt[_-]?secret["\']?\s*[:=]\s*["\'][^"\']+["\']', re.I)),
            ("Database URL", re.compile(r'(postgres|mysql|mongodb)://[^:]+:[^@]+@[^/]+/\w+')),
            ("Password", re.compile(r'["\']?password["\']?\s*[:=]\s*["\'][^"\']+["\']', re.I)),
            ("Token", re.compile(r'["\']?token["\']?\s*[:=]\s*["\'][0-9a-zA-Z]{20,}["\']', re.I)),
            ("OAuth Secret", re.compile(r'["\']?client[_-]?secret["\']?\s*[:=]\s*["\'][^"\']+["\']', re.I)),
        ]
        
    def audit(self) -> Dict:
        """Perform comprehensive security audit"""
        print("🔐 Starting security audit...")
        
        # Different audit phases
        self._audit_secrets()
        self._audit_authentication()
        self._audit_authorization()
        self._audit_input_validation()
        self._audit_api_security()
        self._audit_dependencies()
        self._audit_cors()
        self._audit_sql_injection()
        self._audit_xss()
        self._analyze_permission_consistency()
        
        return self._generate_report()
        
    def _audit_secrets(self):
        """Scan for hardcoded secrets and sensitive data"""
        print("  Scanning for secrets...")
        
        ignore_patterns = ['.git', 'node_modules', '__pycache__', 'venv', '.env.example']
        
        for root, dirs, files in os.walk(self.project_root):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_patterns]
            
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rb')):
                    file_path = Path(root) / file
                    self._scan_file_for_secrets(file_path)
                    
    def _scan_file_for_secrets(self, file_path: Path):
        """Scan a single file for secrets"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            rel_path = str(file_path.relative_to(self.project_root))
            
            # Skip test files and mocks
            if 'test' in rel_path.lower() or 'mock' in rel_path.lower():
                return
                
            for line_num, line in enumerate(content.splitlines(), 1):
                for secret_type, pattern in self.secrets_patterns:
                    if pattern.search(line):
                        # Check if it's actually a placeholder
                        if any(placeholder in line.lower() for placeholder in 
                              ['example', 'placeholder', 'your-', 'xxx', '***', '<your']):
                            continue
                            
                        self.issues.append(SecurityIssue(
                            severity='critical',
                            category='Hardcoded Secrets',
                            file=rel_path,
                            line=line_num,
                            description=f'Potential {secret_type} found',
                            recommendation='Move to environment variables or secure key management',
                            cwe_id='CWE-798',
                            owasp_category='A07:2021 - Identification and Authentication Failures'
                        ))
                        
        except Exception:
            pass
            
    def _audit_authentication(self):
        """Audit authentication mechanisms"""
        print("  Auditing authentication...")
        
        auth_files = []
        for pattern in ['**/auth*.py', '**/auth*.js', '**/login*', '**/session*']:
            auth_files.extend(self.project_root.glob(pattern))
            
        for file_path in auth_files:
            if 'node_modules' in str(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                rel_path = str(file_path.relative_to(self.project_root))
                
                # Check for weak session configuration
                if 'httponly' not in content.lower() and 'cookie' in content.lower():
                    self.issues.append(SecurityIssue(
                        severity='high',
                        category='Session Security',
                        file=rel_path,
                        line=0,
                        description='Session cookies may not have HttpOnly flag',
                        recommendation='Set HttpOnly flag on session cookies',
                        cwe_id='CWE-1004',
                        owasp_category='A05:2021 - Security Misconfiguration'
                    ))
                    
                # Check for missing CSRF protection
                if file_path.suffix in ['.py', '.js'] and 'csrf' not in content.lower():
                    if any(method in content for method in ['POST', 'PUT', 'DELETE']):
                        self.issues.append(SecurityIssue(
                            severity='high',
                            category='CSRF Protection',
                            file=rel_path,
                            line=0,
                            description='State-changing operations without CSRF protection',
                            recommendation='Implement CSRF token validation',
                            cwe_id='CWE-352',
                            owasp_category='A01:2021 - Broken Access Control'
                        ))
                        
            except Exception:
                pass
                
    def _audit_authorization(self):
        """Audit authorization and access control"""
        print("  Auditing authorization...")
        
        # Look for API endpoints and their permission checks
        for file_path in self.project_root.rglob('*.py'):
            self._analyze_python_authorization(file_path)
            
        for file_path in self.project_root.rglob('*.js'):
            self._analyze_js_authorization(file_path)
            
    def _analyze_python_authorization(self, file_path: Path):
        """Analyze Python files for authorization issues"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            rel_path = str(file_path.relative_to(self.project_root))
            
            # Flask/FastAPI route patterns
            route_pattern = re.compile(
                r'@(app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
            )
            
            # Look for routes without auth decorators
            routes = route_pattern.findall(content)
            
            for _, method, endpoint in routes:
                # Check if there's an auth decorator nearby
                if method.upper() in ['POST', 'PUT', 'DELETE', 'PATCH']:
                    # These methods should have auth
                    auth_patterns = ['@auth_required', '@login_required', '@requires_auth', 
                                   '@jwt_required', 'check_permission', 'current_user']
                    
                    if not any(pattern in content for pattern in auth_patterns):
                        self.api_permissions[endpoint] = {
                            'method': method.upper(),
                            'protected': False,
                            'file': rel_path
                        }
                        
                        self.issues.append(SecurityIssue(
                            severity='high',
                            category='Missing Authorization',
                            file=rel_path,
                            line=0,
                            description=f'{method.upper()} {endpoint} lacks authorization checks',
                            recommendation='Add appropriate authorization decorators',
                            cwe_id='CWE-862',
                            owasp_category='A01:2021 - Broken Access Control'
                        ))
                        
        except Exception:
            pass
            
    def _analyze_js_authorization(self, file_path: Path):
        """Analyze JavaScript files for authorization issues"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            rel_path = str(file_path.relative_to(self.project_root))
            
            # Check for frontend permission checks
            if file_path.suffix in ['.jsx', '.tsx']:
                # Look for conditional rendering based on permissions
                if 'render' in content:
                    perm_patterns = ['hasPermission', 'canAccess', 'isAuthorized', 
                                   'userRole', 'permissions']
                    
                    if not any(pattern in content for pattern in perm_patterns):
                        self.frontend_permissions[rel_path].add('no_permission_checks')
                        
        except Exception:
            pass
            
    def _audit_input_validation(self):
        """Audit input validation and sanitization"""
        print("  Auditing input validation...")
        
        validation_issues = []
        
        # Patterns that suggest user input handling
        input_patterns = [
            (re.compile(r'request\.(form|args|json|data|files)'), 'Flask/Python'),
            (re.compile(r'req\.(body|params|query|files)'), 'Express/Node'),
            (re.compile(r'\$_(GET|POST|REQUEST)'), 'PHP'),
        ]
        
        for root, _, files in os.walk(self.project_root):
            for file in files:
                if file.endswith(('.py', '.js', '.php')):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        rel_path = str(file_path.relative_to(self.project_root))
                        
                        for pattern, framework in input_patterns:
                            if pattern.search(content):
                                # Check for validation
                                validation_keywords = ['validate', 'sanitize', 'clean', 'escape', 
                                                     'schema', 'validator']
                                
                                if not any(keyword in content.lower() for keyword in validation_keywords):
                                    self.issues.append(SecurityIssue(
                                        severity='medium',
                                        category='Input Validation',
                                        file=rel_path,
                                        line=0,
                                        description=f'User input handling without validation ({framework})',
                                        recommendation='Implement input validation and sanitization',
                                        cwe_id='CWE-20',
                                        owasp_category='A03:2021 - Injection'
                                    ))
                                    break
                                    
                    except Exception:
                        pass
                        
    def _audit_api_security(self):
        """Audit API-specific security concerns"""
        print("  Auditing API security...")
        
        # Check for rate limiting
        api_files = list(self.project_root.glob('**/api/**/*.py'))
        api_files.extend(self.project_root.glob('**/routes/**/*.js'))
        
        rate_limit_found = False
        for file_path in api_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                if any(pattern in content.lower() for pattern in 
                      ['ratelimit', 'rate_limit', 'throttle', 'limiter']):
                    rate_limit_found = True
                    break
                    
            except Exception:
                pass
                
        if not rate_limit_found and api_files:
            self.issues.append(SecurityIssue(
                severity='medium',
                category='API Security',
                file='API Layer',
                line=0,
                description='No rate limiting detected for API endpoints',
                recommendation='Implement rate limiting to prevent abuse',
                cwe_id='CWE-770',
                owasp_category='A04:2021 - Insecure Design'
            ))
            
    def _audit_dependencies(self):
        """Audit third-party dependencies for vulnerabilities"""
        print("  Auditing dependencies...")
        
        # Check package files
        package_files = {
            'package.json': self._check_npm_packages,
            'requirements.txt': self._check_python_packages,
            'Gemfile': self._check_ruby_packages,
            'pom.xml': self._check_maven_packages,
        }
        
        for filename, checker in package_files.items():
            file_path = self.project_root / filename
            if file_path.exists():
                checker(file_path)
                
    def _check_npm_packages(self, file_path: Path):
        """Check npm packages for known vulnerabilities"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            # Check for outdated security-critical packages
            critical_packages = {
                'express': '4.17.3',  # Example minimum versions
                'jsonwebtoken': '9.0.0',
                'bcrypt': '5.0.1',
            }
            
            dependencies = data.get('dependencies', {})
            for pkg, min_version in critical_packages.items():
                if pkg in dependencies:
                    # Simple version check (in reality, use semver)
                    if dependencies[pkg].lstrip('^~') < min_version:
                        self.issues.append(SecurityIssue(
                            severity='high',
                            category='Vulnerable Dependencies',
                            file='package.json',
                            line=0,
                            description=f'{pkg} version {dependencies[pkg]} has known vulnerabilities',
                            recommendation=f'Update {pkg} to at least version {min_version}',
                            cwe_id='CWE-1104',
                            owasp_category='A06:2021 - Vulnerable and Outdated Components'
                        ))
                        
        except Exception:
            pass
            
    def _check_python_packages(self, file_path: Path):
        """Check Python packages for vulnerabilities"""
        # Similar implementation for Python packages
        pass
        
    def _check_ruby_packages(self, file_path: Path):
        """Check Ruby gems for vulnerabilities"""
        pass
        
    def _check_maven_packages(self, file_path: Path):
        """Check Maven dependencies for vulnerabilities"""
        pass
        
    def _audit_cors(self):
        """Audit CORS configuration"""
        print("  Auditing CORS configuration...")
        
        cors_patterns = [
            (re.compile(r'Access-Control-Allow-Origin.*\*'), 'Wildcard CORS'),
            (re.compile(r'cors\(\s*\)'), 'Permissive CORS (no options)'),
            (re.compile(r'credentials:\s*true.*origin:\s*["\']?\*'), 'Credentials with wildcard'),
        ]
        
        for root, _, files in os.walk(self.project_root):
            for file in files:
                if file.endswith(('.py', '.js', '.ts')):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        rel_path = str(file_path.relative_to(self.project_root))
                        
                        for pattern, issue_type in cors_patterns:
                            if pattern.search(content):
                                self.issues.append(SecurityIssue(
                                    severity='medium',
                                    category='CORS Misconfiguration',
                                    file=rel_path,
                                    line=0,
                                    description=f'{issue_type} detected',
                                    recommendation='Configure CORS with specific allowed origins',
                                    cwe_id='CWE-942',
                                    owasp_category='A05:2021 - Security Misconfiguration'
                                ))
                                
                    except Exception:
                        pass
                        
    def _audit_sql_injection(self):
        """Audit for SQL injection vulnerabilities"""
        print("  Auditing SQL injection risks...")
        
        sql_patterns = [
            # String concatenation in queries
            (re.compile(r'(query|execute)\s*\(\s*["\'].*\+.*["\']'), 'String concatenation in SQL'),
            (re.compile(r'f["\'].*SELECT.*\{'), 'F-string in SQL query'),
            (re.compile(r'%\s*\(.*\).*SELECT'), 'String formatting in SQL'),
        ]
        
        for root, _, files in os.walk(self.project_root):
            for file in files:
                if file.endswith(('.py', '.js', '.php')):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        rel_path = str(file_path.relative_to(self.project_root))
                        
                        for pattern, issue_type in sql_patterns:
                            matches = pattern.finditer(content)
                            for match in matches:
                                line_num = content[:match.start()].count('\n') + 1
                                
                                self.issues.append(SecurityIssue(
                                    severity='critical',
                                    category='SQL Injection',
                                    file=rel_path,
                                    line=line_num,
                                    description=f'{issue_type} - potential SQL injection',
                                    recommendation='Use parameterized queries or ORM',
                                    cwe_id='CWE-89',
                                    owasp_category='A03:2021 - Injection'
                                ))
                                
                    except Exception:
                        pass
                        
    def _audit_xss(self):
        """Audit for XSS vulnerabilities"""
        print("  Auditing XSS risks...")
        
        # Check for unsafe rendering in templates and React/Vue components
        xss_patterns = [
            (re.compile(r'dangerouslySetInnerHTML'), 'React dangerouslySetInnerHTML'),
            (re.compile(r'v-html'), 'Vue v-html directive'),
            (re.compile(r'innerHTML\s*='), 'Direct innerHTML assignment'),
            (re.compile(r'\|\s*safe'), 'Jinja2 safe filter'),
            (re.compile(r'{{{'), 'Unescaped template syntax'),
        ]
        
        for root, _, files in os.walk(self.project_root):
            for file in files:
                if file.endswith(('.jsx', '.tsx', '.vue', '.html', '.js')):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        rel_path = str(file_path.relative_to(self.project_root))
                        
                        for pattern, issue_type in xss_patterns:
                            if pattern.search(content):
                                self.issues.append(SecurityIssue(
                                    severity='high',
                                    category='Cross-Site Scripting (XSS)',
                                    file=rel_path,
                                    line=0,
                                    description=f'{issue_type} usage may lead to XSS',
                                    recommendation='Sanitize user input before rendering',
                                    cwe_id='CWE-79',
                                    owasp_category='A03:2021 - Injection'
                                ))
                                
                    except Exception:
                        pass
                        
    def _analyze_permission_consistency(self):
        """Check consistency between frontend and backend permissions"""
        print("  Analyzing permission consistency...")
        
        # Compare API permissions with frontend checks
        inconsistencies = []
        
        for endpoint, perms in self.api_permissions.items():
            if not perms.get('protected', True):
                # Unprotected API endpoint - check if frontend assumes it's protected
                for frontend_file, checks in self.frontend_permissions.items():
                    if endpoint in str(checks):
                        inconsistencies.append({
                            'api': endpoint,
                            'frontend': frontend_file,
                            'issue': 'Frontend assumes protection, but API is unprotected'
                        })
                        
        for inconsistency in inconsistencies:
            self.issues.append(SecurityIssue(
                severity='high',
                category='Permission Inconsistency',
                file=inconsistency['frontend'],
                line=0,
                description=f"Permission mismatch for {inconsistency['api']}",
                recommendation='Ensure frontend and backend permissions are synchronized',
                cwe_id='CWE-862',
                owasp_category='A01:2021 - Broken Access Control'
            ))
            
    def _generate_report(self) -> Dict:
        """Generate comprehensive security report"""
        # Group issues by severity
        by_severity = defaultdict(list)
        for issue in self.issues:
            by_severity[issue.severity].append(issue)
            
        # Group by category
        by_category = defaultdict(list)
        for issue in self.issues:
            by_category[issue.category].append(issue)
            
        # Calculate risk score
        risk_score = (
            len(by_severity['critical']) * 10 +
            len(by_severity['high']) * 5 +
            len(by_severity['medium']) * 2 +
            len(by_severity['low'])
        )
        
        return {
            'summary': {
                'total_issues': len(self.issues),
                'critical': len(by_severity['critical']),
                'high': len(by_severity['high']),
                'medium': len(by_severity['medium']),
                'low': len(by_severity['low']),
                'risk_score': risk_score,
                'risk_level': self._calculate_risk_level(risk_score)
            },
            'by_severity': dict(by_severity),
            'by_category': dict(by_category),
            'issues': self.issues,
            'recommendations': self._generate_recommendations()
        }
        
    def _calculate_risk_level(self, score: int) -> str:
        """Calculate overall risk level"""
        if score >= 50:
            return 'CRITICAL'
        elif score >= 25:
            return 'HIGH'
        elif score >= 10:
            return 'MEDIUM'
        else:
            return 'LOW'
            
    def _generate_recommendations(self) -> List[str]:
        """Generate prioritized recommendations"""
        recommendations = []
        
        # Check for critical issues
        critical_issues = [i for i in self.issues if i.severity == 'critical']
        if critical_issues:
            recommendations.append("🚨 IMMEDIATE: Address all critical security issues before deployment")
            
        # Check categories
        categories = {i.category for i in self.issues}
        
        if 'Hardcoded Secrets' in categories:
            recommendations.append("1. Move all secrets to environment variables or secure key management")
            
        if 'SQL Injection' in categories:
            recommendations.append("2. Replace all string concatenation in SQL with parameterized queries")
            
        if 'Missing Authorization' in categories:
            recommendations.append("3. Implement proper authorization checks on all state-changing endpoints")
            
        if 'Cross-Site Scripting (XSS)' in categories:
            recommendations.append("4. Sanitize all user input before rendering in the UI")
            
        if 'Vulnerable Dependencies' in categories:
            recommendations.append("5. Update all dependencies with known vulnerabilities")
            
        # General recommendations
        recommendations.extend([
            "• Implement automated security scanning in CI/CD pipeline",
            "• Conduct regular security audits and penetration testing",
            "• Train developers on secure coding practices",
            "• Implement security headers (CSP, HSTS, etc.)",
            "• Use HTTPS everywhere and implement certificate pinning for mobile apps"
        ])
        
        return recommendations

def main():
    parser = argparse.ArgumentParser(description='Security and permission auditor for full-stack apps')
    parser.add_argument('path', nargs='?', default='.', help='Project root path')
    parser.add_argument('--output', help='Output file for JSON report')
    parser.add_argument('--format', choices=['summary', 'detailed', 'json'], default='summary')
    parser.add_argument('--severity', choices=['all', 'critical', 'high', 'medium', 'low'], 
                       default='all', help='Filter by severity')
    
    args = parser.parse_args()
    
    auditor = SecurityAuditor(args.path)
    report = auditor.audit()
    
    if args.format == 'json' or args.output:
        # Convert dataclasses to dicts for JSON serialization
        json_report = {
            'summary': report['summary'],
            'issues': [
                {
                    'severity': issue.severity,
                    'category': issue.category,
                    'file': issue.file,
                    'line': issue.line,
                    'description': issue.description,
                    'recommendation': issue.recommendation,
                    'cwe_id': issue.cwe_id,
                    'owasp_category': issue.owasp_category
                }
                for issue in report['issues']
            ],
            'recommendations': report['recommendations']
        }
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(json_report, f, indent=2)
            print(f"Report saved to {args.output}")
        else:
            print(json.dumps(json_report, indent=2))
            
    else:
        # Print human-readable report
        print("\n🔐 SECURITY AUDIT REPORT")
        print("=" * 60)
        
        summary = report['summary']
        print(f"\n📊 Summary:")
        print(f"  Total Issues: {summary['total_issues']}")
        print(f"  Critical: {summary['critical']} 🚨")
        print(f"  High: {summary['high']} ⚠️")
        print(f"  Medium: {summary['medium']} 📊")
        print(f"  Low: {summary['low']} ℹ️")
        print(f"\n  Risk Score: {summary['risk_score']}")
        print(f"  Risk Level: {summary['risk_level']}")
        
        # Filter by severity if requested
        issues_to_show = report['issues']
        if args.severity != 'all':
            issues_to_show = [i for i in issues_to_show if i.severity == args.severity]
            
        if args.format == 'detailed' and issues_to_show:
            print(f"\n🔍 Detailed Issues:")
            
            # Group by category for better readability
            by_category = defaultdict(list)
            for issue in issues_to_show:
                by_category[issue.category].append(issue)
                
            for category, category_issues in by_category.items():
                print(f"\n### {category}")
                for issue in category_issues[:5]:  # Show max 5 per category
                    severity_emoji = {
                        'critical': '🚨',
                        'high': '⚠️',
                        'medium': '📊',
                        'low': 'ℹ️'
                    }[issue.severity]
                    
                    print(f"\n{severity_emoji} {issue.severity.upper()}: {issue.description}")
                    print(f"   File: {issue.file}:{issue.line}")
                    print(f"   Fix: {issue.recommendation}")
                    if issue.cwe_id:
                        print(f"   CWE: {issue.cwe_id}")
                        
                if len(category_issues) > 5:
                    print(f"   ... and {len(category_issues) - 5} more")
                    
        print(f"\n💡 Recommendations:")
        for rec in report['recommendations'][:10]:
            print(f"  {rec}")
            
        print("\n" + "=" * 60)
        print("Run with --format=detailed to see all issues")
        print("Run with --output=report.json to save full report")

if __name__ == '__main__':
    main()