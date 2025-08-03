#!/usr/bin/env python3
"""
Full-Stack Change Impact Analyzer - Trace changes across entire stack
Analyzes impact from database to API to frontend across all platforms
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

@dataclass
class Change:
    file: str
    line: int
    type: str  # 'added', 'modified', 'deleted'
    content: str
    
@dataclass
class Impact:
    source: str
    target: str
    impact_type: str  # 'direct', 'indirect', 'potential'
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    
class ImpactAnalyzer:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.schema_files = []
        self.api_definitions = {}
        self.component_dependencies = defaultdict(set)
        self.api_consumers = defaultdict(set)
        self.database_queries = {}
        
    def analyze_changes(self, changes: List[Change]) -> Dict[str, List[Impact]]:
        """Analyze the impact of a set of changes"""
        print("🔍 Analyzing change impacts across the stack...")
        
        # First, map the current state
        self._map_database_schema()
        self._map_api_endpoints()
        self._map_frontend_components()
        self._map_mobile_components()
        
        # Analyze impacts
        impacts = defaultdict(list)
        
        for change in changes:
            file_impacts = self._analyze_single_change(change)
            impacts[change.file].extend(file_impacts)
            
        # Find cascading impacts
        self._analyze_cascading_impacts(impacts)
        
        return dict(impacts)
        
    def _map_database_schema(self):
        """Map database schema files and migrations"""
        schema_patterns = [
            '**/schema.sql',
            '**/migrations/*.sql',
            '**/models.py',
            '**/models/*.py',
            '**/schema.prisma',
            '**/schema.graphql',
        ]
        
        for pattern in schema_patterns:
            self.schema_files.extend(self.project_root.glob(pattern))
            
    def _map_api_endpoints(self):
        """Map API endpoints and their definitions"""
        # Search for API route definitions
        for file_path in self.project_root.rglob('*.py'):
            self._extract_python_apis(file_path)
            
        for file_path in self.project_root.rglob('*.js'):
            self._extract_js_apis(file_path)
            
        for file_path in self.project_root.rglob('*.ts'):
            self._extract_js_apis(file_path)
            
    def _extract_python_apis(self, file_path: Path):
        """Extract API definitions from Python files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Flask/FastAPI patterns
            api_patterns = [
                r'@app\.route\([\'"]([^\'"]+)[\'"].*?\)',
                r'@router\.(get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"].*?\)',
                r'@app\.(get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"].*?\)',
            ]
            
            for pattern in api_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, tuple):
                        endpoint = match[1] if len(match) > 1 else match[0]
                    else:
                        endpoint = match
                        
                    self.api_definitions[endpoint] = {
                        'file': str(file_path.relative_to(self.project_root)),
                        'type': 'rest'
                    }
                    
        except Exception:
            pass
            
    def _extract_js_apis(self, file_path: Path):
        """Extract API definitions from JavaScript/TypeScript files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Express patterns
            patterns = [
                r'app\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                r'router\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for method, endpoint in matches:
                    self.api_definitions[endpoint] = {
                        'file': str(file_path.relative_to(self.project_root)),
                        'method': method.upper(),
                        'type': 'rest'
                    }
                    
            # GraphQL patterns
            if 'type Query' in content or 'type Mutation' in content:
                self.api_definitions['graphql'] = {
                    'file': str(file_path.relative_to(self.project_root)),
                    'type': 'graphql'
                }
                
        except Exception:
            pass
            
    def _map_frontend_components(self):
        """Map frontend components and their API usage"""
        component_patterns = ['*.jsx', '*.tsx', '*.vue', '*.svelte']
        
        for pattern in component_patterns:
            for file_path in self.project_root.rglob(pattern):
                self._analyze_component_dependencies(file_path)
                
    def _analyze_component_dependencies(self, file_path: Path):
        """Analyze a frontend component for API calls and dependencies"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            rel_path = str(file_path.relative_to(self.project_root))
            
            # Find API calls
            api_patterns = [
                r'fetch\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
                r'axios\.(get|post|put|delete|patch)\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
                r'api\.(get|post|put|delete|patch)\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
            ]
            
            for pattern in api_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, tuple):
                        endpoint = match[1]
                    else:
                        endpoint = match
                        
                    self.api_consumers[endpoint].add(rel_path)
                    
            # Find component imports
            import_patterns = [
                r'import\s+.*?\s+from\s+[\'"]([^\'\"]+)[\'"]',
                r'require\s*\(\s*[\'"]([^\'\"]+)[\'\"]\s*\)',
            ]
            
            for pattern in import_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if match.startswith('.'):
                        # Relative import
                        imported_path = (file_path.parent / match).resolve()
                        try:
                            imported_rel = str(imported_path.relative_to(self.project_root))
                            self.component_dependencies[rel_path].add(imported_rel)
                        except:
                            pass
                            
        except Exception:
            pass
            
    def _map_mobile_components(self):
        """Map mobile app components"""
        # React Native
        for file_path in self.project_root.rglob('*.js'):
            if 'node_modules' not in str(file_path):
                self._check_mobile_component(file_path, 'react-native')
                
        # Flutter
        for file_path in self.project_root.rglob('*.dart'):
            self._check_mobile_component(file_path, 'flutter')
            
        # iOS
        for file_path in self.project_root.rglob('*.swift'):
            self._check_mobile_component(file_path, 'ios')
            
        # Android
        for file_path in self.project_root.rglob('*.kt'):
            self._check_mobile_component(file_path, 'android')
            
    def _check_mobile_component(self, file_path: Path, platform: str):
        """Check mobile component for API usage"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            rel_path = str(file_path.relative_to(self.project_root))
            
            # Platform-specific API patterns
            if platform == 'react-native':
                if 'fetch(' in content or 'axios' in content:
                    self.component_dependencies[rel_path].add('mobile-api')
            elif platform == 'flutter':
                if 'http.' in content or 'dio.' in content:
                    self.component_dependencies[rel_path].add('mobile-api')
            elif platform == 'ios':
                if 'URLSession' in content or 'Alamofire' in content:
                    self.component_dependencies[rel_path].add('mobile-api')
            elif platform == 'android':
                if 'OkHttpClient' in content or 'Retrofit' in content:
                    self.component_dependencies[rel_path].add('mobile-api')
                    
        except Exception:
            pass
            
    def _analyze_single_change(self, change: Change) -> List[Impact]:
        """Analyze impact of a single change"""
        impacts = []
        
        # Determine the layer of the change
        file_ext = Path(change.file).suffix
        file_path_lower = change.file.lower()
        
        if any(schema in file_path_lower for schema in ['schema', 'model', 'migration', 'database']):
            impacts.extend(self._analyze_database_change(change))
        elif any(api in file_path_lower for api in ['api', 'route', 'controller', 'endpoint']):
            impacts.extend(self._analyze_api_change(change))
        elif file_ext in ['.jsx', '.tsx', '.vue', '.svelte']:
            impacts.extend(self._analyze_frontend_change(change))
        elif any(mobile in file_path_lower for mobile in ['ios', 'android', 'mobile']):
            impacts.extend(self._analyze_mobile_change(change))
            
        return impacts
        
    def _analyze_database_change(self, change: Change) -> List[Impact]:
        """Analyze database schema change impacts"""
        impacts = []
        
        # Database changes affect APIs that query the changed tables
        impacts.append(Impact(
            source=change.file,
            target="API Layer",
            impact_type="direct",
            severity="high",
            description=f"Database {change.type} may affect API queries and ORM models"
        ))
        
        # Check for specific table/column changes
        if 'CREATE TABLE' in change.content or 'ALTER TABLE' in change.content:
            table_match = re.search(r'TABLE\s+(\w+)', change.content)
            if table_match:
                table_name = table_match.group(1)
                impacts.append(Impact(
                    source=change.file,
                    target=f"Models using {table_name}",
                    impact_type="direct",
                    severity="critical",
                    description=f"Table {table_name} structure changed"
                ))
                
        return impacts
        
    def _analyze_api_change(self, change: Change) -> List[Impact]:
        """Analyze API change impacts"""
        impacts = []
        
        # Find which endpoints are affected
        endpoint_match = re.search(r'[\'"]([/\w\-{}]+)[\'"]', change.content)
        if endpoint_match:
            endpoint = endpoint_match.group(1)
            
            # Check frontend consumers
            if endpoint in self.api_consumers:
                for consumer in self.api_consumers[endpoint]:
                    impacts.append(Impact(
                        source=change.file,
                        target=consumer,
                        impact_type="direct",
                        severity="high",
                        description=f"API endpoint {endpoint} {change.type}"
                    ))
                    
            # Generic impact for all API changes
            impacts.append(Impact(
                source=change.file,
                target="Frontend/Mobile Apps",
                impact_type="potential",
                severity="medium",
                description=f"API contract may have changed"
            ))
            
        return impacts
        
    def _analyze_frontend_change(self, change: Change) -> List[Impact]:
        """Analyze frontend component change impacts"""
        impacts = []
        
        # Check component dependencies
        if change.file in self.component_dependencies:
            deps = self.component_dependencies[change.file]
            if deps:
                impacts.append(Impact(
                    source=change.file,
                    target="Dependent Components",
                    impact_type="potential",
                    severity="medium",
                    description=f"Component has {len(deps)} dependencies that may be affected"
                ))
                
        # Check for state management changes
        if any(pattern in change.content for pattern in ['setState', 'useState', 'redux', 'vuex']):
            impacts.append(Impact(
                source=change.file,
                target="Application State",
                impact_type="direct",
                severity="medium",
                description="State management logic changed"
            ))
            
        return impacts
        
    def _analyze_mobile_change(self, change: Change) -> List[Impact]:
        """Analyze mobile app change impacts"""
        impacts = []
        
        platform = "unknown"
        if change.file.endswith('.swift'):
            platform = "iOS"
        elif change.file.endswith('.kt') or change.file.endswith('.java'):
            platform = "Android"
        elif 'react-native' in change.file:
            platform = "React Native"
            
        impacts.append(Impact(
            source=change.file,
            target=f"{platform} App",
            impact_type="direct",
            severity="high",
            description=f"{platform} app code {change.type}"
        ))
        
        # Check for API changes in mobile code
        if any(api_pattern in change.content for api_pattern in ['fetch', 'http', 'api', 'request']):
            impacts.append(Impact(
                source=change.file,
                target="Backend API",
                impact_type="potential",
                severity="medium",
                description="Mobile app may be calling different APIs"
            ))
            
        return impacts
        
    def _analyze_cascading_impacts(self, impacts: Dict[str, List[Impact]]):
        """Analyze cascading impacts across the stack"""
        # Track files that have been impacted
        impacted_files = set()
        for file_impacts in impacts.values():
            for impact in file_impacts:
                if impact.impact_type == "direct":
                    impacted_files.add(impact.target)
                    
        # Check for second-order impacts
        for impacted in impacted_files:
            if impacted in self.component_dependencies:
                deps = self.component_dependencies[impacted]
                for dep in deps:
                    if dep not in impacts:
                        impacts[impacted].append(Impact(
                            source=impacted,
                            target=dep,
                            impact_type="indirect",
                            severity="low",
                            description="Cascading impact from dependency"
                        ))
                        
    def generate_impact_report(self, impacts: Dict[str, List[Impact]]) -> str:
        """Generate a human-readable impact report"""
        report = ["# Change Impact Analysis Report\n"]
        
        # Summary
        total_impacts = sum(len(file_impacts) for file_impacts in impacts.values())
        critical_impacts = sum(
            1 for file_impacts in impacts.values() 
            for impact in file_impacts 
            if impact.severity == "critical"
        )
        
        report.append(f"## Summary")
        report.append(f"- Total impacts identified: {total_impacts}")
        report.append(f"- Critical impacts: {critical_impacts}")
        report.append(f"- Files analyzed: {len(impacts)}\n")
        
        # Risk Assessment
        report.append("## Risk Assessment")
        if critical_impacts > 0:
            report.append("🚨 **HIGH RISK**: Critical impacts detected")
        elif total_impacts > 10:
            report.append("⚠️  **MEDIUM RISK**: Multiple impacts across the stack")
        else:
            report.append("✅ **LOW RISK**: Limited impact scope")
        report.append("")
        
        # Detailed Impacts
        report.append("## Detailed Impact Analysis\n")
        
        for file, file_impacts in impacts.items():
            if file_impacts:
                report.append(f"### {file}")
                
                # Group by severity
                by_severity = defaultdict(list)
                for impact in file_impacts:
                    by_severity[impact.severity].append(impact)
                    
                for severity in ['critical', 'high', 'medium', 'low']:
                    if severity in by_severity:
                        severity_emoji = {
                            'critical': '🚨',
                            'high': '⚠️ ',
                            'medium': '📊',
                            'low': 'ℹ️ '
                        }[severity]
                        
                        report.append(f"\n**{severity_emoji} {severity.upper()} Impact:**")
                        for impact in by_severity[severity]:
                            report.append(f"- {impact.target}: {impact.description}")
                            
                report.append("")
                
        # Recommendations
        report.append("## Recommendations\n")
        
        if critical_impacts > 0:
            report.append("1. **Immediate Actions Required:**")
            report.append("   - Review all critical impacts before deployment")
            report.append("   - Update affected API documentation")
            report.append("   - Notify mobile app teams of breaking changes")
            report.append("   - Run full regression test suite\n")
            
        report.append("2. **Testing Focus Areas:**")
        
        # Determine which areas need testing
        test_areas = set()
        for file_impacts in impacts.values():
            for impact in file_impacts:
                if 'database' in impact.target.lower():
                    test_areas.add("Database migrations and data integrity")
                elif 'api' in impact.target.lower():
                    test_areas.add("API endpoint functionality and contracts")
                elif 'frontend' in impact.target.lower() or 'component' in impact.target.lower():
                    test_areas.add("Frontend component rendering and interactions")
                elif 'mobile' in impact.target.lower():
                    test_areas.add("Mobile app functionality on all platforms")
                    
        for area in test_areas:
            report.append(f"   - {area}")
            
        return "\n".join(report)

def main():
    parser = argparse.ArgumentParser(description='Analyze change impacts across full stack')
    parser.add_argument('path', nargs='?', default='.', help='Project root path')
    parser.add_argument('--changes-file', help='JSON file with changes to analyze')
    parser.add_argument('--git-diff', action='store_true', help='Analyze current git changes')
    parser.add_argument('--output', help='Output file for report')
    
    args = parser.parse_args()
    
    analyzer = ImpactAnalyzer(args.path)
    
    # Get changes to analyze
    changes = []
    
    if args.git_diff:
        # Get changes from git
        import subprocess
        try:
            diff_output = subprocess.check_output(
                ['git', 'diff', '--name-status'], 
                cwd=args.path,
                text=True
            )
            
            for line in diff_output.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        status, file = parts[0], parts[1]
                        change_type = {
                            'A': 'added',
                            'M': 'modified',
                            'D': 'deleted'
                        }.get(status, 'modified')
                        
                        changes.append(Change(
                            file=file,
                            line=0,
                            type=change_type,
                            content=""
                        ))
        except:
            print("No git changes found or git not available")
            
    elif args.changes_file:
        with open(args.changes_file, 'r') as f:
            changes_data = json.load(f)
            changes = [Change(**c) for c in changes_data]
    else:
        # Demo changes
        changes = [
            Change(
                file="src/models/user.py",
                line=15,
                type="modified",
                content="ALTER TABLE users ADD COLUMN last_login TIMESTAMP"
            ),
            Change(
                file="src/api/auth.py",
                line=45,
                type="modified",
                content='@app.route("/api/login")'
            ),
            Change(
                file="src/components/LoginForm.jsx",
                line=23,
                type="modified",
                content='fetch("/api/login")'
            )
        ]
        
    # Analyze impacts
    impacts = analyzer.analyze_changes(changes)
    
    # Generate report
    report = analyzer.generate_impact_report(impacts)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to {args.output}")
    else:
        print(report)

if __name__ == '__main__':
    main()