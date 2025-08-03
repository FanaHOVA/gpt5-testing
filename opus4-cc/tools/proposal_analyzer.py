#!/usr/bin/env python3
"""
Implementation Proposal Analyzer - Evaluate freelancer proposals for SWE management
Analyzes technical merit, feasibility, cost-benefit, and success probability
"""

import os
import json
import argparse
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import hashlib

@dataclass
class Proposal:
    id: str
    author: str
    title: str
    description: str
    approach: str
    estimated_hours: float
    hourly_rate: float
    technologies: List[str]
    experience_level: str
    similar_projects: List[Dict]
    
@dataclass
class AnalysisResult:
    proposal_id: str
    technical_score: float  # 0-100
    feasibility_score: float  # 0-100
    cost_benefit_ratio: float
    risk_level: str  # low, medium, high
    success_probability: float  # 0-1
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]

class ProposalAnalyzer:
    def __init__(self, task_value: float, task_complexity: str = "medium"):
        self.task_value = task_value
        self.task_complexity = task_complexity
        self.historical_data = self._load_historical_data()
        
    def _load_historical_data(self) -> Dict:
        """Load historical project data for pattern matching"""
        # In a real implementation, this would load from a database
        return {
            'average_success_rate': 0.75,
            'technology_success_rates': {
                'react': 0.85,
                'vue': 0.82,
                'angular': 0.78,
                'django': 0.88,
                'flask': 0.80,
                'express': 0.83,
                'rails': 0.86,
                'spring': 0.84,
                'fastapi': 0.87,
            },
            'experience_multipliers': {
                'junior': 0.7,
                'mid': 1.0,
                'senior': 1.3,
                'expert': 1.5,
            },
            'common_failure_patterns': [
                'underestimated_time',
                'missing_requirements',
                'poor_communication',
                'technical_debt',
                'scope_creep',
            ]
        }
        
    def analyze_proposal(self, proposal: Proposal) -> AnalysisResult:
        """Analyze a single proposal"""
        technical_score = self._calculate_technical_score(proposal)
        feasibility_score = self._calculate_feasibility_score(proposal)
        cost_benefit_ratio = self._calculate_cost_benefit(proposal)
        risk_level = self._assess_risk(proposal)
        success_probability = self._calculate_success_probability(proposal)
        strengths = self._identify_strengths(proposal)
        weaknesses = self._identify_weaknesses(proposal)
        recommendations = self._generate_recommendations(proposal, weaknesses)
        
        return AnalysisResult(
            proposal_id=proposal.id,
            technical_score=technical_score,
            feasibility_score=feasibility_score,
            cost_benefit_ratio=cost_benefit_ratio,
            risk_level=risk_level,
            success_probability=success_probability,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations
        )
        
    def _calculate_technical_score(self, proposal: Proposal) -> float:
        """Calculate technical merit score"""
        score = 50.0  # Base score
        
        # Technology alignment
        tech_scores = []
        for tech in proposal.technologies:
            tech_lower = tech.lower()
            if tech_lower in self.historical_data['technology_success_rates']:
                tech_scores.append(self.historical_data['technology_success_rates'][tech_lower] * 100)
            else:
                tech_scores.append(70)  # Unknown tech gets average score
                
        if tech_scores:
            score += sum(tech_scores) / len(tech_scores) * 0.3  # 30% weight
            
        # Experience level
        exp_mult = self.historical_data['experience_multipliers'].get(proposal.experience_level, 1.0)
        score *= exp_mult
        
        # Similar projects boost
        if proposal.similar_projects:
            similarity_boost = min(len(proposal.similar_projects) * 5, 20)
            score += similarity_boost
            
        # Approach quality (simple heuristic based on detail)
        approach_words = len(proposal.approach.split())
        if approach_words > 200:
            score += 10
        elif approach_words > 100:
            score += 5
            
        return min(score, 100)
        
    def _calculate_feasibility_score(self, proposal: Proposal) -> float:
        """Calculate feasibility score"""
        score = 80.0  # Base score
        
        # Time estimation accuracy
        expected_hours = self._estimate_expected_hours()
        time_ratio = proposal.estimated_hours / expected_hours
        
        if 0.8 <= time_ratio <= 1.2:
            score += 20  # Good estimation
        elif 0.5 <= time_ratio <= 1.5:
            score += 10  # Reasonable estimation
        else:
            score -= 20  # Poor estimation
            
        # Check for red flags in approach
        approach_lower = proposal.approach.lower()
        red_flags = ['quick fix', 'temporary solution', 'hack', 'workaround']
        for flag in red_flags:
            if flag in approach_lower:
                score -= 10
                
        # Technology appropriateness
        if self._are_technologies_appropriate(proposal.technologies):
            score += 10
            
        return max(min(score, 100), 0)
        
    def _calculate_cost_benefit(self, proposal: Proposal) -> float:
        """Calculate cost-benefit ratio"""
        total_cost = proposal.estimated_hours * proposal.hourly_rate
        
        # Adjust benefit based on success probability
        expected_benefit = self.task_value * self._calculate_success_probability(proposal)
        
        return expected_benefit / total_cost if total_cost > 0 else 0
        
    def _assess_risk(self, proposal: Proposal) -> str:
        """Assess risk level"""
        risk_score = 0
        
        # Time estimation risk
        expected_hours = self._estimate_expected_hours()
        time_ratio = proposal.estimated_hours / expected_hours
        if time_ratio < 0.5 or time_ratio > 2.0:
            risk_score += 3
            
        # Experience risk
        if proposal.experience_level in ['junior']:
            risk_score += 2
            
        # Technology risk
        unknown_tech_count = sum(
            1 for tech in proposal.technologies 
            if tech.lower() not in self.historical_data['technology_success_rates']
        )
        risk_score += unknown_tech_count
        
        # Cost risk
        if proposal.hourly_rate * proposal.estimated_hours > self.task_value * 0.8:
            risk_score += 2
            
        if risk_score <= 2:
            return "low"
        elif risk_score <= 5:
            return "medium"
        else:
            return "high"
            
    def _calculate_success_probability(self, proposal: Proposal) -> float:
        """Calculate probability of successful completion"""
        base_probability = self.historical_data['average_success_rate']
        
        # Adjust based on experience
        exp_mult = self.historical_data['experience_multipliers'].get(proposal.experience_level, 1.0)
        probability = base_probability * exp_mult
        
        # Adjust based on similar projects
        if proposal.similar_projects:
            similar_project_boost = min(len(proposal.similar_projects) * 0.05, 0.15)
            probability += similar_project_boost
            
        # Adjust based on approach quality
        if len(proposal.approach) > 200 and 'test' in proposal.approach.lower():
            probability += 0.1
            
        # Adjust based on risk
        risk_level = self._assess_risk(proposal)
        risk_adjustments = {'low': 0, 'medium': -0.1, 'high': -0.25}
        probability += risk_adjustments[risk_level]
        
        return max(min(probability, 0.95), 0.3)
        
    def _identify_strengths(self, proposal: Proposal) -> List[str]:
        """Identify proposal strengths"""
        strengths = []
        
        if proposal.similar_projects:
            strengths.append(f"Has completed {len(proposal.similar_projects)} similar projects")
            
        if proposal.experience_level in ['senior', 'expert']:
            strengths.append(f"{proposal.experience_level.capitalize()} level experience")
            
        if 'test' in proposal.approach.lower():
            strengths.append("Includes testing in approach")
            
        if self._calculate_cost_benefit(proposal) > 1.5:
            strengths.append("Excellent cost-benefit ratio")
            
        tech_scores = [
            self.historical_data['technology_success_rates'].get(tech.lower(), 0)
            for tech in proposal.technologies
        ]
        if tech_scores and sum(tech_scores) / len(tech_scores) > 0.85:
            strengths.append("Uses proven technology stack")
            
        return strengths
        
    def _identify_weaknesses(self, proposal: Proposal) -> List[str]:
        """Identify proposal weaknesses"""
        weaknesses = []
        
        # Time estimation issues
        expected_hours = self._estimate_expected_hours()
        time_ratio = proposal.estimated_hours / expected_hours
        if time_ratio < 0.5:
            weaknesses.append("Significantly underestimated time")
        elif time_ratio > 2.0:
            weaknesses.append("Significantly overestimated time")
            
        # Cost issues
        if proposal.hourly_rate * proposal.estimated_hours > self.task_value * 0.8:
            weaknesses.append("Cost approaches or exceeds task value")
            
        # Experience issues
        if proposal.experience_level == 'junior' and self.task_complexity in ['high', 'critical']:
            weaknesses.append("Junior experience may not match task complexity")
            
        # Approach issues
        if len(proposal.approach) < 100:
            weaknesses.append("Approach lacks detail")
            
        if 'test' not in proposal.approach.lower():
            weaknesses.append("No mention of testing strategy")
            
        return weaknesses
        
    def _generate_recommendations(self, proposal: Proposal, weaknesses: List[str]) -> List[str]:
        """Generate recommendations for proposal improvement"""
        recommendations = []
        
        for weakness in weaknesses:
            if "underestimated time" in weakness:
                recommendations.append("Request detailed time breakdown and add buffer")
            elif "overestimated time" in weakness:
                recommendations.append("Negotiate timeline or explore phased approach")
            elif "Cost approaches" in weakness:
                recommendations.append("Negotiate rate or reduce scope")
            elif "Junior experience" in weakness:
                recommendations.append("Require senior oversight or mentorship")
            elif "lacks detail" in weakness:
                recommendations.append("Request more detailed implementation plan")
            elif "testing strategy" in weakness:
                recommendations.append("Require explicit testing plan and coverage goals")
                
        # General recommendations
        if self._assess_risk(proposal) == "high":
            recommendations.append("Consider milestone-based payments to reduce risk")
            
        if not proposal.similar_projects:
            recommendations.append("Request portfolio or references for similar work")
            
        return recommendations
        
    def _estimate_expected_hours(self) -> float:
        """Estimate expected hours based on task value and complexity"""
        # Simple heuristic: higher value tasks typically take more time
        base_hours = self.task_value / 100  # $100 per hour baseline
        
        complexity_multipliers = {
            'low': 0.5,
            'medium': 1.0,
            'high': 2.0,
            'critical': 3.0
        }
        
        return base_hours * complexity_multipliers.get(self.task_complexity, 1.0)
        
    def _are_technologies_appropriate(self, technologies: List[str]) -> bool:
        """Check if proposed technologies are appropriate"""
        # In a real implementation, this would check against task requirements
        return len(technologies) > 0 and len(technologies) < 10
        
    def rank_proposals(self, proposals: List[Proposal]) -> List[Tuple[Proposal, AnalysisResult]]:
        """Rank multiple proposals"""
        results = []
        for proposal in proposals:
            analysis = self.analyze_proposal(proposal)
            results.append((proposal, analysis))
            
        # Sort by composite score
        def composite_score(result: Tuple[Proposal, AnalysisResult]) -> float:
            analysis = result[1]
            return (
                analysis.technical_score * 0.3 +
                analysis.feasibility_score * 0.3 +
                analysis.success_probability * 100 * 0.2 +
                min(analysis.cost_benefit_ratio * 20, 100) * 0.2
            )
            
        results.sort(key=composite_score, reverse=True)
        return results

