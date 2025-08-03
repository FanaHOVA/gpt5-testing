#!/usr/bin/env python3
"""
Integration Test Runner Tool

Provides a sandboxed environment for running integration tests with proper
isolation, resource management, and comprehensive reporting.
"""

import os
import sys
import time
import json
import tempfile
import subprocess
import shutil
import signal
import threading
import queue
import psutil
import docker
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import yaml
import logging
from contextlib import contextmanager
import venv
import requests


@dataclass
class TestResult:
    """Result of a single test execution"""
    test_name: str
    status: str  # 'passed', 'failed', 'skipped', 'error'
    duration: float  # seconds
    output: str
    error_output: str
    exit_code: int
    memory_peak: int  # bytes
    cpu_time: float  # seconds
    timestamp: datetime = field(default_factory=datetime.now)
    
    
@dataclass
class TestEnvironment:
    """Configuration for test environment"""
    working_dir: Path
    temp_dir: Path
    python_version: str = "3.9"
    dependencies: List[str] = field(default_factory=list)
    environment_vars: Dict[str, str] = field(default_factory=dict)
    services: List[Dict[str, Any]] = field(default_factory=list)  # Docker services
    cleanup_on_exit: bool = True
    timeout: int = 300  # 5 minutes default
    memory_limit: int = 1024 * 1024 * 1024  # 1GB default
    cpu_limit: float = 1.0  # 1 CPU core default
    

@dataclass
class TestSuite:
    """Collection of tests to run"""
    name: str
    tests: List[Dict[str, Any]]
    setup_commands: List[str] = field(default_factory=list)
    teardown_commands: List[str] = field(default_factory=list)
    environment: TestEnvironment = None
    

class ProcessMonitor:
    """Monitors process resource usage"""
    
    def __init__(self, pid: int):
        self.pid = pid
        self.process = None
        self.monitoring = False
        self.stats = {
            'memory_peak': 0,
            'cpu_percent_samples': [],
            'io_counters': None
        }
        self._lock = threading.Lock()
        
    def start(self):
        """Start monitoring the process"""
        try:
            self.process = psutil.Process(self.pid)
            self.monitoring = True
            self._monitor_thread = threading.Thread(target=self._monitor_loop)
            self._monitor_thread.daemon = True
            self._monitor_thread.start()
        except psutil.NoSuchProcess:
            pass
            
    def stop(self):
        """Stop monitoring"""
        self.monitoring = False
        if hasattr(self, '_monitor_thread'):
            self._monitor_thread.join(timeout=1)
            
    def _monitor_loop(self):
        """Monitor loop running in separate thread"""
        while self.monitoring:
            try:
                if self.process.is_running():
                    with self._lock:
                        # Memory usage
                        memory_info = self.process.memory_info()
                        self.stats['memory_peak'] = max(
                            self.stats['memory_peak'],
                            memory_info.rss
                        )
                        
                        # CPU usage
                        cpu_percent = self.process.cpu_percent(interval=0.1)
                        self.stats['cpu_percent_samples'].append(cpu_percent)
                        
                        # IO counters
                        try:
                            self.stats['io_counters'] = self.process.io_counters()
                        except:
                            pass
                else:
                    self.monitoring = False
            except psutil.NoSuchProcess:
                self.monitoring = False
            except Exception:
                pass
                
            time.sleep(0.5)
            
    def get_stats(self) -> Dict[str, Any]:
        """Get collected statistics"""
        with self._lock:
            cpu_samples = self.stats['cpu_percent_samples']
            avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
            
            return {
                'memory_peak': self.stats['memory_peak'],
                'cpu_average': avg_cpu,
                'cpu_time': sum(cpu_samples) * 0.5 / 100,  # Rough estimate
                'io_counters': self.stats['io_counters']
            }
            

