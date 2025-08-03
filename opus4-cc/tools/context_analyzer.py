#!/usr/bin/env python3
"""
Context Analyzer Tool - Rapid codebase understanding for SWE-Lancer tasks
Provides dependency graphs, API mapping, and architectural overview
"""

import os
import ast
import json
import argparse
import subprocess
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
import re

class ContextAnalyzer:
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.dependencies = defaultdict(set)
        self.api_endpoints = []
        self.tech_stack = {}
        self.file_purposes = {}
        self.critical_paths = []
        
    def analyze(self):
        """Run full analysis on the codebase"""
        print(f"Analyzing codebase at {self.root_path}...")
        
        self.detect_tech_stack()
        self.analyze_dependencies()
        self.map_api_endpoints()
        self.identify_critical_paths()
        self.analyze_architecture()
        
        return self.generate_report()
    
    def detect_tech_stack(self):
        """Detect technologies and frameworks used"""
        tech_files = {
            'package.json': self._analyze_npm,
            'requirements.txt': self._analyze_python_requirements,
            'Gemfile': self._analyze_ruby,
            'pom.xml': self._analyze_maven,
            'build.gradle': self._analyze_gradle,
            'Cargo.toml': self._analyze_rust,
            'go.mod': self._analyze_go,
        }
        
        for file_name, analyzer in tech_files.items():
            file_path = self.root_path / file_name
            if file_path.exists():
                analyzer(file_path)
                
        # Detect frameworks from code patterns
        self._detect_frameworks_from_code()
        
    def _analyze_npm(self, path: Path):
        """Analyze package.json for JS/TS dependencies"""
        try:
            with open(path) as f:
                data = json.load(f)
                
            self.tech_stack['language'] = 'JavaScript/TypeScript'
            self.tech_stack['dependencies'] = {}
            
            for dep_type in ['dependencies', 'devDependencies']:
                if dep_type in data:
                    for pkg, version in data[dep_type].items():
                        self.tech_stack['dependencies'][pkg] = version
                        
                        # Identify key frameworks
                        if 'react' in pkg:
                            self.tech_stack['frontend'] = 'React'
                        elif 'vue' in pkg:
                            self.tech_stack['frontend'] = 'Vue'
                        elif 'angular' in pkg:
                            self.tech_stack['frontend'] = 'Angular'
                        elif 'express' in pkg:
                            self.tech_stack['backend'] = 'Express'
                        elif 'nest' in pkg:
                            self.tech_stack['backend'] = 'NestJS'
                            
        except Exception as e:
            print(f"Error analyzing package.json: {e}")
            
    def _analyze_python_requirements(self, path: Path):
        """Analyze requirements.txt for Python dependencies"""
        try:
            with open(path) as f:
                requirements = f.read().splitlines()
                
            self.tech_stack['language'] = 'Python'
            self.tech_stack['dependencies'] = {}
            
            for req in requirements:
                if '==' in req:
                    pkg, version = req.split('==')
                    self.tech_stack['dependencies'][pkg] = version
                    
                    # Identify frameworks
                    if 'django' in pkg.lower():
                        self.tech_stack['backend'] = 'Django'
                    elif 'flask' in pkg.lower():
                        self.tech_stack['backend'] = 'Flask'
                    elif 'fastapi' in pkg.lower():
                        self.tech_stack['backend'] = 'FastAPI'
                        
        except Exception as e:
            print(f"Error analyzing requirements.txt: {e}")
            
    def _analyze_ruby(self, path: Path):
        """Analyze Gemfile for Ruby dependencies"""
        self.tech_stack['language'] = 'Ruby'
        # Check for Rails
        with open(path) as f:
            content = f.read()
            if 'rails' in content:
                self.tech_stack['backend'] = 'Ruby on Rails'
                
    def _analyze_maven(self, path: Path):
        """Analyze pom.xml for Java dependencies"""
        self.tech_stack['language'] = 'Java'
        with open(path) as f:
            content = f.read()
            if 'spring' in content.lower():
                self.tech_stack['backend'] = 'Spring'
                
    def _analyze_gradle(self, path: Path):
        """Analyze build.gradle for Java/Kotlin dependencies"""
        self.tech_stack['language'] = 'Java/Kotlin'
        with open(path) as f:
            content = f.read()
            if 'spring' in content.lower():
                self.tech_stack['backend'] = 'Spring'
                
    def _analyze_rust(self, path: Path):
        """Analyze Cargo.toml for Rust dependencies"""
        self.tech_stack['language'] = 'Rust'
        
    def _analyze_go(self, path: Path):
        """Analyze go.mod for Go dependencies"""
        self.tech_stack['language'] = 'Go'
        
    def _detect_frameworks_from_code(self):
        """Detect frameworks from code patterns"""
        patterns = {
            'React Native': ['react-native', 'ReactNative'],
            'Flutter': ['flutter', 'dart:'],
            'SwiftUI': ['SwiftUI', '@State', '@Binding'],
            'UIKit': ['UIViewController', 'UIView'],
            'Android': ['androidx', 'android.', 'Activity'],
        }
        
        for root, _, files in os.walk(self.root_path):
            for file in files[:100]:  # Sample first 100 files
                if file.endswith(('.js', '.jsx', '.ts', '.tsx', '.swift', '.kt', '.java', '.dart')):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            content = f.read(1000)  # Read first 1KB
                            
                        for framework, markers in patterns.items():
                            if any(marker in content for marker in markers):
                                if 'mobile' not in self.tech_stack:
                                    self.tech_stack['mobile'] = []
                                if framework not in self.tech_stack['mobile']:
                                    self.tech_stack['mobile'].append(framework)
                    except:
                        pass
                        
    def analyze_dependencies(self):
        """Analyze code dependencies and imports"""
        for root, _, files in os.walk(self.root_path):
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')):
                    file_path = os.path.join(root, file)
                    self._analyze_file_dependencies(file_path)
                    
    def _analyze_file_dependencies(self, file_path: str):
        """Extract dependencies from a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            rel_path = os.path.relpath(file_path, self.root_path)
            
            if file_path.endswith('.py'):
                # Python imports
                imports = re.findall(r'(?:from|import)\s+([^\s]+)', content)
                for imp in imports:
                    self.dependencies[rel_path].add(imp.split('.')[0])
                    
            elif file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                # JavaScript/TypeScript imports
                imports = re.findall(r'(?:import|require)\s*\(?[\'"]([^\'\"]+)[\'\"]\)?', content)
                for imp in imports:
                    self.dependencies[rel_path].add(imp)
                    
        except Exception as e:
            pass
            
    def map_api_endpoints(self):
        """Map API endpoints in the codebase"""
        api_patterns = {
            # Express.js
            r'app\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'\"]+)[\'"]': 'express',
            r'router\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'\"]+)[\'"]': 'express',
            # Flask
            r'@app\.route\s*\(\s*[\'"]([^\'\"]+)[\'"].*methods=\[[\'"](\w+)[\'"]': 'flask',
            # Django
            r'path\s*\(\s*[\'"]([^\'\"]+)[\'"]': 'django',
            # FastAPI
            r'@app\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'\"]+)[\'"]': 'fastapi',
        }
        
        for root, _, files in os.walk(self.root_path):
            for file in files:
                if file.endswith(('.py', '.js', '.ts')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        for pattern, framework in api_patterns.items():
                            matches = re.findall(pattern, content)
                            for match in matches:
                                if isinstance(match, tuple):
                                    if len(match) == 2:
                                        method, path = match
                                    else:
                                        path = match[0]
                                        method = 'GET'
                                else:
                                    path = match
                                    method = 'GET'
                                    
                                self.api_endpoints.append({
                                    'path': path,
                                    'method': method.upper(),
                                    'file': os.path.relpath(file_path, self.root_path),
                                    'framework': framework
                                })
                    except:
                        pass
                        
    def identify_critical_paths(self):
        """Identify critical paths for bug fixes"""
        critical_patterns = [
            ('Authentication', ['auth', 'login', 'session', 'token', 'jwt']),
            ('Database', ['query', 'database', 'sql', 'orm', 'model']),
            ('API Calls', ['fetch', 'axios', 'request', 'http', 'api']),
            ('State Management', ['state', 'redux', 'vuex', 'store']),
            ('Error Handling', ['error', 'exception', 'catch', 'try']),
            ('Validation', ['validate', 'validator', 'schema', 'rules']),
        ]
        
        for category, keywords in critical_patterns:
            files = []
            for root, _, filenames in os.walk(self.root_path):
                for filename in filenames:
                    if any(kw in filename.lower() for kw in keywords):
                        files.append(os.path.relpath(os.path.join(root, filename), self.root_path))
                        
            if files:
                self.critical_paths.append({
                    'category': category,
                    'files': files[:10]  # Top 10 files
                })
                
    def analyze_architecture(self):
        """Analyze overall architecture patterns"""
        # Check for common architectural patterns
        dirs = set()
        for root, dirnames, _ in os.walk(self.root_path):
            for dirname in dirnames:
                dirs.add(dirname.lower())
                
        # Identify architecture style
        if 'controllers' in dirs and 'models' in dirs and 'views' in dirs:
            self.tech_stack['architecture'] = 'MVC'
        elif 'components' in dirs and ('pages' in dirs or 'screens' in dirs):
            self.tech_stack['architecture'] = 'Component-Based'
        elif 'domain' in dirs and 'infrastructure' in dirs:
            self.tech_stack['architecture'] = 'Domain-Driven Design'
        elif 'src' in dirs and 'tests' in dirs:
            self.tech_stack['architecture'] = 'Standard'
            
    def generate_report(self) -> Dict:
        """Generate comprehensive analysis report"""
        return {
            'tech_stack': self.tech_stack,
            'api_endpoints': self.api_endpoints[:20],  # Top 20 endpoints
            'dependencies': {
                'total_files': len(self.dependencies),
                'most_imported': self._get_most_imported(),
            },
            'critical_paths': self.critical_paths,
            'quick_start': self._generate_quick_start(),
        }
        
    def _get_most_imported(self) -> List[Tuple[str, int]]:
        """Get most frequently imported modules"""
        import_counts = defaultdict(int)
        for imports in self.dependencies.values():
            for imp in imports:
                import_counts[imp] += 1
                
        return sorted(import_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
    def _generate_quick_start(self) -> Dict[str, str]:
        """Generate quick start guide based on analysis"""
        guide = {}
        
        if 'language' in self.tech_stack:
            lang = self.tech_stack['language']
            if 'JavaScript' in lang:
                guide['install'] = 'npm install'
                guide['run'] = 'npm start'
                guide['test'] = 'npm test'
            elif lang == 'Python':
                guide['install'] = 'pip install -r requirements.txt'
                guide['run'] = 'python main.py or python app.py'
                guide['test'] = 'pytest'
                
        return guide


def main():
    parser = argparse.ArgumentParser(description='Analyze codebase context for SWE tasks')
    parser.add_argument('path', nargs='?', default='.', help='Path to analyze (default: current directory)')
    parser.add_argument('--output', '-o', help='Output file for JSON report')
    parser.add_argument('--format', '-f', choices=['json', 'summary'], default='summary', help='Output format')
    
    args = parser.parse_args()
    
    analyzer = ContextAnalyzer(args.path)
    report = analyzer.analyze()
    
    if args.format == 'json' or args.output:
        json_output = json.dumps(report, indent=2)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(json_output)
            print(f"Report saved to {args.output}")
        else:
            print(json_output)
    else:
        # Print summary
        print("\n🔍 CODEBASE CONTEXT ANALYSIS")
        print("=" * 50)
        
        if 'language' in report['tech_stack']:
            print(f"\n📚 Technology Stack:")
            print(f"  Language: {report['tech_stack']['language']}")
            if 'backend' in report['tech_stack']:
                print(f"  Backend: {report['tech_stack']['backend']}")
            if 'frontend' in report['tech_stack']:
                print(f"  Frontend: {report['tech_stack']['frontend']}")
            if 'mobile' in report['tech_stack']:
                print(f"  Mobile: {', '.join(report['tech_stack']['mobile'])}")
            if 'architecture' in report['tech_stack']:
                print(f"  Architecture: {report['tech_stack']['architecture']}")
                
        if report['api_endpoints']:
            print(f"\n🌐 API Endpoints ({len(report['api_endpoints'])} found):")
            for ep in report['api_endpoints'][:5]:
                print(f"  {ep['method']} {ep['path']} ({ep['file']})")
            if len(report['api_endpoints']) > 5:
                print(f"  ... and {len(report['api_endpoints']) - 5} more")
                
        if report['dependencies']['most_imported']:
            print(f"\n📦 Most Imported Modules:")
            for module, count in report['dependencies']['most_imported'][:5]:
                print(f"  {module}: {count} imports")
                
        if report['critical_paths']:
            print(f"\n🎯 Critical Paths for Bug Fixes:")
            for path in report['critical_paths']:
                print(f"  {path['category']}:")
                for file in path['files'][:3]:
                    print(f"    - {file}")
                    
        if report['quick_start']:
            print(f"\n🚀 Quick Start:")
            for cmd, desc in report['quick_start'].items():
                print(f"  {cmd}: {desc}")


if __name__ == '__main__':
    main()