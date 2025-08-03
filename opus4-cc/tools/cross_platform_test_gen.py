#!/usr/bin/env python3
"""
Cross-Platform Test Generator - Generate E2E tests for web, iOS, Android, and desktop
Unified test specification that generates platform-specific implementations
"""

import os
import json
import argparse
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

class Platform(Enum):
    WEB = "web"
    IOS = "ios"
    ANDROID = "android"
    DESKTOP = "desktop"

@dataclass
class TestStep:
    action: str
    target: str
    value: Optional[str] = None
    assertions: Optional[List[Dict[str, Any]]] = None

@dataclass
class TestCase:
    name: str
    description: str
    platforms: List[Platform]
    steps: List[TestStep]
    setup: Optional[List[TestStep]] = None
    teardown: Optional[List[TestStep]] = None

class TestGenerator:
    def __init__(self):
        self.test_cases = []
        
    def add_test_case(self, test_case: TestCase):
        """Add a test case to the generator"""
        self.test_cases.append(test_case)
        
    def generate_for_platform(self, platform: Platform) -> str:
        """Generate tests for a specific platform"""
        generators = {
            Platform.WEB: self._generate_web_tests,
            Platform.IOS: self._generate_ios_tests,
            Platform.ANDROID: self._generate_android_tests,
            Platform.DESKTOP: self._generate_desktop_tests,
        }
        
        return generators[platform]()
        
    def _generate_web_tests(self) -> str:
        """Generate Playwright tests for web"""
        tests = []
        tests.append("import { test, expect } from '@playwright/test';")
        tests.append("")
        
        for tc in self.test_cases:
            if Platform.WEB not in tc.platforms:
                continue
                
            tests.append(f"test('{tc.name}', async ({{ page }}) => {{")
            tests.append(f"  // {tc.description}")
            
            # Setup
            if tc.setup:
                tests.append("  // Setup")
                for step in tc.setup:
                    tests.append(f"  {self._web_step_to_code(step)}")
                    
            # Test steps
            tests.append("  // Test steps")
            for step in tc.steps:
                tests.append(f"  {self._web_step_to_code(step)}")
                
            # Teardown
            if tc.teardown:
                tests.append("  // Teardown")
                for step in tc.teardown:
                    tests.append(f"  {self._web_step_to_code(step)}")
                    
            tests.append("});")
            tests.append("")
            
        return "\n".join(tests)
        
    def _web_step_to_code(self, step: TestStep) -> str:
        """Convert a test step to Playwright code"""
        if step.action == "navigate":
            return f"await page.goto('{step.target}');"
        elif step.action == "click":
            return f"await page.click('{step.target}');"
        elif step.action == "fill":
            return f"await page.fill('{step.target}', '{step.value}');"
        elif step.action == "wait":
            return f"await page.waitForSelector('{step.target}');"
        elif step.action == "assert_visible":
            return f"await expect(page.locator('{step.target}')).toBeVisible();"
        elif step.action == "assert_text":
            return f"await expect(page.locator('{step.target}')).toHaveText('{step.value}');"
        elif step.action == "screenshot":
            return f"await page.screenshot({{ path: '{step.value}' }});"
        else:
            return f"// TODO: {step.action} on {step.target}"
            
    def _generate_ios_tests(self) -> str:
        """Generate XCUITest for iOS"""
        tests = []
        tests.append("import XCTest")
        tests.append("")
        tests.append("class E2ETests: XCTestCase {")
        
        for tc in self.test_cases:
            if Platform.IOS not in tc.platforms:
                continue
                
            tests.append(f"    func test{tc.name.replace(' ', '')}() {{")
            tests.append(f"        // {tc.description}")
            tests.append("        let app = XCUIApplication()")
            tests.append("        app.launch()")
            
            # Setup
            if tc.setup:
                tests.append("        // Setup")
                for step in tc.setup:
                    tests.append(f"        {self._ios_step_to_code(step)}")
                    
            # Test steps
            tests.append("        // Test steps")
            for step in tc.steps:
                tests.append(f"        {self._ios_step_to_code(step)}")
                
            # Teardown
            if tc.teardown:
                tests.append("        // Teardown")
                for step in tc.teardown:
                    tests.append(f"        {self._ios_step_to_code(step)}")
                    
            tests.append("    }")
            tests.append("")
            
        tests.append("}")
        return "\n".join(tests)
        
    def _ios_step_to_code(self, step: TestStep) -> str:
        """Convert a test step to XCUITest code"""
        if step.action == "tap":
            return f'app.buttons["{step.target}"].tap()'
        elif step.action == "type":
            return f'app.textFields["{step.target}"].typeText("{step.value}")'
        elif step.action == "swipe":
            return f'app.swipe{step.value.capitalize()}()'
        elif step.action == "wait":
            return f'let exists = app.staticTexts["{step.target}"].waitForExistence(timeout: 5)'
        elif step.action == "assert_exists":
            return f'XCTAssertTrue(app.staticTexts["{step.target}"].exists)'
        else:
            return f"// TODO: {step.action} on {step.target}"
            
    def _generate_android_tests(self) -> str:
        """Generate Espresso tests for Android"""
        tests = []
        tests.append("import androidx.test.espresso.Espresso.*")
        tests.append("import androidx.test.espresso.action.ViewActions.*")
        tests.append("import androidx.test.espresso.assertion.ViewAssertions.*")
        tests.append("import androidx.test.espresso.matcher.ViewMatchers.*")
        tests.append("import androidx.test.ext.junit.rules.ActivityScenarioRule")
        tests.append("import androidx.test.ext.junit.runners.AndroidJUnit4")
        tests.append("import org.junit.Rule")
        tests.append("import org.junit.Test")
        tests.append("import org.junit.runner.RunWith")
        tests.append("")
        tests.append("@RunWith(AndroidJUnit4::class)")
        tests.append("class E2ETests {")
        tests.append("    @get:Rule")
        tests.append("    val activityRule = ActivityScenarioRule(MainActivity::class.java)")
        tests.append("")
        
        for tc in self.test_cases:
            if Platform.ANDROID not in tc.platforms:
                continue
                
            tests.append(f"    @Test")
            tests.append(f"    fun test{tc.name.replace(' ', '')}() {{")
            tests.append(f"        // {tc.description}")
            
            # Setup
            if tc.setup:
                tests.append("        // Setup")
                for step in tc.setup:
                    tests.append(f"        {self._android_step_to_code(step)}")
                    
            # Test steps
            tests.append("        // Test steps")
            for step in tc.steps:
                tests.append(f"        {self._android_step_to_code(step)}")
                
            # Teardown
            if tc.teardown:
                tests.append("        // Teardown")
                for step in tc.teardown:
                    tests.append(f"        {self._android_step_to_code(step)}")
                    
            tests.append("    }")
            tests.append("")
            
        tests.append("}")
        return "\n".join(tests)
        
    def _android_step_to_code(self, step: TestStep) -> str:
        """Convert a test step to Espresso code"""
        if step.action == "click":
            return f'onView(withId(R.id.{step.target})).perform(click())'
        elif step.action == "type":
            return f'onView(withId(R.id.{step.target})).perform(typeText("{step.value}"))'
        elif step.action == "assert_displayed":
            return f'onView(withId(R.id.{step.target})).check(matches(isDisplayed()))'
        elif step.action == "assert_text":
            return f'onView(withId(R.id.{step.target})).check(matches(withText("{step.value}")))'
        else:
            return f"// TODO: {step.action} on {step.target}"
            
    def _generate_desktop_tests(self) -> str:
        """Generate tests for desktop (Electron example)"""
        tests = []
        tests.append("const { _electron: electron } = require('playwright');")
        tests.append("const { test, expect } = require('@playwright/test');")
        tests.append("")
        
        for tc in self.test_cases:
            if Platform.DESKTOP not in tc.platforms:
                continue
                
            tests.append(f"test('{tc.name}', async () => {{")
            tests.append(f"  // {tc.description}")
            tests.append("  const app = await electron.launch({ args: ['main.js'] });")
            tests.append("  const window = await app.firstWindow();")
            
            # Setup
            if tc.setup:
                tests.append("  // Setup")
                for step in tc.setup:
                    tests.append(f"  {self._desktop_step_to_code(step)}")
                    
            # Test steps
            tests.append("  // Test steps")
            for step in tc.steps:
                tests.append(f"  {self._desktop_step_to_code(step)}")
                
            # Teardown
            if tc.teardown:
                tests.append("  // Teardown")
                for step in tc.teardown:
                    tests.append(f"  {self._desktop_step_to_code(step)}")
                    
            tests.append("  await app.close();")
            tests.append("});")
            tests.append("")
            
        return "\n".join(tests)
        
    def _desktop_step_to_code(self, step: TestStep) -> str:
        """Convert a test step to desktop test code"""
        if step.action == "click":
            return f"await window.click('{step.target}');"
        elif step.action == "fill":
            return f"await window.fill('{step.target}', '{step.value}');"
        elif step.action == "assert_visible":
            return f"await expect(window.locator('{step.target}')).toBeVisible();"
        else:
            return f"// TODO: {step.action} on {step.target}"

