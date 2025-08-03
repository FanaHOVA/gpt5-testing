#!/usr/bin/env python3
"""
SWE-Lancer Toolkit Integration Layer
Connects all tools to the task manager for coordinated execution
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import importlib.util

# Import all tool modules
tools_dir = Path(__file__).parent
sys.path.insert(0, str(tools_dir))

# Tool imports with error handling
tools_available = {}

def import_tool(name: str, module_file: str):
    """Safely import a tool module"""
    try:
        spec = importlib.util.spec_from_file_location(name, tools_dir / module_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tools_available[name] = module
        return True
    except Exception as e:
        print(f"Warning: Could not import {name}: {e}")
        return False

# Import all tools
import_tool('context_analyzer', 'context_analyzer.py')
import_tool('cross_platform_test_gen', 'cross_platform_test_gen.py')
import_tool('proposal_analyzer', 'proposal_analyzer.py')
import_tool('impact_analyzer', 'impact_analyzer.py')
import_tool('bug_pattern_engine', 'bug_pattern_engine.py')
import_tool('security_auditor', 'security_auditor.py')
import_tool('multi_platform_feature', 'multi_platform_feature.py')
import_tool('api_integration_assistant', 'api_integration_assistant.py')
import_tool('performance_optimizer', 'performance_optimizer.py')
import_tool('task_complexity_estimator', 'task_complexity_estimator.py')

@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time: float = 0.0

@dataclass
class WorkflowStep:
    tool: str
    params: Dict[str, Any]
    depends_on: List[str] = None
    condition: Optional[str] = None

class SWELancerToolkit:
    def __init__(self, project_root: str = '.'):
        self.project_root = Path(project_root).resolve()
        self.task_manager_path = self.project_root / 'tm'
        self.results_cache = {}
        
    def analyze_task(self, task_id: str) -> Dict[str, Any]:
        """Analyze a task from the task manager"""
        # Get task details
        task_details = self._get_task_details(task_id)
        if not task_details:
            return {'error': f'Task {task_id} not found'}
            
        # Determine task type and value
        task_type = self._classify_task(task_details)
        task_value = self._estimate_task_value(task_details)
        
        results = {
            'task_id': task_id,
            'task_details': task_details,
            'task_type': task_type,
            'estimated_value': task_value,
            'tool_results': {}
        }
        
        # Run appropriate tools based on task type
        workflow = self._create_workflow(task_type, task_value)
        
        for step in workflow:
            if self._should_run_step(step, results):
                result = self._run_tool(step.tool, step.params)
                results['tool_results'][step.tool] = result
                
        # Generate recommendations
        results['recommendations'] = self._generate_recommendations(results)
        
        return results
        
    def _get_task_details(self, task_id: str) -> Optional[Dict]:
        """Get task details from task manager"""
        try:
            result = subprocess.run(
                [str(self.task_manager_path), 'show', task_id],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Parse the output to extract task details
                output = result.stdout
                task = {
                    'id': task_id,
                    'title': '',
                    'description': '',
                    'status': '',
                    'files': []
                }
                
                lines = output.split('\n')
                for line in lines:
                    if 'Title:' in line:
                        task['title'] = line.split('Title:', 1)[1].strip()
                    elif 'Description:' in line:
                        task['description'] = line.split('Description:', 1)[1].strip()
                    elif 'Status:' in line:
                        task['status'] = line.split('Status:', 1)[1].strip()
                    elif 'Files:' in line:
                        # Extract file references
                        files_section = output.split('Files:', 1)[1]
                        task['files'] = [f.strip() for f in files_section.split('\n') if f.strip()]
                        
                return task
        except Exception as e:
            print(f"Error getting task details: {e}")
            
        return None
        
    def _classify_task(self, task_details: Dict) -> str:
        """Classify task type based on details"""
        title = task_details.get('title', '').lower()
        description = task_details.get('description', '').lower()
        combined = f"{title} {description}"
        
        # Classification rules
        if any(word in combined for word in ['bug', 'fix', 'error', 'issue']):
            return 'bug_fix'
        elif any(word in combined for word in ['feature', 'implement', 'add', 'create']):
            if 'video' in combined or 'playback' in combined:
                return 'multimedia_feature'
            elif any(platform in combined for platform in ['ios', 'android', 'mobile', 'desktop']):
                return 'multi_platform_feature'
            else:
                return 'feature'
        elif any(word in combined for word in ['security', 'permission', 'auth']):
            return 'security'
        elif any(word in combined for word in ['performance', 'optimize', 'speed']):
            return 'performance'
        elif any(word in combined for word in ['api', 'integration', 'endpoint']):
            return 'api_integration'
        else:
            return 'general'
            
    def _estimate_task_value(self, task_details: Dict) -> float:
        """Estimate task value based on complexity indicators"""
        # Use task complexity estimator if available
        if 'task_complexity_estimator' in tools_available:
            estimator = tools_available['task_complexity_estimator'].TaskComplexityEstimator()
            estimate = estimator.estimate_task(
                task_details.get('title', ''),
                task_details.get('description', ''),
                1000  # Default value
            )
            return estimate.value
            
        # Simple heuristic fallback
        description_length = len(task_details.get('description', ''))
        if description_length < 100:
            return 500
        elif description_length < 300:
            return 2000
        else:
            return 5000
            
    def _create_workflow(self, task_type: str, task_value: float) -> List[WorkflowStep]:
        """Create tool execution workflow based on task type"""
        workflows = {
            'bug_fix': [
                WorkflowStep('context_analyzer', {'path': self.project_root}),
                WorkflowStep('bug_pattern_engine', {'analyze': True}),
                WorkflowStep('impact_analyzer', {'git_diff': True}),
                WorkflowStep('performance_optimizer', {'path': self.project_root}),
            ],
            'multi_platform_feature': [
                WorkflowStep('context_analyzer', {'path': self.project_root}),
                WorkflowStep('multi_platform_feature', {'analyze': True}),
                WorkflowStep('cross_platform_test_gen', {'platform': 'all'}),
                WorkflowStep('impact_analyzer', {'git_diff': True}),
            ],
            'security': [
                WorkflowStep('security_auditor', {'path': self.project_root}),
                WorkflowStep('context_analyzer', {'path': self.project_root}),
                WorkflowStep('impact_analyzer', {'git_diff': True}),
            ],
            'performance': [
                WorkflowStep('performance_optimizer', {'path': self.project_root}),
                WorkflowStep('context_analyzer', {'path': self.project_root}),
                WorkflowStep('impact_analyzer', {'git_diff': True}),
            ],
            'api_integration': [
                WorkflowStep('api_integration_assistant', {'patterns': True}),
                WorkflowStep('context_analyzer', {'path': self.project_root}),
                WorkflowStep('security_auditor', {'path': self.project_root}),
            ],
            'feature': [
                WorkflowStep('context_analyzer', {'path': self.project_root}),
                WorkflowStep('task_complexity_estimator', {'value': task_value}),
                WorkflowStep('impact_analyzer', {'git_diff': True}),
            ],
            'general': [
                WorkflowStep('context_analyzer', {'path': self.project_root}),
                WorkflowStep('task_complexity_estimator', {'value': task_value}),
            ]
        }
        
        # Add proposal analyzer for high-value tasks
        if task_value > 5000:
            workflow = workflows.get(task_type, workflows['general'])
            workflow.insert(0, WorkflowStep('proposal_analyzer', {'task_value': task_value}))
            
        return workflows.get(task_type, workflows['general'])
        
    def _should_run_step(self, step: WorkflowStep, results: Dict) -> bool:
        """Check if a workflow step should run"""
        # Check dependencies
        if step.depends_on:
            for dep in step.depends_on:
                if dep not in results['tool_results']:
                    return False
                if not results['tool_results'][dep].success:
                    return False
                    
        # Check condition
        if step.condition:
            # Simple condition evaluation (in production, use safe eval)
            try:
                return eval(step.condition, {'results': results})
            except:
                return True
                
        return True
        
    def _run_tool(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """Run a specific tool with parameters"""
        start_time = datetime.now()
        
        if tool_name not in tools_available:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=f"Tool {tool_name} not available"
            )
            
        try:
            # Get the tool module
            tool_module = tools_available[tool_name]
            
            # Run tool based on its interface
            output = None
            if tool_name == 'context_analyzer':
                analyzer = tool_module.ContextAnalyzer(params.get('path', '.'))
                output = analyzer.analyze()
            elif tool_name == 'bug_pattern_engine':
                engine = tool_module.BugPatternEngine()
                # Create sample bug for analysis
                bug = tool_module.create_sample_bug()
                suggestions = engine.analyze_bug(bug)
                output = {'suggestions': [asdict(s) for s in suggestions]}
            elif tool_name == 'performance_optimizer':
                optimizer = tool_module.PerformanceOptimizer(params.get('path', '.'))
                output = optimizer.analyze()
            elif tool_name == 'security_auditor':
                auditor = tool_module.SecurityAuditor(params.get('path', '.'))
                output = auditor.audit()
            elif tool_name == 'task_complexity_estimator':
                estimator = tool_module.TaskComplexityEstimator()
                # Use task details from results
                output = {'estimate': 'See task analysis'}
            else:
                output = {'status': 'Tool integration pending'}
                
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ToolResult(
                tool_name=tool_name,
                success=True,
                output=output,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=str(e),
                execution_time=execution_time
            )
            
    def _generate_recommendations(self, results: Dict) -> List[str]:
        """Generate recommendations based on tool results"""
        recommendations = []
        
        # Check context analyzer results
        if 'context_analyzer' in results['tool_results']:
            context = results['tool_results']['context_analyzer'].output
            if context and 'tech_stack' in context:
                tech_stack = context['tech_stack']
                if 'language' in tech_stack:
                    recommendations.append(f"Project uses {tech_stack['language']} - ensure compatibility")
                    
        # Check security results
        if 'security_auditor' in results['tool_results']:
            security = results['tool_results']['security_auditor'].output
            if security and 'summary' in security:
                if security['summary']['critical'] > 0:
                    recommendations.append(f"🚨 Fix {security['summary']['critical']} critical security issues first")
                    
        # Check performance results
        if 'performance_optimizer' in results['tool_results']:
            perf = results['tool_results']['performance_optimizer'].output
            if perf and 'summary' in perf:
                if perf['summary']['health_score'] < 50:
                    recommendations.append("⚠️ Poor performance health - optimization needed")
                    
        # Task-specific recommendations
        task_type = results['task_type']
        if task_type == 'bug_fix':
            recommendations.append("📝 Write regression tests to prevent recurrence")
        elif task_type == 'multi_platform_feature':
            recommendations.append("📱 Test on all target platforms before deployment")
        elif task_type == 'security':
            recommendations.append("🔐 Conduct security review after implementation")
            
        return recommendations
        
    def generate_report(self, results: Dict, output_format: str = 'markdown') -> str:
        """Generate a comprehensive report from analysis results"""
        if output_format == 'markdown':
            return self._generate_markdown_report(results)
        elif output_format == 'json':
            return json.dumps(results, indent=2, default=str)
        else:
            return str(results)
            
    def _generate_markdown_report(self, results: Dict) -> str:
        """Generate markdown report"""
        report = []
        
        # Header
        report.append(f"# SWE-Lancer Task Analysis Report")
        report.append(f"**Task ID**: {results['task_id']}")
        report.append(f"**Type**: {results['task_type']}")
        report.append(f"**Estimated Value**: ${results['estimated_value']:,.0f}")
        report.append("")
        
        # Task details
        task = results['task_details']
        report.append("## Task Details")
        report.append(f"**Title**: {task.get('title', 'N/A')}")
        report.append(f"**Status**: {task.get('status', 'N/A')}")
        if task.get('description'):
            report.append(f"**Description**: {task['description']}")
        report.append("")
        
        # Tool results
        report.append("## Analysis Results")
        
        for tool_name, result in results['tool_results'].items():
            report.append(f"\n### {tool_name.replace('_', ' ').title()}")
            
            if result.success:
                report.append(f"✅ Success (execution time: {result.execution_time:.2f}s)")
                
                # Summarize key findings
                if tool_name == 'context_analyzer' and result.output:
                    if 'tech_stack' in result.output:
                        report.append(f"- **Technology**: {result.output['tech_stack'].get('language', 'Unknown')}")
                        if 'architecture' in result.output['tech_stack']:
                            report.append(f"- **Architecture**: {result.output['tech_stack']['architecture']}")
                            
                elif tool_name == 'security_auditor' and result.output:
                    if 'summary' in result.output:
                        summary = result.output['summary']
                        report.append(f"- **Total Issues**: {summary['total_issues']}")
                        report.append(f"- **Risk Level**: {summary['risk_level']}")
                        
                elif tool_name == 'performance_optimizer' and result.output:
                    if 'summary' in result.output:
                        summary = result.output['summary']
                        report.append(f"- **Health Score**: {summary['health_score']}/100")
                        report.append(f"- **Potential Improvement**: {summary.get('estimated_improvement', 'N/A')}")
                        
            else:
                report.append(f"❌ Failed: {result.error}")
                
        # Recommendations
        if results['recommendations']:
            report.append("\n## Recommendations")
            for rec in results['recommendations']:
                report.append(f"- {rec}")
                
        # Next steps
        report.append("\n## Next Steps")
        report.append("1. Review the analysis results above")
        report.append("2. Address any critical issues identified")
        report.append("3. Use the specific tool commands for detailed analysis")
        report.append("4. Update task status in task manager")
        
        return "\n".join(report)
        
    def update_task_with_results(self, task_id: str, results: Dict):
        """Update task in task manager with analysis results"""
        try:
            # Add analysis results as a note or file reference
            summary = f"Analysis completed: {len(results['tool_results'])} tools run"
            
            # Update task with summary
            subprocess.run([
                str(self.task_manager_path),
                'update',
                task_id,
                '-d',
                summary
            ])
            
            # Save detailed results
            results_file = self.project_root / f'.task-analysis-{task_id}.json'
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
                
            print(f"Task {task_id} updated with analysis results")
            
        except Exception as e:
            print(f"Error updating task: {e}")

def main():
    parser = argparse.ArgumentParser(description='SWE-Lancer Toolkit - Integrated tool suite')
    parser.add_argument('--task', help='Task ID from task manager')
    parser.add_argument('--analyze', help='Analyze a specific aspect', 
                       choices=['context', 'security', 'performance', 'all'])
    parser.add_argument('--project', default='.', help='Project root directory')
    parser.add_argument('--output', help='Output file for report')
    parser.add_argument('--format', choices=['markdown', 'json'], default='markdown',
                       help='Output format')
    parser.add_argument('--update-task', action='store_true', 
                       help='Update task with analysis results')
    
    args = parser.parse_args()
    
    toolkit = SWELancerToolkit(args.project)
    
    if not args.task:
        # Demo mode
        print("🚀 SWE-Lancer Toolkit")
        print("=" * 60)
        print("\nAvailable Tools:")
        
        tool_descriptions = {
            'context_analyzer': '🔍 Analyze codebase structure and dependencies',
            'cross_platform_test_gen': '🧪 Generate tests for multiple platforms',
            'proposal_analyzer': '📊 Evaluate implementation proposals',
            'impact_analyzer': '💥 Analyze change impacts across stack',
            'bug_pattern_engine': '🐛 Identify bug patterns and fixes',
            'security_auditor': '🔐 Audit security vulnerabilities',
            'multi_platform_feature': '📱 Plan multi-platform features',
            'api_integration_assistant': '🔌 Assist with API integrations',
            'performance_optimizer': '🚀 Optimize performance bottlenecks',
            'task_complexity_estimator': '📏 Estimate task complexity and effort'
        }
        
        for tool, desc in tool_descriptions.items():
            status = "✅" if tool in tools_available else "❌"
            print(f"{status} {tool}: {desc}")
            
        print("\nUsage:")
        print("  swe_lancer_toolkit.py --task <task_id>")
        print("  swe_lancer_toolkit.py --analyze all --project /path/to/project")
        
        return
        
    # Analyze task
    print(f"Analyzing task {args.task}...")
    results = toolkit.analyze_task(args.task)
    
    # Generate report
    report = toolkit.generate_report(results, args.format)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to {args.output}")
    else:
        print(report)
        
    # Update task if requested
    if args.update_task:
        toolkit.update_task_with_results(args.task, results)

if __name__ == '__main__':
    main()