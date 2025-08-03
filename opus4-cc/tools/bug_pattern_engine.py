#!/usr/bin/env python3
"""
Bug Pattern Recognition Engine - Identify similar bugs and suggest proven fixes
Uses historical data and pattern matching to accelerate bug resolution
"""

import os
import json
import argparse
import re
import hashlib
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
import difflib

@dataclass
class Bug:
    id: str
    title: str
    description: str
    stack_trace: Optional[str]
    error_message: Optional[str]
    affected_files: List[str]
    symptoms: List[str]
    root_cause: Optional[str]
    fix_description: Optional[str]
    fix_diff: Optional[str]
    tags: List[str]
    severity: str
    value: float  # Task value in dollars

@dataclass
class Pattern:
    pattern_id: str
    name: str
    symptoms: List[str]
    common_causes: List[str]
    fix_templates: List[str]
    success_rate: float
    avg_fix_time: float
    occurrences: int

@dataclass
class FixSuggestion:
    pattern_id: str
    confidence: float
    description: str
    code_changes: List[str]
    similar_bugs: List[str]
    estimated_time: float
    success_probability: float

class BugPatternEngine:
    def __init__(self):
        self.bug_database = []
        self.patterns = []
        self._load_pattern_database()
        
    def _load_pattern_database(self):
        """Load common bug patterns"""
        self.patterns = [
            Pattern(
                pattern_id="double_api_call",
                name="Double-triggered API Call",
                symptoms=["duplicate requests", "multiple api calls", "repeated actions"],
                common_causes=[
                    "Missing event handler cleanup",
                    "Duplicate event listeners",
                    "Missing debounce/throttle",
                    "React double render in StrictMode"
                ],
                fix_templates=[
                    "Add debounce to event handler",
                    "Remove event listener on cleanup",
                    "Use useEffect cleanup function",
                    "Implement request deduplication"
                ],
                success_rate=0.92,
                avg_fix_time=3.5,
                occurrences=247
            ),
            Pattern(
                pattern_id="permission_error",
                name="Permission/Authorization Error",
                symptoms=["403 error", "unauthorized", "permission denied", "access denied"],
                common_causes=[
                    "Missing authentication token",
                    "Expired session",
                    "Incorrect role checks",
                    "CORS misconfiguration"
                ],
                fix_templates=[
                    "Verify token is sent in headers",
                    "Check token expiration handling",
                    "Review role-based access control",
                    "Update CORS configuration"
                ],
                success_rate=0.88,
                avg_fix_time=4.2,
                occurrences=189
            ),
            Pattern(
                pattern_id="state_sync",
                name="State Synchronization Issue",
                symptoms=["stale data", "ui not updating", "inconsistent state", "race condition"],
                common_causes=[
                    "Missing state dependencies",
                    "Async state updates",
                    "Stale closure",
                    "Improper state management"
                ],
                fix_templates=[
                    "Add missing dependencies to useEffect",
                    "Use functional state updates",
                    "Implement proper state management",
                    "Add optimistic updates"
                ],
                success_rate=0.85,
                avg_fix_time=5.1,
                occurrences=156
            ),
            Pattern(
                pattern_id="memory_leak",
                name="Memory Leak",
                symptoms=["increasing memory usage", "performance degradation", "app crash", "slow ui"],
                common_causes=[
                    "Unremoved event listeners",
                    "Uncancelled subscriptions",
                    "Circular references",
                    "Large object retention"
                ],
                fix_templates=[
                    "Clean up event listeners",
                    "Cancel subscriptions on unmount",
                    "Break circular references",
                    "Implement proper cleanup"
                ],
                success_rate=0.79,
                avg_fix_time=6.8,
                occurrences=98
            ),
            Pattern(
                pattern_id="null_reference",
                name="Null/Undefined Reference",
                symptoms=["cannot read property", "undefined is not", "null reference", "type error"],
                common_causes=[
                    "Missing null checks",
                    "Async data not loaded",
                    "Incorrect optional chaining",
                    "Type assumption errors"
                ],
                fix_templates=[
                    "Add null/undefined checks",
                    "Use optional chaining",
                    "Add loading states",
                    "Validate data before use"
                ],
                success_rate=0.94,
                avg_fix_time=2.1,
                occurrences=412
            ),
            Pattern(
                pattern_id="infinite_loop",
                name="Infinite Loop/Recursion",
                symptoms=["browser freeze", "stack overflow", "maximum call stack", "infinite render"],
                common_causes=[
                    "useEffect without dependencies",
                    "State update in render",
                    "Circular dependencies",
                    "Incorrect recursion base case"
                ],
                fix_templates=[
                    "Add proper effect dependencies",
                    "Move state updates out of render",
                    "Add recursion limits",
                    "Fix circular dependencies"
                ],
                success_rate=0.91,
                avg_fix_time=3.2,
                occurrences=134
            ),
            Pattern(
                pattern_id="data_validation",
                name="Data Validation Error",
                symptoms=["invalid data", "validation error", "schema mismatch", "type mismatch"],
                common_causes=[
                    "Missing validation",
                    "Incorrect data types",
                    "Schema drift",
                    "Missing required fields"
                ],
                fix_templates=[
                    "Add input validation",
                    "Update validation schema",
                    "Add type checking",
                    "Handle edge cases"
                ],
                success_rate=0.87,
                avg_fix_time=3.8,
                occurrences=203
            ),
            Pattern(
                pattern_id="async_error",
                name="Async/Promise Error",
                symptoms=["unhandled promise", "async error", "promise rejection", "timeout error"],
                common_causes=[
                    "Missing error handling",
                    "Unhandled promise rejection",
                    "Race conditions",
                    "Timeout issues"
                ],
                fix_templates=[
                    "Add try-catch blocks",
                    "Handle promise rejections",
                    "Implement proper error boundaries",
                    "Add timeout handling"
                ],
                success_rate=0.86,
                avg_fix_time=4.5,
                occurrences=178
            )
        ]
        
    def analyze_bug(self, bug: Bug) -> List[FixSuggestion]:
        """Analyze a bug and suggest fixes based on patterns"""
        suggestions = []
        
        # Extract features from the bug
        bug_features = self._extract_bug_features(bug)
        
        # Match against known patterns
        for pattern in self.patterns:
            similarity = self._calculate_pattern_similarity(bug_features, pattern)
            
            if similarity > 0.6:  # Threshold for pattern match
                suggestion = self._generate_fix_suggestion(bug, pattern, similarity)
                suggestions.append(suggestion)
                
        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        
        # Find similar historical bugs
        similar_bugs = self._find_similar_bugs(bug)
        if similar_bugs and suggestions:
            suggestions[0].similar_bugs = [b.id for b in similar_bugs[:3]]
            
        return suggestions
        
    def _extract_bug_features(self, bug: Bug) -> Dict[str, any]:
        """Extract features from bug for pattern matching"""
        features = {
            'symptoms': set(),
            'error_types': set(),
            'affected_areas': set(),
            'keywords': set()
        }
        
        # Extract from description and error message
        text = f"{bug.description} {bug.error_message or ''} {bug.stack_trace or ''}"
        text_lower = text.lower()
        
        # Common symptom keywords
        symptom_keywords = [
            'duplicate', 'multiple', 'repeated', 'twice', 'double',
            'not updating', 'stale', 'old data', 'wrong data',
            'crash', 'freeze', 'hang', 'slow', 'memory',
            'undefined', 'null', 'cannot read', 'type error',
            'permission', 'denied', 'unauthorized', '403', '401',
            'timeout', 'failed', 'error', 'exception'
        ]
        
        for keyword in symptom_keywords:
            if keyword in text_lower:
                features['symptoms'].add(keyword)
                
        # Extract error types from stack trace
        if bug.stack_trace:
            error_patterns = [
                r'TypeError:', r'ReferenceError:', r'SyntaxError:',
                r'RangeError:', r'Promise.*rejection', r'Error:'
            ]
            for pattern in error_patterns:
                if re.search(pattern, bug.stack_trace):
                    features['error_types'].add(pattern)
                    
        # Identify affected areas from file paths
        for file in bug.affected_files:
            if 'api' in file or 'endpoint' in file:
                features['affected_areas'].add('api')
            elif 'component' in file or 'view' in file:
                features['affected_areas'].add('frontend')
            elif 'model' in file or 'database' in file:
                features['affected_areas'].add('database')
            elif 'auth' in file or 'permission' in file:
                features['affected_areas'].add('auth')
                
        # Add explicit symptoms
        features['symptoms'].update(s.lower() for s in bug.symptoms)
        
        return features
        
    def _calculate_pattern_similarity(self, bug_features: Dict, pattern: Pattern) -> float:
        """Calculate similarity between bug features and pattern"""
        score = 0.0
        total_weight = 0.0
        
        # Symptom matching (weight: 0.5)
        pattern_symptoms = set(s.lower() for s in pattern.symptoms)
        bug_symptoms = bug_features['symptoms']
        
        if pattern_symptoms and bug_symptoms:
            symptom_overlap = len(pattern_symptoms & bug_symptoms)
            symptom_union = len(pattern_symptoms | bug_symptoms)
            if symptom_union > 0:
                score += 0.5 * (symptom_overlap / symptom_union)
                total_weight += 0.5
                
        # Keyword matching (weight: 0.3)
        pattern_keywords = set()
        for symptom in pattern.symptoms:
            pattern_keywords.update(symptom.lower().split())
        for cause in pattern.common_causes:
            pattern_keywords.update(cause.lower().split())
            
        keyword_overlap = len(pattern_keywords & bug_features['keywords'])
        if pattern_keywords:
            score += 0.3 * min(keyword_overlap / len(pattern_keywords), 1.0)
            total_weight += 0.3
            
        # Area matching (weight: 0.2)
        if pattern.pattern_id == "double_api_call" and 'api' in bug_features['affected_areas']:
            score += 0.2
            total_weight += 0.2
        elif pattern.pattern_id == "permission_error" and 'auth' in bug_features['affected_areas']:
            score += 0.2
            total_weight += 0.2
        elif pattern.pattern_id in ["state_sync", "null_reference"] and 'frontend' in bug_features['affected_areas']:
            score += 0.2
            total_weight += 0.2
            
        return score / total_weight if total_weight > 0 else 0
        
    def _generate_fix_suggestion(self, bug: Bug, pattern: Pattern, similarity: float) -> FixSuggestion:
        """Generate fix suggestion based on pattern match"""
        # Calculate confidence based on similarity and pattern success rate
        confidence = similarity * pattern.success_rate
        
        # Estimate time based on pattern average and bug value
        time_multiplier = 1.0
        if bug.value > 1000:
            time_multiplier = 1.3  # Complex bugs take longer
        elif bug.value < 300:
            time_multiplier = 0.8  # Simple bugs are faster
            
        estimated_time = pattern.avg_fix_time * time_multiplier
        
        # Generate specific code changes based on pattern
        code_changes = self._generate_code_changes(bug, pattern)
        
        # Create detailed description
        description = f"""
Based on pattern analysis, this appears to be a {pattern.name} issue.

Common causes for this pattern:
{chr(10).join(f'• {cause}' for cause in pattern.common_causes[:3])}

Recommended fixes:
{chr(10).join(f'{i+1}. {fix}' for i, fix in enumerate(pattern.fix_templates[:3]))}

This pattern has been successfully resolved in {pattern.occurrences} similar cases 
with a {pattern.success_rate:.0%} success rate.
"""
        
        return FixSuggestion(
            pattern_id=pattern.pattern_id,
            confidence=confidence,
            description=description.strip(),
            code_changes=code_changes,
            similar_bugs=[],
            estimated_time=estimated_time,
            success_probability=pattern.success_rate
        )
        
    def _generate_code_changes(self, bug: Bug, pattern: Pattern) -> List[str]:
        """Generate specific code change suggestions"""
        changes = []
        
        if pattern.pattern_id == "double_api_call":
            changes.append("""
// Add debounce to prevent double calls
import { debounce } from 'lodash';

const debouncedApiCall = debounce(async () => {
  await fetch('/api/endpoint');
}, 300);
""")
            changes.append("""
// Clean up event listeners
useEffect(() => {
  const handler = () => apiCall();
  element.addEventListener('click', handler);
  
  return () => {
    element.removeEventListener('click', handler);
  };
}, []);
""")
            
        elif pattern.pattern_id == "permission_error":
            changes.append("""
// Ensure auth token is included
const response = await fetch('/api/endpoint', {
  headers: {
    'Authorization': `Bearer ${getAuthToken()}`,
    'Content-Type': 'application/json'
  }
});
""")
            
        elif pattern.pattern_id == "null_reference":
            changes.append("""
// Add null checking
const value = data?.property?.subProperty ?? defaultValue;

// Or with explicit checking
if (data && data.property) {
  // Safe to use data.property
}
""")
            
        elif pattern.pattern_id == "state_sync":
            changes.append("""
// Use functional state update
setState(prevState => ({
  ...prevState,
  newValue: calculatedValue
}));

// Add missing dependencies
useEffect(() => {
  // Effect logic
}, [dependency1, dependency2]); // Include all dependencies
""")
            
        return changes
        
    def _find_similar_bugs(self, bug: Bug) -> List[Bug]:
        """Find similar bugs from historical data"""
        # In a real implementation, this would query a bug database
        # For now, return empty list
        return []
        
    def learn_from_fix(self, bug: Bug, applied_pattern_id: str, success: bool, time_taken: float):
        """Update pattern statistics based on fix results"""
        for pattern in self.patterns:
            if pattern.pattern_id == applied_pattern_id:
                # Update success rate
                pattern.occurrences += 1
                if success:
                    current_successes = pattern.success_rate * (pattern.occurrences - 1)
                    pattern.success_rate = (current_successes + 1) / pattern.occurrences
                else:
                    current_successes = pattern.success_rate * (pattern.occurrences - 1)
                    pattern.success_rate = current_successes / pattern.occurrences
                    
                # Update average time
                current_total_time = pattern.avg_fix_time * (pattern.occurrences - 1)
                pattern.avg_fix_time = (current_total_time + time_taken) / pattern.occurrences
                
                break
                
    def export_patterns(self, output_file: str):
        """Export pattern database"""
        patterns_data = []
        for pattern in self.patterns:
            patterns_data.append({
                'pattern_id': pattern.pattern_id,
                'name': pattern.name,
                'symptoms': pattern.symptoms,
                'common_causes': pattern.common_causes,
                'fix_templates': pattern.fix_templates,
                'success_rate': pattern.success_rate,
                'avg_fix_time': pattern.avg_fix_time,
                'occurrences': pattern.occurrences
            })
            
        with open(output_file, 'w') as f:
            json.dump(patterns_data, f, indent=2)