class TestSpecParser:
    """Parse unified test specifications"""
    
    @staticmethod
    def parse_yaml(yaml_content: str) -> List[TestCase]:
        """Parse YAML test specification"""
        import yaml
        data = yaml.safe_load(yaml_content)
        test_cases = []
        
        for test_data in data.get('tests', []):
            steps = []
            for step_data in test_data.get('steps', []):
                step = TestStep(
                    action=step_data['action'],
                    target=step_data['target'],
                    value=step_data.get('value'),
                    assertions=step_data.get('assertions')
                )
                steps.append(step)
                
            test_case = TestCase(
                name=test_data['name'],
                description=test_data.get('description', ''),
                platforms=[Platform(p) for p in test_data.get('platforms', ['web'])],
                steps=steps,
                setup=[TestStep(**s) for s in test_data.get('setup', [])],
                teardown=[TestStep(**s) for s in test_data.get('teardown', [])]
            )
            test_cases.append(test_case)
            
        return test_cases

def create_sample_spec():
    """Create a sample test specification"""
    sample = {
        'tests': [
            {
                'name': 'User Login Flow',
                'description': 'Test user authentication across all platforms',
                'platforms': ['web', 'ios', 'android', 'desktop'],
                'setup': [
                    {'action': 'navigate', 'target': '/login'}
                ],
                'steps': [
                    {'action': 'fill', 'target': '#email', 'value': 'test@example.com'},
                    {'action': 'fill', 'target': '#password', 'value': 'password123'},
                    {'action': 'click', 'target': '#login-button'},
                    {'action': 'wait', 'target': '.dashboard'},
                    {'action': 'assert_visible', 'target': '.user-profile'},
                    {'action': 'assert_text', 'target': '.welcome-message', 'value': 'Welcome back!'}
                ]
            },
            {
                'name': 'Video Playback Feature',
                'description': 'Test in-app video playback functionality',
                'platforms': ['web', 'ios', 'android'],
                'steps': [
                    {'action': 'click', 'target': '.video-thumbnail'},
                    {'action': 'wait', 'target': '.video-player'},
                    {'action': 'click', 'target': '.play-button'},
                    {'action': 'wait', 'target': '.video-playing'},
                    {'action': 'assert_visible', 'target': '.video-controls'},
                    {'action': 'screenshot', 'target': 'player', 'value': 'video-playing.png'}
                ]
            }
        ]
    }
    
    with open('sample_test_spec.yaml', 'w') as f:
        import yaml
        yaml.dump(sample, f, default_flow_style=False)
        
    return sample