def create_sample_proposals() -> List[Proposal]:
    """Create sample proposals for testing"""
    return [
        Proposal(
            id="001",
            author="dev_expert_123",
            title="Efficient Bug Fix with Comprehensive Testing",
            description="Fix double-triggered API call issue",
            approach="""
            I'll start by analyzing the event handlers and API call mechanisms to identify
            the root cause. Then implement debouncing/throttling as needed. Will add
            comprehensive unit and integration tests to prevent regression. Finally,
            I'll document the fix and any architectural improvements made.
            """,
            estimated_hours=8,
            hourly_rate=125,
            technologies=["react", "jest", "typescript"],
            experience_level="senior",
            similar_projects=[
                {"name": "API optimization for e-commerce", "value": 1200},
                {"name": "Event handler refactoring", "value": 800}
            ]
        ),
        Proposal(
            id="002",
            author="quick_fixer",
            title="Quick API Fix",
            description="I can fix this quickly",
            approach="Will find the bug and fix it with a quick workaround.",
            estimated_hours=2,
            hourly_rate=50,
            technologies=["javascript"],
            experience_level="junior",
            similar_projects=[]
        ),
        Proposal(
            id="003",
            author="full_stack_pro",
            title="Comprehensive Solution with Architecture Review",
            description="Fix the issue and improve overall system reliability",
            approach="""
            1. Root cause analysis using debugging tools and logs
            2. Implement proper event handling with RxJS observables
            3. Add request deduplication at API gateway level
            4. Implement circuit breaker pattern for resilience
            5. Add monitoring and alerting for similar issues
            6. Full test coverage including load testing
            7. Documentation and knowledge transfer
            """,
            estimated_hours=24,
            hourly_rate=150,
            technologies=["react", "rxjs", "node.js", "jest", "datadog"],
            experience_level="expert",
            similar_projects=[
                {"name": "Payment system reliability", "value": 5000},
                {"name": "High-traffic API optimization", "value": 3500},
                {"name": "Event-driven architecture", "value": 4000}
            ]
        )
    ]