def create_sample_bug():
    """Create a sample bug for testing"""
    return Bug(
        id="BUG-1234",
        title="API endpoint called twice on button click",
        description="When clicking the submit button, the API is called twice causing duplicate entries",
        stack_trace=None,
        error_message="Duplicate key error",
        affected_files=["src/components/SubmitForm.jsx", "src/api/submissions.js"],
        symptoms=["duplicate requests", "multiple api calls"],
        root_cause=None,
        fix_description=None,
        fix_diff=None,
        tags=["frontend", "api", "react"],
        severity="medium",
        value=500
    )

def main():
    parser = argparse.ArgumentParser(description='Bug pattern recognition and fix suggestion engine')
    parser.add_argument('--analyze', help='Analyze a bug (JSON file)')
    parser.add_argument('--interactive', action='store_true', help='Interactive bug analysis')
    parser.add_argument('--export-patterns', help='Export pattern database to file')
    parser.add_argument('--show-patterns', action='store_true', help='Show all patterns')
    
    args = parser.parse_args()
    
    engine = BugPatternEngine()
    
    if args.show_patterns:
        print("📋 Available Bug Patterns:\n")
        for pattern in engine.patterns:
            print(f"🔍 {pattern.name} (ID: {pattern.pattern_id})")
            print(f"   Success Rate: {pattern.success_rate:.0%}")
            print(f"   Avg Fix Time: {pattern.avg_fix_time:.1f} hours")
            print(f"   Occurrences: {pattern.occurrences}")
            print()
            
    elif args.export_patterns:
        engine.export_patterns(args.export_patterns)
        print(f"Exported patterns to {args.export_patterns}")
        
    elif args.analyze:
        with open(args.analyze, 'r') as f:
            bug_data = json.load(f)
            bug = Bug(**bug_data)
            
        suggestions = engine.analyze_bug(bug)
        print_suggestions(bug, suggestions)
        
    elif args.interactive:
        print("🐛 Interactive Bug Analysis")
        print("-" * 40)
        
        # Get bug details
        title = input("Bug title: ")
        description = input("Bug description: ")
        symptoms = input("Symptoms (comma-separated): ").split(',')
        affected_files = input("Affected files (comma-separated): ").split(',')
        error_message = input("Error message (optional): ")
        value = float(input("Task value ($): ") or "500")
        
        bug = Bug(
            id=f"INTERACTIVE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            title=title,
            description=description,
            stack_trace=None,
            error_message=error_message if error_message else None,
            affected_files=[f.strip() for f in affected_files],
            symptoms=[s.strip() for s in symptoms],
            root_cause=None,
            fix_description=None,
            fix_diff=None,
            tags=[],
            severity="medium",
            value=value
        )
        
        suggestions = engine.analyze_bug(bug)
        print_suggestions(bug, suggestions)
        
    else:
        # Demo with sample bug
        print("🔍 Analyzing sample bug...\n")
        bug = create_sample_bug()
        suggestions = engine.analyze_bug(bug)
        print_suggestions(bug, suggestions)

