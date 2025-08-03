#!/usr/bin/env python3
"""
Task Complexity Estimator - Estimate effort and approach based on task value
Calibrates effort estimation based on the $250-$32,000 task value range
"""

import os
import json
import argparse
import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import hashlib
from collections import defaultdict

@dataclass
class TaskRequirement:
    category: str  # 'functional', 'technical', 'design', 'testing'
    description: str
    complexity_weight: float
    
@dataclass
class TaskEstimate:
    task_id: str
    title: str
    value: float
    complexity_score: float
    estimated_hours: float
    confidence_level: float  # 0-1
    approach: str  # 'simple', 'standard', 'complex', 'enterprise'
    team_size: int
    risks: List[str]
    milestones: List[Dict[str, Any]]
    
@dataclass
class ComplexityFactors:
    technical_debt: float
    integration_points: int
    platforms: int
    user_impact: str  # 'low', 'medium', 'high', 'critical'
    performance_requirements: bool
    security_requirements: bool
    compliance_requirements: bool

class TaskComplexityEstimator:
    def __init__(self):
        self.historical_data = self._load_historical_data()
        self.complexity_model = self._initialize_complexity_model()
        
    def _load_historical_data(self) -> Dict[str, Any]:
        """Load historical task completion data"""
        return {
            'value_to_hours_ratio': {
                (0, 500): 0.02,      # $250-500: ~5-10 hours
                (500, 1000): 0.015,  # $500-1000: ~7.5-15 hours
                (1000, 5000): 0.012, # $1000-5000: ~12-60 hours
                (5000, 15000): 0.01, # $5000-15000: ~50-150 hours
                (15000, 35000): 0.008 # $15000+: ~120-280 hours
            },
            'complexity_multipliers': {
                'simple': 0.7,
                'standard': 1.0,
                'complex': 1.5,
                'enterprise': 2.2
            },
            'success_rates': {
                'simple': 0.95,
                'standard': 0.85,
                'complex': 0.75,
                'enterprise': 0.65
            }
        }
        
    def _initialize_complexity_model(self) -> Dict[str, float]:
        """Initialize complexity scoring model"""
        return {
            # Technical factors
            'new_feature': 1.0,
            'bug_fix': 0.3,
            'refactoring': 0.6,
            'optimization': 0.8,
            'migration': 1.2,
            
            # Integration factors
            'api_integration': 0.5,
            'database_change': 0.6,
            'third_party_service': 0.7,
            'multi_platform': 1.0,
            
            # Requirements factors
            'ui_changes': 0.4,
            'backend_logic': 0.6,
            'security_critical': 0.8,
            'performance_critical': 0.7,
            'data_migration': 0.9,
            
            # Testing factors
            'unit_tests': 0.2,
            'integration_tests': 0.3,
            'e2e_tests': 0.5,
            'manual_testing': 0.4
        }
        
    def estimate_task(self, title: str, description: str, value: float, 
                     requirements: Optional[List[str]] = None,
                     factors: Optional[ComplexityFactors] = None) -> TaskEstimate:
        """Estimate task complexity and effort"""
        
        # Extract requirements from description if not provided
        if not requirements:
            requirements = self._extract_requirements(title, description)
            
        # Calculate complexity score
        complexity_score = self._calculate_complexity_score(
            title, description, requirements, factors
        )
        
        # Determine approach based on value and complexity
        approach = self._determine_approach(value, complexity_score)
        
        # Estimate hours based on value and complexity
        estimated_hours = self._estimate_hours(value, complexity_score, approach)
        
        # Calculate confidence level
        confidence = self._calculate_confidence(value, complexity_score, requirements)
        
        # Determine team size
        team_size = self._recommend_team_size(value, estimated_hours, approach)
        
        # Identify risks
        risks = self._identify_risks(value, complexity_score, requirements, factors)
        
        # Generate milestones
        milestones = self._generate_milestones(estimated_hours, approach, requirements)
        
        return TaskEstimate(
            task_id=hashlib.md5(title.encode()).hexdigest()[:8],
            title=title,
            value=value,
            complexity_score=complexity_score,
            estimated_hours=estimated_hours,
            confidence_level=confidence,
            approach=approach,
            team_size=team_size,
            risks=risks,
            milestones=milestones
        )
        
    def _extract_requirements(self, title: str, description: str) -> List[str]:
        """Extract requirements from task description"""
        text = f"{title} {description}".lower()
        requirements = []
        
        # Feature patterns
        feature_keywords = {
            'add', 'implement', 'create', 'build', 'develop',
            'integrate', 'support', 'enable'
        }
        
        # Bug patterns
        bug_keywords = {
            'fix', 'resolve', 'bug', 'issue', 'error', 'problem',
            'broken', 'crash', 'fail'
        }
        
        # Technical patterns
        tech_patterns = [
            (r'api|endpoint|rest|graphql', 'api_integration'),
            (r'database|sql|query|migration', 'database_change'),
            (r'ui|ux|interface|design|frontend', 'ui_changes'),
            (r'backend|server|service', 'backend_logic'),
            (r'performance|optimize|speed|fast', 'optimization'),
            (r'security|auth|permission|encrypt', 'security_critical'),
            (r'test|testing|coverage', 'testing'),
            (r'refactor|clean|improve', 'refactoring'),
            (r'mobile|ios|android|flutter|react.native', 'multi_platform'),
        ]
        
        # Check for feature vs bug
        if any(word in text for word in feature_keywords):
            requirements.append('new_feature')
        elif any(word in text for word in bug_keywords):
            requirements.append('bug_fix')
            
        # Check technical patterns
        for pattern, req in tech_patterns:
            if re.search(pattern, text):
                requirements.append(req)
                
        # Platform detection
        platforms = []
        if 'web' in text or 'browser' in text:
            platforms.append('web')
        if 'ios' in text or 'iphone' in text:
            platforms.append('ios')
        if 'android' in text:
            platforms.append('android')
        if 'desktop' in text or 'electron' in text:
            platforms.append('desktop')
            
        if len(platforms) > 1:
            requirements.append('multi_platform')
            
        return requirements
        
    def _calculate_complexity_score(self, title: str, description: str, 
                                  requirements: List[str], 
                                  factors: Optional[ComplexityFactors]) -> float:
        """Calculate overall complexity score"""
        base_score = 0.0
        
        # Add scores from requirements
        for req in requirements:
            base_score += self.complexity_model.get(req, 0.3)
            
        # Adjust based on description length (more detailed = more complex)
        desc_words = len(description.split())
        if desc_words > 200:
            base_score *= 1.2
        elif desc_words < 50:
            base_score *= 0.8
            
        # Apply additional factors if provided
        if factors:
            # Technical debt increases complexity
            base_score *= (1 + factors.technical_debt * 0.5)
            
            # Integration points
            base_score += factors.integration_points * 0.2
            
            # Multiple platforms
            if factors.platforms > 1:
                base_score *= (1 + (factors.platforms - 1) * 0.3)
                
            # Critical requirements
            if factors.performance_requirements:
                base_score *= 1.3
            if factors.security_requirements:
                base_score *= 1.4
            if factors.compliance_requirements:
                base_score *= 1.5
                
            # User impact
            impact_multipliers = {
                'low': 1.0,
                'medium': 1.2,
                'high': 1.5,
                'critical': 2.0
            }
            base_score *= impact_multipliers.get(factors.user_impact, 1.0)
            
        return min(base_score, 10.0)  # Cap at 10
        
    def _determine_approach(self, value: float, complexity_score: float) -> str:
        """Determine implementation approach based on value and complexity"""
        # Value-based thresholds
        if value < 500:
            if complexity_score < 2:
                return 'simple'
            else:
                return 'standard'
        elif value < 5000:
            if complexity_score < 3:
                return 'standard'
            else:
                return 'complex'
        else:  # > $5000
            if complexity_score < 4:
                return 'complex'
            else:
                return 'enterprise'
                
    def _estimate_hours(self, value: float, complexity_score: float, approach: str) -> float:
        """Estimate hours based on value and complexity"""
        # Find base ratio for value range
        base_ratio = 0.01
        for (min_val, max_val), ratio in self.historical_data['value_to_hours_ratio'].items():
            if min_val <= value <= max_val:
                base_ratio = ratio
                break
                
        # Calculate base hours
        base_hours = value * base_ratio
        
        # Apply complexity multiplier
        complexity_multiplier = 1 + (complexity_score - 1) * 0.15
        
        # Apply approach multiplier
        approach_multiplier = self.historical_data['complexity_multipliers'][approach]
        
        estimated_hours = base_hours * complexity_multiplier * approach_multiplier
        
        # Apply bounds based on value
        if value < 1000:
            estimated_hours = max(2, min(estimated_hours, 20))
        elif value < 5000:
            estimated_hours = max(10, min(estimated_hours, 80))
        else:
            estimated_hours = max(40, min(estimated_hours, 400))
            
        return round(estimated_hours, 1)
        
    def _calculate_confidence(self, value: float, complexity_score: float, 
                            requirements: List[str]) -> float:
        """Calculate confidence level in estimate"""
        confidence = 0.8  # Base confidence
        
        # Lower confidence for very high value tasks
        if value > 20000:
            confidence -= 0.2
        elif value > 10000:
            confidence -= 0.1
            
        # Lower confidence for high complexity
        if complexity_score > 7:
            confidence -= 0.2
        elif complexity_score > 5:
            confidence -= 0.1
            
        # Higher confidence for common patterns
        common_patterns = ['bug_fix', 'api_integration', 'ui_changes']
        common_count = sum(1 for req in requirements if req in common_patterns)
        confidence += common_count * 0.05
        
        # Lower confidence for unclear requirements
        if len(requirements) < 2:
            confidence -= 0.1
            
        return max(0.3, min(confidence, 0.95))
        
    def _recommend_team_size(self, value: float, hours: float, approach: str) -> int:
        """Recommend team size based on task parameters"""
        if approach == 'simple':
            return 1
        elif approach == 'standard':
            if hours > 40:
                return 2
            return 1
        elif approach == 'complex':
            if value > 10000 or hours > 100:
                return 3
            return 2
        else:  # enterprise
            if value > 20000:
                return 4
            return 3
            
    def _identify_risks(self, value: float, complexity_score: float,
                       requirements: List[str], factors: Optional[ComplexityFactors]) -> List[str]:
        """Identify project risks"""
        risks = []
        
        # Value-based risks
        if value > 15000:
            risks.append("High-value task requires extensive stakeholder management")
            
        # Complexity risks
        if complexity_score > 7:
            risks.append("High complexity may lead to timeline overruns")
            
        # Requirement-based risks
        if 'multi_platform' in requirements:
            risks.append("Multi-platform requirements increase testing complexity")
            
        if 'security_critical' in requirements:
            risks.append("Security requirements need specialized expertise")
            
        if 'performance_critical' in requirements:
            risks.append("Performance requirements may require optimization iterations")
            
        if 'database_change' in requirements:
            risks.append("Database changes require careful migration planning")
            
        # Factor-based risks
        if factors:
            if factors.technical_debt > 0.5:
                risks.append("High technical debt may complicate implementation")
                
            if factors.integration_points > 3:
                risks.append("Multiple integration points increase failure possibilities")
                
            if factors.compliance_requirements:
                risks.append("Compliance requirements add verification overhead")
                
        # General risks
        if len(requirements) > 5:
            risks.append("Multiple requirements increase coordination complexity")
            
        return risks
        
    def _generate_milestones(self, hours: float, approach: str, 
                           requirements: List[str]) -> List[Dict[str, Any]]:
        """Generate project milestones"""
        milestones = []
        
        if approach == 'simple':
            milestones.append({
                'name': 'Implementation Complete',
                'hours': hours * 0.8,
                'deliverables': ['Working code', 'Basic tests']
            })
            milestones.append({
                'name': 'Testing & Deployment',
                'hours': hours * 0.2,
                'deliverables': ['All tests passing', 'Deployed to production']
            })
            
        elif approach == 'standard':
            milestones.append({
                'name': 'Design & Planning',
                'hours': hours * 0.15,
                'deliverables': ['Technical design', 'Implementation plan']
            })
            milestones.append({
                'name': 'Core Implementation',
                'hours': hours * 0.5,
                'deliverables': ['Core functionality', 'Unit tests']
            })
            milestones.append({
                'name': 'Integration & Testing',
                'hours': hours * 0.25,
                'deliverables': ['Integration complete', 'E2E tests']
            })
            milestones.append({
                'name': 'Polish & Deployment',
                'hours': hours * 0.1,
                'deliverables': ['Bug fixes', 'Production deployment']
            })
            
        else:  # complex or enterprise
            milestones.append({
                'name': 'Discovery & Architecture',
                'hours': hours * 0.2,
                'deliverables': ['Requirements analysis', 'Architecture design', 'POC']
            })
            milestones.append({
                'name': 'Foundation',
                'hours': hours * 0.25,
                'deliverables': ['Core infrastructure', 'Base components', 'CI/CD setup']
            })
            milestones.append({
                'name': 'Feature Implementation',
                'hours': hours * 0.3,
                'deliverables': ['Feature complete', 'Integration tests']
            })
            milestones.append({
                'name': 'Hardening',
                'hours': hours * 0.15,
                'deliverables': ['Performance optimization', 'Security review', 'Load testing']
            })
            milestones.append({
                'name': 'Release Preparation',
                'hours': hours * 0.1,
                'deliverables': ['Documentation', 'Deployment guide', 'Production release']
            })
            
        # Add cumulative hours
        cumulative = 0
        for milestone in milestones:
            cumulative += milestone['hours']
            milestone['cumulative_hours'] = round(cumulative, 1)
            milestone['percentage'] = round((cumulative / hours) * 100)
            
        return milestones
        
    def analyze_portfolio(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a portfolio of tasks for resource planning"""
        total_value = sum(task['value'] for task in tasks)
        estimates = []
        
        for task in tasks:
            estimate = self.estimate_task(
                task['title'],
                task.get('description', ''),
                task['value'],
                task.get('requirements'),
                task.get('factors')
            )
            estimates.append(estimate)
            
        # Aggregate analysis
        total_hours = sum(e.estimated_hours for e in estimates)
        
        by_approach = defaultdict(int)
        for e in estimates:
            by_approach[e.approach] += 1
            
        # Resource requirements
        max_team_size = max(e.team_size for e in estimates)
        
        # Risk analysis
        all_risks = []
        for e in estimates:
            all_risks.extend(e.risks)
            
        risk_frequency = defaultdict(int)
        for risk in all_risks:
            risk_frequency[risk] += 1
            
        return {
            'portfolio_value': total_value,
            'total_estimated_hours': total_hours,
            'average_confidence': sum(e.confidence_level for e in estimates) / len(estimates),
            'task_distribution': dict(by_approach),
            'resource_requirements': {
                'max_team_size': max_team_size,
                'total_developer_hours': total_hours,
                'timeline_weeks': total_hours / (40 * max_team_size)
            },
            'top_risks': sorted(risk_frequency.items(), key=lambda x: x[1], reverse=True)[:5],
            'estimates': estimates
        }
        
    def generate_roi_analysis(self, estimate: TaskEstimate) -> Dict[str, float]:
        """Generate ROI analysis for a task"""
        # Calculate costs
        hourly_rate = 100  # Average developer rate
        development_cost = estimate.estimated_hours * hourly_rate * estimate.team_size
        
        # Add overhead (PM, QA, etc.)
        total_cost = development_cost * 1.3
        
        # Calculate ROI
        roi = ((estimate.value - total_cost) / total_cost) * 100
        
        # Break-even analysis
        break_even_hours = estimate.value / (hourly_rate * estimate.team_size * 1.3)
        
        return {
            'development_cost': development_cost,
            'total_cost': total_cost,
            'profit': estimate.value - total_cost,
            'roi_percentage': roi,
            'break_even_hours': break_even_hours,
            'margin': (estimate.value - total_cost) / estimate.value * 100
        }

def create_sample_tasks():
    """Create sample tasks for testing"""
    return [
        {
            'title': 'Fix double-triggered API call',
            'description': 'API endpoint is being called twice on button click causing duplicate entries',
            'value': 500
        },
        {
            'title': 'Implement user permission system',
            'description': 'Add role-based access control with admin, editor, and viewer roles across web and mobile apps',
            'value': 5000
        },
        {
            'title': 'Add video playback feature',
            'description': 'Implement in-app video playback with streaming, offline support, and subtitles for iOS, Android, web, and desktop platforms',
            'value': 16000
        },
        {
            'title': 'Migrate database to new architecture',
            'description': 'Complete database migration from PostgreSQL to distributed architecture with zero downtime',
            'value': 25000,
            'factors': ComplexityFactors(
                technical_debt=0.7,
                integration_points=5,
                platforms=1,
                user_impact='critical',
                performance_requirements=True,
                security_requirements=True,
                compliance_requirements=False
            )
        }
    ]

def main():
    parser = argparse.ArgumentParser(description='Estimate task complexity and effort')
    parser.add_argument('--task', help='Task title')
    parser.add_argument('--description', help='Task description')
    parser.add_argument('--value', type=float, help='Task value in dollars')
    parser.add_argument('--portfolio', help='JSON file with multiple tasks')
    parser.add_argument('--demo', action='store_true', help='Run demo analysis')
    
    args = parser.parse_args()
    
    estimator = TaskComplexityEstimator()
    
    if args.demo or (not args.task and not args.portfolio):
        # Demo mode
        print("📊 Task Complexity Estimator - Demo Mode")
        print("=" * 60)
        
        tasks = create_sample_tasks()
        
        for task in tasks:
            print(f"\n{'='*60}")
            estimate = estimator.estimate_task(
                task['title'],
                task['description'],
                task['value'],
                factors=task.get('factors')
            )
            
            print(f"\n💰 Task: {estimate.title}")
            print(f"Value: ${estimate.value:,.0f}")
            print(f"\n📈 Estimates:")
            print(f"  Complexity Score: {estimate.complexity_score:.1f}/10")
            print(f"  Estimated Hours: {estimate.estimated_hours:.1f}")
            print(f"  Confidence Level: {estimate.confidence_level:.0%}")
            print(f"  Approach: {estimate.approach.capitalize()}")
            print(f"  Team Size: {estimate.team_size} developer(s)")
            
            # ROI Analysis
            roi = estimator.generate_roi_analysis(estimate)
            print(f"\n💵 ROI Analysis:")
            print(f"  Development Cost: ${roi['development_cost']:,.0f}")
            print(f"  Total Cost: ${roi['total_cost']:,.0f}")
            print(f"  Profit: ${roi['profit']:,.0f}")
            print(f"  ROI: {roi['roi_percentage']:.0f}%")
            print(f"  Margin: {roi['margin']:.0f}%")
            
            if estimate.risks:
                print(f"\n⚠️  Risks:")
                for risk in estimate.risks:
                    print(f"  • {risk}")
                    
            print(f"\n📍 Milestones:")
            for milestone in estimate.milestones:
                print(f"  {milestone['percentage']:3d}% - {milestone['name']} ({milestone['hours']:.0f}h)")
                print(f"       Deliverables: {', '.join(milestone['deliverables'])}")
                
        # Portfolio analysis
        print(f"\n{'='*60}")
        print("\n📊 Portfolio Analysis")
        portfolio_analysis = estimator.analyze_portfolio(tasks)
        
        print(f"\nTotal Portfolio Value: ${portfolio_analysis['portfolio_value']:,.0f}")
        print(f"Total Estimated Hours: {portfolio_analysis['total_estimated_hours']:.0f}")
        print(f"Timeline: {portfolio_analysis['resource_requirements']['timeline_weeks']:.1f} weeks")
        print(f"Max Team Size: {portfolio_analysis['resource_requirements']['max_team_size']}")
        print(f"Average Confidence: {portfolio_analysis['average_confidence']:.0%}")
        
        print("\nTask Distribution:")
        for approach, count in portfolio_analysis['task_distribution'].items():
            print(f"  {approach.capitalize()}: {count}")
            
        print("\nTop Portfolio Risks:")
        for risk, count in portfolio_analysis['top_risks']:
            print(f"  • {risk} (affects {count} tasks)")
            
    elif args.portfolio:
        # Analyze portfolio
        with open(args.portfolio, 'r') as f:
            tasks = json.load(f)
            
        analysis = estimator.analyze_portfolio(tasks)
        print(json.dumps(analysis, indent=2, default=str))
        
    elif args.task:
        # Single task analysis
        estimate = estimator.estimate_task(
            args.task,
            args.description or '',
            args.value or 1000
        )
        
        print(f"\n📊 Task Complexity Analysis")
        print("=" * 60)
        print(f"Task: {estimate.title}")
        print(f"Value: ${estimate.value:,.0f}")
        print(f"Complexity: {estimate.complexity_score:.1f}/10")
        print(f"Hours: {estimate.estimated_hours:.1f}")
        print(f"Confidence: {estimate.confidence_level:.0%}")
        print(f"Team Size: {estimate.team_size}")
        
        roi = estimator.generate_roi_analysis(estimate)
        print(f"\nROI: {roi['roi_percentage']:.0f}%")
        print(f"Profit Margin: {roi['margin']:.0f}%")

if __name__ == '__main__':
    main()