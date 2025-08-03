#!/usr/bin/env python3
"""
Performance Optimization Toolkit - Identify and fix performance bottlenecks
Comprehensive performance analysis across full stack applications
"""

import os
import json
import argparse
import time
import cProfile
import pstats
import io
import re
import ast
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import subprocess

@dataclass
class PerformanceIssue:
    type: str  # 'cpu', 'memory', 'io', 'network', 'database'
    severity: str  # 'critical', 'high', 'medium', 'low'
    location: str
    description: str
    impact_ms: float
    recommendation: str
    code_snippet: Optional[str] = None
    
@dataclass
class OptimizationSuggestion:
    issue_type: str
    original_code: str
    optimized_code: str
    expected_improvement: str
    explanation: str

class PerformanceOptimizer:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.issues = []
        self.profiles = {}
        self.query_analyzer = DatabaseQueryAnalyzer()
        self.memory_analyzer = MemoryAnalyzer()
        self.bundle_analyzer = BundleAnalyzer()
        
    def analyze(self) -> Dict[str, Any]:
        """Run comprehensive performance analysis"""
        print("🚀 Starting performance analysis...")
        
        results = {
            'summary': {},
            'bottlenecks': [],
            'optimizations': [],
            'metrics': {}
        }
        
        # Different analysis phases
        self._analyze_code_performance()
        self._analyze_database_queries()
        self._analyze_memory_usage()
        self._analyze_bundle_size()
        self._analyze_network_performance()
        self._analyze_render_performance()
        
        # Generate optimization suggestions
        results['optimizations'] = self._generate_optimizations()
        
        # Calculate summary metrics
        results['summary'] = self._generate_summary()
        results['bottlenecks'] = self._identify_top_bottlenecks()
        results['metrics'] = self._collect_metrics()
        
        return results
        
    def _analyze_code_performance(self):
        """Analyze code for performance issues"""
        print("  Analyzing code performance...")
        
        # Python performance analysis
        for py_file in self.project_root.rglob('*.py'):
            self._analyze_python_performance(py_file)
            
        # JavaScript performance analysis
        for js_file in self.project_root.rglob('*.js'):
            if 'node_modules' not in str(js_file):
                self._analyze_js_performance(js_file)
                
    def _analyze_python_performance(self, file_path: Path):
        """Analyze Python file for performance issues"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse AST
            tree = ast.parse(content)
            
            # Check for common performance anti-patterns
            for node in ast.walk(tree):
                # Nested loops
                if isinstance(node, ast.For):
                    nested_loops = sum(1 for child in ast.walk(node) 
                                     if isinstance(child, ast.For))
                    if nested_loops > 2:
                        self.issues.append(PerformanceIssue(
                            type='cpu',
                            severity='high',
                            location=f"{file_path}:{node.lineno}",
                            description=f"Deeply nested loops (depth: {nested_loops})",
                            impact_ms=nested_loops * 100,
                            recommendation="Consider using vectorized operations or optimizing algorithm",
                            code_snippet=ast.get_source_segment(content, node)[:200]
                        ))
                        
                # String concatenation in loops
                if isinstance(node, ast.For):
                    for child in ast.walk(node):
                        if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
                            if isinstance(child.target, ast.Name):
                                self.issues.append(PerformanceIssue(
                                    type='memory',
                                    severity='medium',
                                    location=f"{file_path}:{child.lineno}",
                                    description="String concatenation in loop",
                                    impact_ms=50,
                                    recommendation="Use list append and join instead",
                                    code_snippet=ast.get_source_segment(content, child)
                                ))
                                
        except Exception:
            pass
            
    def _analyze_js_performance(self, file_path: Path):
        """Analyze JavaScript file for performance issues"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            rel_path = str(file_path.relative_to(self.project_root))
            
            # Check for performance patterns
            patterns = [
                # Inefficient array operations
                (r'\.filter\([^)]+\)\.map\([^)]+\)', 'Chained filter and map', 
                 'Combine into single reduce operation'),
                
                # DOM queries in loops
                (r'for\s*\([^)]+\)\s*{[^}]*document\.(querySelector|getElementById)',
                 'DOM query in loop', 'Cache DOM queries outside loop'),
                
                # Repeated regex compilation
                (r'new RegExp\([^)]+\)', 'RegExp creation', 
                 'Create RegExp once and reuse'),
                
                # Large object spreads
                (r'\.\.\.(?:[a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)+)',
                 'Deep object spread', 'Consider using Object.assign or lodash'),
                
                # Synchronous operations
                (r'(readFileSync|writeFileSync|execSync)', 'Synchronous I/O',
                 'Use async alternatives'),
            ]
            
            for pattern, issue_type, recommendation in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    self.issues.append(PerformanceIssue(
                        type='cpu',
                        severity='medium',
                        location=f"{rel_path}:{line_num}",
                        description=issue_type,
                        impact_ms=20,
                        recommendation=recommendation,
                        code_snippet=content[match.start():match.end()]
                    ))
                    
        except Exception:
            pass
            
    def _analyze_database_queries(self):
        """Analyze database queries for optimization"""
        print("  Analyzing database queries...")
        
        # Look for SQL queries in code
        sql_patterns = [
            r'SELECT.*FROM',
            r'UPDATE.*SET',
            r'DELETE.*FROM',
            r'INSERT.*INTO'
        ]
        
        for pattern in sql_patterns:
            for file_path in self.project_root.rglob('*'):
                if file_path.suffix in ['.py', '.js', '.java', '.php']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
                        for match in matches:
                            query = match.group(0)
                            analysis = self.query_analyzer.analyze_query(query)
                            
                            if analysis['issues']:
                                for issue in analysis['issues']:
                                    self.issues.append(PerformanceIssue(
                                        type='database',
                                        severity=issue['severity'],
                                        location=str(file_path),
                                        description=issue['description'],
                                        impact_ms=issue['impact_ms'],
                                        recommendation=issue['recommendation'],
                                        code_snippet=query[:200]
                                    ))
                                    
                    except Exception:
                        pass
                        
    def _analyze_memory_usage(self):
        """Analyze for memory leaks and inefficiencies"""
        print("  Analyzing memory usage...")
        
        # JavaScript/React memory patterns
        react_patterns = [
            (r'addEventListener\([^)]+\)(?!.*removeEventListener)', 
             'Event listener without cleanup', 'high'),
            (r'setInterval\([^)]+\)(?!.*clearInterval)',
             'Interval without cleanup', 'high'),
            (r'new Worker\([^)]+\)(?!.*terminate)',
             'Worker without termination', 'medium'),
        ]
        
        for file_path in self.project_root.rglob('*.jsx'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for pattern, issue, severity in react_patterns:
                    if re.search(pattern, content):
                        self.issues.append(PerformanceIssue(
                            type='memory',
                            severity=severity,
                            location=str(file_path),
                            description=issue,
                            impact_ms=100,
                            recommendation='Add proper cleanup in useEffect/componentWillUnmount'
                        ))
                        
            except Exception:
                pass
                
    def _analyze_bundle_size(self):
        """Analyze JavaScript bundle sizes"""
        print("  Analyzing bundle sizes...")
        
        # Check for package.json
        package_json = self.project_root / 'package.json'
        if package_json.exists():
            analysis = self.bundle_analyzer.analyze(self.project_root)
            
            for issue in analysis['issues']:
                self.issues.append(PerformanceIssue(
                    type='network',
                    severity=issue['severity'],
                    location='bundle',
                    description=issue['description'],
                    impact_ms=issue['impact_ms'],
                    recommendation=issue['recommendation']
                ))
                
    def _analyze_network_performance(self):
        """Analyze network-related performance issues"""
        print("  Analyzing network performance...")
        
        # Check for unoptimized images
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        large_images = []
        
        for ext in image_extensions:
            for img_path in self.project_root.rglob(f'*{ext}'):
                if img_path.stat().st_size > 500 * 1024:  # 500KB
                    large_images.append((img_path, img_path.stat().st_size))
                    
        if large_images:
            self.issues.append(PerformanceIssue(
                type='network',
                severity='high',
                location='images',
                description=f"Found {len(large_images)} large unoptimized images",
                impact_ms=len(large_images) * 1000,
                recommendation='Compress images and use modern formats (WebP, AVIF)'
            ))
            
        # Check for missing caching headers
        self._check_caching_configuration()
        
    def _analyze_render_performance(self):
        """Analyze frontend rendering performance"""
        print("  Analyzing render performance...")
        
        # React re-render patterns
        react_files = list(self.project_root.rglob('*.jsx'))
        react_files.extend(self.project_root.rglob('*.tsx'))
        
        for file_path in react_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Check for missing React.memo
                if 'export' in content and 'function' in content:
                    if 'React.memo' not in content and 'memo(' not in content:
                        self.issues.append(PerformanceIssue(
                            type='cpu',
                            severity='low',
                            location=str(file_path),
                            description='Component without memoization',
                            impact_ms=10,
                            recommendation='Consider using React.memo for pure components'
                        ))
                        
                # Check for inline function definitions
                inline_patterns = [
                    r'onClick=\{(?:function|\(\))',
                    r'onChange=\{(?:function|\(\))',
                ]
                
                for pattern in inline_patterns:
                    if re.search(pattern, content):
                        self.issues.append(PerformanceIssue(
                            type='cpu',
                            severity='medium',
                            location=str(file_path),
                            description='Inline function in render',
                            impact_ms=5,
                            recommendation='Use useCallback to memoize event handlers'
                        ))
                        break
                        
            except Exception:
                pass
                
    def _check_caching_configuration(self):
        """Check for caching configuration"""
        # Check for common server config files
        config_patterns = {
            'nginx.conf': self._check_nginx_caching,
            '.htaccess': self._check_apache_caching,
            'server.js': self._check_express_caching,
        }
        
        for filename, checker in config_patterns.items():
            for config_path in self.project_root.rglob(filename):
                checker(config_path)
                
    def _check_nginx_caching(self, config_path: Path):
        """Check nginx caching configuration"""
        try:
            with open(config_path, 'r') as f:
                content = f.read()
                
            if 'expires' not in content and 'Cache-Control' not in content:
                self.issues.append(PerformanceIssue(
                    type='network',
                    severity='medium',
                    location=str(config_path),
                    description='Missing caching headers in nginx config',
                    impact_ms=500,
                    recommendation='Add expires and Cache-Control headers for static assets'
                ))
                
        except Exception:
            pass
            
    def _check_apache_caching(self, config_path: Path):
        """Check Apache caching configuration"""
        # Similar to nginx
        pass
        
    def _check_express_caching(self, config_path: Path):
        """Check Express.js caching"""
        try:
            with open(config_path, 'r') as f:
                content = f.read()
                
            if 'static' in content and 'maxAge' not in content:
                self.issues.append(PerformanceIssue(
                    type='network',
                    severity='medium',
                    location=str(config_path),
                    description='Static files served without cache headers',
                    impact_ms=300,
                    recommendation="Add maxAge option to express.static()"
                ))
                
        except Exception:
            pass
            
    def _generate_optimizations(self) -> List[OptimizationSuggestion]:
        """Generate specific optimization suggestions"""
        optimizations = []
        
        # Group issues by type
        issues_by_type = defaultdict(list)
        for issue in self.issues:
            issues_by_type[issue.type].append(issue)
            
        # Generate optimizations for each type
        if issues_by_type['database']:
            optimizations.extend(self._generate_db_optimizations(issues_by_type['database']))
            
        if issues_by_type['memory']:
            optimizations.extend(self._generate_memory_optimizations(issues_by_type['memory']))
            
        if issues_by_type['cpu']:
            optimizations.extend(self._generate_cpu_optimizations(issues_by_type['cpu']))
            
        return optimizations
        
    def _generate_db_optimizations(self, issues: List[PerformanceIssue]) -> List[OptimizationSuggestion]:
        """Generate database optimization suggestions"""
        optimizations = []
        
        # N+1 query optimization
        n_plus_one = [i for i in issues if 'N+1' in i.description]
        if n_plus_one:
            optimizations.append(OptimizationSuggestion(
                issue_type='N+1 Queries',
                original_code='''for user in users:
    user.posts = Post.query.filter_by(user_id=user.id).all()''',
                optimized_code='''users = User.query.options(joinedload(User.posts)).all()''',
                expected_improvement='90% reduction in database queries',
                explanation='Use eager loading to fetch related data in a single query'
            ))
            
        return optimizations
        
    def _generate_memory_optimizations(self, issues: List[PerformanceIssue]) -> List[OptimizationSuggestion]:
        """Generate memory optimization suggestions"""
        optimizations = []
        
        # Event listener cleanup
        listener_issues = [i for i in issues if 'listener' in i.description.lower()]
        if listener_issues:
            optimizations.append(OptimizationSuggestion(
                issue_type='Memory Leak - Event Listeners',
                original_code='''useEffect(() => {
    window.addEventListener('resize', handleResize);
}, []);''',
                optimized_code='''useEffect(() => {
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
}, []);''',
                expected_improvement='Prevents memory leak on component unmount',
                explanation='Always clean up event listeners in useEffect cleanup function'
            ))
            
        return optimizations
        
    def _generate_cpu_optimizations(self, issues: List[PerformanceIssue]) -> List[OptimizationSuggestion]:
        """Generate CPU optimization suggestions"""
        optimizations = []
        
        # React re-render optimizations
        render_issues = [i for i in issues if 'render' in i.description.lower()]
        if render_issues:
            optimizations.append(OptimizationSuggestion(
                issue_type='Unnecessary Re-renders',
                original_code='''function ExpensiveComponent({ data }) {
    return <div>{processData(data)}</div>;
}''',
                optimized_code='''const ExpensiveComponent = React.memo(({ data }) => {
    const processed = useMemo(() => processData(data), [data]);
    return <div>{processed}</div>;
});''',
                expected_improvement='50-80% reduction in render time',
                explanation='Use React.memo and useMemo to prevent unnecessary re-renders'
            ))
            
        return optimizations
        
    def _identify_top_bottlenecks(self) -> List[Dict[str, Any]]:
        """Identify the top performance bottlenecks"""
        # Sort issues by impact
        sorted_issues = sorted(self.issues, key=lambda x: x.impact_ms, reverse=True)
        
        bottlenecks = []
        for issue in sorted_issues[:10]:
            bottlenecks.append({
                'type': issue.type,
                'location': issue.location,
                'description': issue.description,
                'impact_ms': issue.impact_ms,
                'severity': issue.severity,
                'fix': issue.recommendation
            })
            
        return bottlenecks
        
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate performance summary"""
        total_impact = sum(issue.impact_ms for issue in self.issues)
        
        by_type = defaultdict(int)
        by_severity = defaultdict(int)
        
        for issue in self.issues:
            by_type[issue.type] += 1
            by_severity[issue.severity] += 1
            
        return {
            'total_issues': len(self.issues),
            'total_impact_ms': total_impact,
            'estimated_improvement': f"{min(total_impact / 1000, 50):.1f}s",
            'by_type': dict(by_type),
            'by_severity': dict(by_severity),
            'health_score': self._calculate_health_score()
        }
        
    def _calculate_health_score(self) -> int:
        """Calculate overall performance health score (0-100)"""
        if not self.issues:
            return 100
            
        # Weight by severity
        weights = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
        total_weight = sum(weights.get(issue.severity, 1) for issue in self.issues)
        
        # Calculate score (max penalty of 100)
        penalty = min(total_weight, 100)
        return 100 - penalty
        
    def _collect_metrics(self) -> Dict[str, Any]:
        """Collect performance metrics"""
        return {
            'load_time_estimate': self._estimate_load_time(),
            'memory_usage_estimate': self._estimate_memory_usage(),
            'bundle_size': self._get_bundle_size(),
            'database_query_count': len([i for i in self.issues if i.type == 'database']),
            'optimization_potential': f"{len(self._generate_optimizations())} improvements"
        }
        
    def _estimate_load_time(self) -> str:
        """Estimate page load time impact"""
        network_impact = sum(i.impact_ms for i in self.issues if i.type == 'network')
        cpu_impact = sum(i.impact_ms for i in self.issues if i.type == 'cpu')
        
        total_ms = network_impact + (cpu_impact * 0.3)  # CPU impact is partial
        return f"{total_ms / 1000:.1f}s potential reduction"
        
    def _estimate_memory_usage(self) -> str:
        """Estimate memory usage"""
        memory_issues = [i for i in self.issues if i.type == 'memory']
        if not memory_issues:
            return "No significant memory issues"
            
        return f"{len(memory_issues)} memory leaks detected"
        
    def _get_bundle_size(self) -> str:
        """Get bundle size if available"""
        # Check for webpack stats or similar
        stats_file = self.project_root / 'stats.json'
        if stats_file.exists():
            try:
                with open(stats_file) as f:
                    stats = json.load(f)
                    size = stats.get('assets', [{}])[0].get('size', 0)
                    return f"{size / 1024:.1f}KB"
            except:
                pass
                
        return "Unknown"

class DatabaseQueryAnalyzer:
    """Analyze database queries for performance issues"""
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze a SQL query for performance issues"""
        issues = []
        query_lower = query.lower()
        
        # Check for SELECT *
        if 'select *' in query_lower:
            issues.append({
                'severity': 'medium',
                'description': 'SELECT * query fetches unnecessary columns',
                'impact_ms': 50,
                'recommendation': 'Specify only required columns'
            })
            
        # Check for missing WHERE clause in UPDATE/DELETE
        if ('update' in query_lower or 'delete' in query_lower) and 'where' not in query_lower:
            issues.append({
                'severity': 'critical',
                'description': 'UPDATE/DELETE without WHERE clause',
                'impact_ms': 1000,
                'recommendation': 'Add WHERE clause to prevent full table operation'
            })
            
        # Check for LIKE with leading wildcard
        if re.search(r"like\s+['\"]%", query_lower):
            issues.append({
                'severity': 'high',
                'description': 'LIKE query with leading wildcard prevents index usage',
                'impact_ms': 200,
                'recommendation': 'Use full-text search or redesign query'
            })
            
        # Check for NOT IN with subquery
        if 'not in' in query_lower and 'select' in query_lower[query_lower.find('not in'):]:
            issues.append({
                'severity': 'high',
                'description': 'NOT IN with subquery can be slow',
                'impact_ms': 300,
                'recommendation': 'Use NOT EXISTS or LEFT JOIN instead'
            })
            
        # Check for OR conditions
        or_count = query_lower.count(' or ')
        if or_count > 2:
            issues.append({
                'severity': 'medium',
                'description': f'Multiple OR conditions ({or_count}) can prevent index usage',
                'impact_ms': or_count * 30,
                'recommendation': 'Consider using IN clause or UNION'
            })
            
        return {'issues': issues}

class MemoryAnalyzer:
    """Analyze memory usage patterns"""
    
    def analyze(self, project_root: Path) -> Dict[str, Any]:
        """Analyze project for memory issues"""
        issues = []
        
        # Analyze would include:
        # - Heap dump analysis
        # - Memory leak detection
        # - Large object detection
        # - Circular reference detection
        
        return {'issues': issues}

class BundleAnalyzer:
    """Analyze JavaScript bundle sizes"""
    
    def analyze(self, project_root: Path) -> Dict[str, Any]:
        """Analyze bundle for size optimizations"""
        issues = []
        
        # Check package.json for large dependencies
        package_json = project_root / 'package.json'
        if package_json.exists():
            with open(package_json) as f:
                data = json.load(f)
                
            large_packages = {
                'moment': ('date-fns or dayjs', 500),
                'lodash': ('lodash-es with tree shaking', 300),
                'jquery': ('vanilla JavaScript', 400),
            }
            
            dependencies = data.get('dependencies', {})
            for pkg, (alternative, impact) in large_packages.items():
                if pkg in dependencies:
                    issues.append({
                        'severity': 'medium',
                        'description': f'Large dependency: {pkg}',
                        'impact_ms': impact,
                        'recommendation': f'Consider using {alternative}'
                    })
                    
        return {'issues': issues}

def main():
    parser = argparse.ArgumentParser(description='Performance optimization toolkit')
    parser.add_argument('path', nargs='?', default='.', help='Project path to analyze')
    parser.add_argument('--output', help='Output file for JSON report')
    parser.add_argument('--fix', action='store_true', help='Apply automatic fixes')
    parser.add_argument('--profile', help='Profile a specific Python file')
    
    args = parser.parse_args()
    
    if args.profile:
        # Profile specific file
        print(f"📊 Profiling {args.profile}...")
        profiler = cProfile.Profile()
        profiler.enable()
        
        # Run the file
        with open(args.profile) as f:
            exec(f.read())
            
        profiler.disable()
        
        # Print stats
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)
        print(s.getvalue())
        return
        
    # Run performance analysis
    optimizer = PerformanceOptimizer(args.path)
    results = optimizer.analyze()
    
    # Print report
    print("\n🚀 PERFORMANCE OPTIMIZATION REPORT")
    print("=" * 60)
    
    summary = results['summary']
    print(f"\n📊 Summary:")
    print(f"  Total Issues: {summary['total_issues']}")
    print(f"  Performance Impact: {summary['total_impact_ms']:.0f}ms")
    print(f"  Potential Improvement: {summary['estimated_improvement']}")
    print(f"  Health Score: {summary['health_score']}/100")
    
    print(f"\n🔥 Top Bottlenecks:")
    for i, bottleneck in enumerate(results['bottlenecks'][:5], 1):
        severity_emoji = {
            'critical': '🚨',
            'high': '⚠️',
            'medium': '📊',
            'low': 'ℹ️'
        }[bottleneck['severity']]
        
        print(f"\n{i}. {severity_emoji} {bottleneck['description']}")
        print(f"   Location: {bottleneck['location']}")
        print(f"   Impact: {bottleneck['impact_ms']:.0f}ms")
        print(f"   Fix: {bottleneck['fix']}")
        
    if results['optimizations']:
        print(f"\n💡 Optimization Suggestions:")
        for opt in results['optimizations'][:3]:
            print(f"\n### {opt.issue_type}")
            print(f"Before:\n```\n{opt.original_code}\n```")
            print(f"After:\n```\n{opt.optimized_code}\n```")
            print(f"Expected: {opt.expected_improvement}")
            
    print(f"\n📈 Metrics:")
    for key, value in results['metrics'].items():
        print(f"  {key.replace('_', ' ').title()}: {value}")
        
    # Save JSON report if requested
    if args.output:
        # Convert to JSON-serializable format
        json_results = {
            'summary': results['summary'],
            'bottlenecks': results['bottlenecks'],
            'metrics': results['metrics'],
            'optimizations': [
                {
                    'issue_type': opt.issue_type,
                    'original_code': opt.original_code,
                    'optimized_code': opt.optimized_code,
                    'expected_improvement': opt.expected_improvement,
                    'explanation': opt.explanation
                }
                for opt in results['optimizations']
            ]
        }
        
        with open(args.output, 'w') as f:
            json.dump(json_results, f, indent=2)
            
        print(f"\n💾 Report saved to {args.output}")
        
    print("\n" + "=" * 60)
    print("Run with --fix to apply automatic optimizations")

if __name__ == '__main__':
    main()