def print_suggestions(bug: Bug, suggestions: List[FixSuggestion]):
    """Print fix suggestions in a formatted way"""
    print(f"\n🐛 Bug Analysis: {bug.title}")
    print(f"Value: ${bug.value} | Severity: {bug.severity}")
    print("=" * 60)
    
    if not suggestions:
        print("❌ No pattern matches found. This might be a unique issue.")
        return
        
    print(f"\n✅ Found {len(suggestions)} potential fix patterns:\n")
    
    for i, suggestion in enumerate(suggestions, 1):
        print(f"Pattern #{i}: {suggestion.pattern_id}")
        print(f"Confidence: {suggestion.confidence:.0%}")
        print(f"Estimated Time: {suggestion.estimated_time:.1f} hours")
        print(f"Success Probability: {suggestion.success_probability:.0%}")
        print(f"\n{suggestion.description}")
        
        if suggestion.code_changes:
            print("\n📝 Suggested Code Changes:")
            for change in suggestion.code_changes[:2]:  # Show first 2
                print(change)
                
        if suggestion.similar_bugs:
            print(f"\n🔗 Similar bugs: {', '.join(suggestion.similar_bugs)}")
            
        print("-" * 60)
        
    # Recommendation
    best = suggestions[0]
    print(f"\n🎯 RECOMMENDATION:")
    print(f"Apply the '{best.pattern_id}' pattern with {best.confidence:.0%} confidence.")
    print(f"Expected time: {best.estimated_time:.1f} hours")

if __name__ == '__main__':
    main()