def main():
    parser = argparse.ArgumentParser(description='Generate cross-platform E2E tests')
    parser.add_argument('--spec', help='Test specification file (YAML)')
    parser.add_argument('--platform', choices=['web', 'ios', 'android', 'desktop', 'all'], 
                       default='all', help='Target platform')
    parser.add_argument('--output-dir', default='generated_tests', help='Output directory')
    parser.add_argument('--create-sample', action='store_true', help='Create sample test spec')
    
    args = parser.parse_args()
    
    if args.create_sample:
        create_sample_spec()
        print("Created sample_test_spec.yaml")
        return
        
    if not args.spec:
        print("Creating example test cases...")
        # Create example test cases
        generator = TestGenerator()
        
        # Example test case
        login_test = TestCase(
            name="User Login Flow",
            description="Test user authentication across platforms",
            platforms=[Platform.WEB, Platform.IOS, Platform.ANDROID, Platform.DESKTOP],
            steps=[
                TestStep("fill", "#email", "test@example.com"),
                TestStep("fill", "#password", "password123"),
                TestStep("click", "#login-button"),
                TestStep("wait", ".dashboard"),
                TestStep("assert_visible", ".user-profile")
            ]
        )
        
        generator.add_test_case(login_test)
        
    else:
        # Parse specification file
        generator = TestGenerator()
        with open(args.spec, 'r') as f:
            if args.spec.endswith('.yaml') or args.spec.endswith('.yml'):
                test_cases = TestSpecParser.parse_yaml(f.read())
                for tc in test_cases:
                    generator.add_test_case(tc)
                    
    # Generate tests
    os.makedirs(args.output_dir, exist_ok=True)
    
    platforms = [Platform.WEB, Platform.IOS, Platform.ANDROID, Platform.DESKTOP] if args.platform == 'all' else [Platform(args.platform)]
    
    file_extensions = {
        Platform.WEB: 'spec.ts',
        Platform.IOS: 'swift',
        Platform.ANDROID: 'kt',
        Platform.DESKTOP: 'spec.js'
    }
    
    for platform in platforms:
        code = generator.generate_for_platform(platform)
        filename = f"{args.output_dir}/e2e_tests.{file_extensions[platform]}"
        
        with open(filename, 'w') as f:
            f.write(code)
            
        print(f"Generated {platform.value} tests: {filename}")
        
    # Generate test runner configuration
    if Platform.WEB in platforms:
        playwright_config = """import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './',
  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    { name: 'firefox', use: { browserName: 'firefox' } },
    { name: 'webkit', use: { browserName: 'webkit' } },
  ],
});"""
        
        with open(f"{args.output_dir}/playwright.config.ts", 'w') as f:
            f.write(playwright_config)
            
    print(f"\n✅ Test generation complete! Generated tests in {args.output_dir}/")

if __name__ == '__main__':
    main()