def main():
    parser = argparse.ArgumentParser(description='Analyze freelancer proposals for SWE tasks')
    parser.add_argument('--task-value', type=float, default=1000, help='Task value in dollars')
    parser.add_argument('--complexity', choices=['low', 'medium', 'high', 'critical'], 
                       default='medium', help='Task complexity')
    parser.add_argument('--proposals', help='JSON file with proposals')
    parser.add_argument('--format', choices=['summary', 'detailed', 'json'], 
                       default='summary', help='Output format')
    
    args = parser.parse_args()
    
    # Load or create proposals
    if args.proposals:
        with open(args.proposals, 'r') as f:
            proposal_data = json.load(f)
            proposals = [Proposal(**p) for p in proposal_data]
    else:
        proposals = create_sample_proposals()
        
    # Analyze proposals
    analyzer = ProposalAnalyzer(args.task_value, args.complexity)
    ranked_results = analyzer.rank_proposals(proposals)
    
    # Output results
    if args.format == 'json':
        output = []
        for proposal, analysis in ranked_results:
            output.append({
                'proposal': proposal.__dict__,
                'analysis': analysis.__dict__
            })
        print(json.dumps(output, indent=2))
    else:
        print(f"\n📊 PROPOSAL ANALYSIS REPORT")
        print(f"Task Value: ${args.task_value} | Complexity: {args.complexity}")
        print("=" * 60)
        
        for i, (proposal, analysis) in enumerate(ranked_results, 1):
            print(f"\n🏆 Rank #{i}: {proposal.title}")
            print(f"Author: {proposal.author} | Experience: {proposal.experience_level}")
            print(f"Cost: ${proposal.estimated_hours * proposal.hourly_rate:.2f} ({proposal.estimated_hours}h @ ${proposal.hourly_rate}/h)")
            print(f"\nScores:")
            print(f"  Technical Merit: {analysis.technical_score:.1f}/100")
            print(f"  Feasibility: {analysis.feasibility_score:.1f}/100")
            print(f"  Cost-Benefit Ratio: {analysis.cost_benefit_ratio:.2f}")
            print(f"  Success Probability: {analysis.success_probability:.1%}")
            print(f"  Risk Level: {analysis.risk_level}")
            
            if args.format == 'detailed':
                if analysis.strengths:
                    print(f"\n✅ Strengths:")
                    for strength in analysis.strengths:
                        print(f"  • {strength}")
                        
                if analysis.weaknesses:
                    print(f"\n⚠️  Weaknesses:")
                    for weakness in analysis.weaknesses:
                        print(f"  • {weakness}")
                        
                if analysis.recommendations:
                    print(f"\n💡 Recommendations:")
                    for rec in analysis.recommendations:
                        print(f"  • {rec}")
                        
            print("-" * 60)
            
        # Summary recommendation
        if ranked_results:
            best_proposal, best_analysis = ranked_results[0]
            print(f"\n🎯 RECOMMENDATION:")
            print(f"Select proposal from {best_proposal.author} with {best_analysis.success_probability:.0%} success probability")
            if best_analysis.risk_level == "high":
                print("⚠️  Note: This is a high-risk proposal. Consider risk mitigation strategies.")

if __name__ == '__main__':
    main()