class DockerServiceManager:
    """Manages Docker services for tests"""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
            self.containers = []
            self.networks = []
        except:
            self.client = None
            
    @property
    def available(self) -> bool:
        """Check if Docker is available"""
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except:
            return False
            
    def start_service(self, service_config: Dict[str, Any]) -> Optional[str]:
        """Start a Docker service"""
        if not self.available:
            return None
            
        try:
            # Extract configuration
            image = service_config.get('image')
            name = service_config.get('name', f"test-service-{int(time.time())}")
            environment = service_config.get('environment', {})
            ports = service_config.get('ports', {})
            volumes = service_config.get('volumes', {})
            command = service_config.get('command')
            
            # Pull image if needed
            try:
                self.client.images.get(image)
            except docker.errors.ImageNotFound:
                self.client.images.pull(image)
                
            # Create and start container
            container = self.client.containers.run(
                image=image,
                name=name,
                environment=environment,
                ports=ports,
                volumes=volumes,
                command=command,
                detach=True,
                remove=False
            )
            
            self.containers.append(container)
            
            # Wait for service to be ready
            if 'healthcheck' in service_config:
                self._wait_for_health(container, service_config['healthcheck'])
            elif 'wait_for_port' in service_config:
                self._wait_for_port(service_config['wait_for_port'])
                
            return container.id
            
        except Exception as e:
            logging.error(f"Failed to start service: {e}")
            return None
            
    def _wait_for_health(self, container, healthcheck_config: Dict[str, Any]):
        """Wait for container health check"""
        timeout = healthcheck_config.get('timeout', 30)
        interval = healthcheck_config.get('interval', 1)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            container.reload()
            
            health = container.attrs.get('State', {}).get('Health', {})
            if health.get('Status') == 'healthy':
                return
                
            time.sleep(interval)
            
        raise TimeoutError(f"Container {container.name} failed health check")
        
    def _wait_for_port(self, port: int, host: str = 'localhost', timeout: int = 30):
        """Wait for a port to be available"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://{host}:{port}", timeout=1)
                if response.status_code < 500:
                    return
            except:
                pass
            time.sleep(1)
            
        raise TimeoutError(f"Port {port} not available after {timeout} seconds")
        
    def cleanup(self):
        """Clean up all containers and networks"""
        for container in self.containers:
            try:
                container.stop(timeout=5)
                container.remove()
            except:
                pass
                
        for network in self.networks:
            try:
                network.remove()
            except:
                pass
                

class IntegrationTestRunner:
    """Main test runner with sandboxing capabilities"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.docker_manager = DockerServiceManager()
        self.results: List[TestResult] = []
        self.environments: List[TestEnvironment] = []
        
    def create_test_environment(self, config: Dict[str, Any]) -> TestEnvironment:
        """Create an isolated test environment"""
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="test_env_"))
        
        # Create working directory
        working_dir = temp_dir / "workspace"
        working_dir.mkdir()
        
        # Copy project files
        self._copy_project_files(working_dir, config.get('include_patterns', ['**/*']))
        
        # Create environment
        env = TestEnvironment(
            working_dir=working_dir,
            temp_dir=temp_dir,
            python_version=config.get('python_version', '3.9'),
            dependencies=config.get('dependencies', []),
            environment_vars=config.get('environment', {}),
            services=config.get('services', []),
            cleanup_on_exit=config.get('cleanup', True),
            timeout=config.get('timeout', 300),
            memory_limit=config.get('memory_limit', 1024 * 1024 * 1024),
            cpu_limit=config.get('cpu_limit', 1.0)
        )
        
        self.environments.append(env)
        return env
        
    def _copy_project_files(self, destination: Path, patterns: List[str]):
        """Copy project files to test environment"""
        # Default excludes
        excludes = {
            '__pycache__', '.git', '.pytest_cache', '.tox',
            'venv', '.venv', 'env', '.env', 'node_modules',
            '*.pyc', '*.pyo', '.DS_Store', 'Thumbs.db'
        }
        
        for pattern in patterns:
            for source_file in self.project_root.glob(pattern):
                if source_file.is_file():
                    # Check excludes
                    if any(exclude in str(source_file) for exclude in excludes):
                        continue
                        
                    # Calculate relative path
                    rel_path = source_file.relative_to(self.project_root)
                    dest_file = destination / rel_path
                    
                    # Create parent directories
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file
                    shutil.copy2(source_file, dest_file)
                    
    @contextmanager
    def _virtual_environment(self, env: TestEnvironment):
        """Create and activate a virtual environment"""
        venv_path = env.temp_dir / "venv"
        
        # Create virtual environment
        venv.create(venv_path, with_pip=True)
        
        # Get paths
        if sys.platform == "win32":
            python_path = venv_path / "Scripts" / "python.exe"
            pip_path = venv_path / "Scripts" / "pip.exe"
        else:
            python_path = venv_path / "bin" / "python"
            pip_path = venv_path / "bin" / "pip"
            
        # Install dependencies
        if env.dependencies:
            deps_file = env.temp_dir / "requirements.txt"
            with open(deps_file, 'w') as f:
                f.write('\n'.join(env.dependencies))
                
            subprocess.run(
                [str(pip_path), "install", "-r", str(deps_file)],
                check=True,
                capture_output=True
            )
            
        yield str(python_path)
        
    def _start_services(self, services: List[Dict[str, Any]]) -> List[str]:
        """Start required services"""
        service_ids = []
        
        for service in services:
            service_id = self.docker_manager.start_service(service)
            if service_id:
                service_ids.append(service_id)
            else:
                logging.warning(f"Failed to start service: {service.get('name', 'unknown')}")
                
        return service_ids
        
    def run_test(self, test_config: Dict[str, Any], env: TestEnvironment) -> TestResult:
        """Run a single test in isolation"""
        test_name = test_config.get('name', 'unnamed_test')
        command = test_config.get('command')
        
        if not command:
            return TestResult(
                test_name=test_name,
                status='error',
                duration=0,
                output='',
                error_output='No command specified',
                exit_code=-1,
                memory_peak=0,
                cpu_time=0
            )
            
        # Prepare environment variables
        test_env = os.environ.copy()
        test_env.update(env.environment_vars)
        test_env.update(test_config.get('environment', {}))
        
        # Start services if needed
        service_ids = []
        if env.services:
            service_ids = self._start_services(env.services)
            
        try:
            with self._virtual_environment(env) as python_path:
                # Prepare command
                if isinstance(command, str):
                    command = command.replace('python', python_path)
                    full_command = command
                else:
                    full_command = [python_path if c == 'python' else c for c in command]
                    
                # Run test
                start_time = time.time()
                
                process = subprocess.Popen(
                    full_command,
                    shell=isinstance(full_command, str),
                    cwd=str(env.working_dir),
                    env=test_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Monitor process
                monitor = ProcessMonitor(process.pid)
                monitor.start()
                
                try:
                    # Wait for completion with timeout
                    stdout, stderr = process.communicate(timeout=env.timeout)
                    exit_code = process.returncode
                    
                except subprocess.TimeoutExpired:
                    # Kill process on timeout
                    process.kill()
                    stdout, stderr = process.communicate()
                    exit_code = -1
                    stderr = f"Test timed out after {env.timeout} seconds\n{stderr}"
                    
                finally:
                    monitor.stop()
                    
                duration = time.time() - start_time
                stats = monitor.get_stats()
                
                # Determine status
                if exit_code == 0:
                    status = 'passed'
                elif exit_code == -1:
                    status = 'error'
                else:
                    status = 'failed'
                    
                return TestResult(
                    test_name=test_name,
                    status=status,
                    duration=duration,
                    output=stdout,
                    error_output=stderr,
                    exit_code=exit_code,
                    memory_peak=stats['memory_peak'],
                    cpu_time=stats['cpu_time']
                )
                
        except Exception as e:
            return TestResult(
                test_name=test_name,
                status='error',
                duration=0,
                output='',
                error_output=str(e),
                exit_code=-1,
                memory_peak=0,
                cpu_time=0
            )
            
        finally:
            # Cleanup services
            if service_ids and self.docker_manager.available:
                for container in self.docker_manager.containers:
                    if container.id in service_ids:
                        try:
                            container.stop(timeout=5)
                            container.remove()
                        except:
                            pass
                            
    def run_suite(self, suite: TestSuite) -> List[TestResult]:
        """Run a complete test suite"""
        results = []
        
        # Run setup commands
        if suite.setup_commands:
            for cmd in suite.setup_commands:
                self._run_command(cmd, suite.environment)
                
        # Run each test
        for test_config in suite.tests:
            result = self.run_test(test_config, suite.environment)
            results.append(result)
            self.results.append(result)
            
            # Stop on critical failure if configured
            if test_config.get('stop_on_failure') and result.status == 'failed':
                break
                
        # Run teardown commands
        if suite.teardown_commands:
            for cmd in suite.teardown_commands:
                self._run_command(cmd, suite.environment)
                
        return results
        
    def _run_command(self, command: str, env: TestEnvironment):
        """Run a setup/teardown command"""
        subprocess.run(
            command,
            shell=True,
            cwd=str(env.working_dir),
            env=os.environ.copy().update(env.environment_vars or {}),
            capture_output=True
        )
        
    def cleanup(self):
        """Clean up all test environments"""
        # Clean up Docker services
        self.docker_manager.cleanup()
        
        # Clean up temporary directories
        for env in self.environments:
            if env.cleanup_on_exit and env.temp_dir.exists():
                shutil.rmtree(env.temp_dir)
                
    def generate_report(self) -> Dict[str, Any]:
        """Generate test execution report"""
        total_tests = len(self.results)
        passed = len([r for r in self.results if r.status == 'passed'])
        failed = len([r for r in self.results if r.status == 'failed'])
        skipped = len([r for r in self.results if r.status == 'skipped'])
        errors = len([r for r in self.results if r.status == 'error'])
        
        total_duration = sum(r.duration for r in self.results)
        total_memory = sum(r.memory_peak for r in self.results)
        total_cpu_time = sum(r.cpu_time for r in self.results)
        
        return {
            'summary': {
                'total': total_tests,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'errors': errors,
                'duration': total_duration,
                'memory_usage': total_memory,
                'cpu_time': total_cpu_time,
                'success_rate': (passed / total_tests * 100) if total_tests > 0 else 0
            },
            'results': [
                {
                    'name': r.test_name,
                    'status': r.status,
                    'duration': r.duration,
                    'memory_peak': r.memory_peak,
                    'cpu_time': r.cpu_time,
                    'output': r.output,
                    'error_output': r.error_output,
                    'exit_code': r.exit_code,
                    'timestamp': r.timestamp.isoformat()
                }
                for r in self.results
            ],
            'environment': {
                'docker_available': self.docker_manager.available,
                'project_root': str(self.project_root),
                'timestamp': datetime.now().isoformat()
            }
        }
        
    def format_report(self, report: Dict[str, Any], format: str = 'text') -> str:
        """Format report for output"""
        if format == 'json':
            return json.dumps(report, indent=2)
            
        # Text format
        lines = []
        lines.append("=" * 80)
        lines.append("INTEGRATION TEST REPORT")
        lines.append("=" * 80)
        
        summary = report['summary']
        lines.append(f"\nTotal Tests: {summary['total']}")
        lines.append(f"Passed: {summary['passed']} ({summary['success_rate']:.1f}%)")
        lines.append(f"Failed: {summary['failed']}")
        lines.append(f"Errors: {summary['errors']}")
        lines.append(f"Skipped: {summary['skipped']}")
        
        lines.append(f"\nTotal Duration: {summary['duration']:.2f}s")
        lines.append(f"Total CPU Time: {summary['cpu_time']:.2f}s")
        lines.append(f"Peak Memory: {summary['memory_usage'] / 1024 / 1024:.1f}MB")
        
        # Failed tests details
        failed_tests = [r for r in report['results'] if r['status'] in ['failed', 'error']]
        if failed_tests:
            lines.append("\n" + "-" * 60)
            lines.append("FAILED TESTS")
            lines.append("-" * 60)
            
            for test in failed_tests:
                lines.append(f"\n{test['name']} [{test['status'].upper()}]")
                lines.append(f"Duration: {test['duration']:.2f}s")
                lines.append(f"Exit Code: {test['exit_code']}")
                
                if test['error_output']:
                    lines.append("\nError Output:")
                    lines.append(test['error_output'][:500])
                    if len(test['error_output']) > 500:
                        lines.append("... (truncated)")
                        
        # All test results
        lines.append("\n" + "-" * 60)
        lines.append("ALL TEST RESULTS")
        lines.append("-" * 60)
        
        for test in report['results']:
            status_icon = {
                'passed': '✓',
                'failed': '✗',
                'error': '!',
                'skipped': '-'
            }.get(test['status'], '?')
            
            lines.append(f"{status_icon} {test['name']:<50} {test['duration']:>6.2f}s {test['memory_peak']/1024/1024:>6.1f}MB")
            
        return '\n'.join(lines)


def load_test_config(config_file: str) -> Dict[str, Any]:
    """Load test configuration from file"""
    config_path = Path(config_file)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
    with open(config_path, 'r') as f:
        if config_path.suffix in ['.yaml', '.yml']:
            return yaml.safe_load(f)
        elif config_path.suffix == '.json':
            return json.load(f)
        else:
            raise ValueError(f"Unsupported config format: {config_path.suffix}")
            

def main():
    """CLI interface for the integration test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Integration Test Runner - Run tests in isolated environments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration file example (test-config.yaml):

environment:
  python_version: "3.9"
  dependencies:
    - pytest>=6.0
    - requests
  environment:
    DATABASE_URL: "sqlite:///test.db"
  services:
    - name: test-postgres
      image: postgres:13
      environment:
        POSTGRES_PASSWORD: testpass
      ports:
        5432: 5432
      healthcheck:
        timeout: 30

suites:
  - name: API Tests
    tests:
      - name: test_endpoints
        command: pytest tests/test_api.py
      - name: test_integration
        command: python -m pytest tests/integration/

Examples:
  # Run tests from configuration file
  python integration_test_runner.py --config test-config.yaml
  
  # Run specific test command
  python integration_test_runner.py --command "pytest tests/"
  
  # Run with custom Python version
  python integration_test_runner.py --command "pytest" --python 3.8
  
  # Output JSON report
  python integration_test_runner.py --config test-config.yaml --json
        """
    )
    
    parser.add_argument('--config', help='Test configuration file (YAML or JSON)')
    parser.add_argument('--command', help='Single test command to run')
    parser.add_argument('--python', default='3.9', help='Python version to use')
    parser.add_argument('--timeout', type=int, default=300, help='Test timeout in seconds')
    parser.add_argument('--no-cleanup', action='store_true', help='Keep test environments after completion')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    parser.add_argument('--output', '-o', help='Write report to file')
    parser.add_argument('project_path', nargs='?', default='.', help='Project root directory')
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = IntegrationTestRunner(args.project_path)
    
    try:
        if args.config:
            # Load configuration
            config = load_test_config(args.config)
            
            # Create environment
            env_config = config.get('environment', {})
            env_config['cleanup'] = not args.no_cleanup
            env = runner.create_test_environment(env_config)
            
            # Run test suites
            for suite_config in config.get('suites', []):
                suite = TestSuite(
                    name=suite_config.get('name', 'default'),
                    tests=suite_config.get('tests', []),
                    setup_commands=suite_config.get('setup', []),
                    teardown_commands=suite_config.get('teardown', []),
                    environment=env
                )
                runner.run_suite(suite)
                
        elif args.command:
            # Run single command
            env = runner.create_test_environment({
                'python_version': args.python,
                'timeout': args.timeout,
                'cleanup': not args.no_cleanup
            })
            
            result = runner.run_test(
                {'name': 'cli_test', 'command': args.command},
                env
            )
            
        else:
            parser.error("Either --config or --command must be specified")
            
        # Generate report
        report = runner.generate_report()
        formatted_report = runner.format_report(report, 'json' if args.json else 'text')
        
        # Output report
        if args.output:
            with open(args.output, 'w') as f:
                f.write(formatted_report)
            print(f"Report written to: {args.output}")
        else:
            print(formatted_report)
            
        # Exit code based on results
        if report['summary']['failed'] > 0 or report['summary']['errors'] > 0:
            sys.exit(1)
            
    finally:
        # Cleanup
        runner.cleanup()


if __name__ == '__main__':
    main()