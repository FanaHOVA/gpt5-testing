#!/usr/bin/env python3
"""
Service Connectivity Checker Tool

Verifies service connectivity in different environments (local, Docker, Kubernetes)
and helps diagnose networking issues between services.
"""

import os
import sys
import time
import socket
import subprocess
import json
import yaml
import requests
import docker
import psutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import dns.resolver
import ipaddress
from urllib.parse import urlparse
import platform
import traceback


@dataclass
class ConnectivityResult:
    """Result of a connectivity check"""
    from_service: str
    to_service: str
    host: str
    port: int
    protocol: str  # 'tcp', 'http', 'https', 'udp'
    status: str  # 'success', 'failed', 'timeout', 'dns_error', 'refused'
    latency: Optional[float] = None  # milliseconds
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    additional_info: Dict[str, Any] = field(default_factory=dict)
    

@dataclass
class ServiceEndpoint:
    """Represents a service endpoint"""
    name: str
    host: str
    port: int
    protocol: str = 'tcp'
    environment: str = 'local'  # 'local', 'docker', 'kubernetes'
    health_check_path: Optional[str] = None  # For HTTP/HTTPS
    expected_status_codes: List[int] = field(default_factory=lambda: [200])
    timeout: int = 5
    

@dataclass
class NetworkDiagnostics:
    """Network diagnostics information"""
    dns_resolution: Dict[str, List[str]]
    routing_table: List[str]
    active_connections: List[Dict[str, Any]]
    docker_networks: List[Dict[str, Any]]
    firewall_rules: List[str]
    

class ConnectivityChecker:
    """Base connectivity checker"""
    
    def check(self, endpoint: ServiceEndpoint) -> ConnectivityResult:
        """Check connectivity to an endpoint"""
        raise NotImplementedError
        

class TCPConnectivityChecker(ConnectivityChecker):
    """TCP connectivity checker"""
    
    def check(self, endpoint: ServiceEndpoint) -> ConnectivityResult:
        """Check TCP connectivity"""
        start_time = time.time()
        
        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(endpoint.timeout)
            
            # Try to connect
            result = sock.connect_ex((endpoint.host, endpoint.port))
            sock.close()
            
            latency = (time.time() - start_time) * 1000  # Convert to ms
            
            if result == 0:
                return ConnectivityResult(
                    from_service='local',
                    to_service=endpoint.name,
                    host=endpoint.host,
                    port=endpoint.port,
                    protocol='tcp',
                    status='success',
                    latency=latency
                )
            else:
                error_msg = os.strerror(result) if result else "Connection failed"
                return ConnectivityResult(
                    from_service='local',
                    to_service=endpoint.name,
                    host=endpoint.host,
                    port=endpoint.port,
                    protocol='tcp',
                    status='refused',
                    error_message=error_msg
                )
                
        except socket.timeout:
            return ConnectivityResult(
                from_service='local',
                to_service=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                protocol='tcp',
                status='timeout',
                error_message=f"Connection timeout after {endpoint.timeout}s"
            )
        except socket.gaierror as e:
            return ConnectivityResult(
                from_service='local',
                to_service=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                protocol='tcp',
                status='dns_error',
                error_message=f"DNS resolution failed: {str(e)}"
            )
        except Exception as e:
            return ConnectivityResult(
                from_service='local',
                to_service=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                protocol='tcp',
                status='failed',
                error_message=str(e)
            )
            

class HTTPConnectivityChecker(ConnectivityChecker):
    """HTTP/HTTPS connectivity checker"""
    
    def check(self, endpoint: ServiceEndpoint) -> ConnectivityResult:
        """Check HTTP/HTTPS connectivity"""
        # Build URL
        scheme = endpoint.protocol
        if endpoint.health_check_path:
            url = f"{scheme}://{endpoint.host}:{endpoint.port}{endpoint.health_check_path}"
        else:
            url = f"{scheme}://{endpoint.host}:{endpoint.port}/"
            
        start_time = time.time()
        
        try:
            response = requests.get(
                url,
                timeout=endpoint.timeout,
                verify=False if scheme == 'https' else True,
                allow_redirects=False
            )
            
            latency = (time.time() - start_time) * 1000
            
            if response.status_code in endpoint.expected_status_codes:
                return ConnectivityResult(
                    from_service='local',
                    to_service=endpoint.name,
                    host=endpoint.host,
                    port=endpoint.port,
                    protocol=scheme,
                    status='success',
                    latency=latency,
                    additional_info={
                        'status_code': response.status_code,
                        'headers': dict(response.headers)
                    }
                )
            else:
                return ConnectivityResult(
                    from_service='local',
                    to_service=endpoint.name,
                    host=endpoint.host,
                    port=endpoint.port,
                    protocol=scheme,
                    status='failed',
                    error_message=f"Unexpected status code: {response.status_code}",
                    additional_info={
                        'status_code': response.status_code,
                        'body': response.text[:500]
                    }
                )
                
        except requests.exceptions.Timeout:
            return ConnectivityResult(
                from_service='local',
                to_service=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                protocol=scheme,
                status='timeout',
                error_message=f"Request timeout after {endpoint.timeout}s"
            )
        except requests.exceptions.ConnectionError as e:
            return ConnectivityResult(
                from_service='local',
                to_service=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                protocol=scheme,
                status='refused',
                error_message=f"Connection error: {str(e)}"
            )
        except Exception as e:
            return ConnectivityResult(
                from_service='local',
                to_service=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                protocol=scheme,
                status='failed',
                error_message=str(e)
            )
            

class ServiceConnectivityChecker:
    """Main service connectivity checker"""
    
    def __init__(self):
        self.checkers = {
            'tcp': TCPConnectivityChecker(),
            'http': HTTPConnectivityChecker(),
            'https': HTTPConnectivityChecker(),
        }
        try:
            self.docker_client = docker.from_env()
        except:
            self.docker_client = None
            
    def check_connectivity(self, from_service: str, to_service: str,
                         host: str, port: int,
                         protocol: str = 'tcp',
                         environment: str = 'local',
                         **kwargs) -> ConnectivityResult:
        """Check connectivity from one service to another"""
        endpoint = ServiceEndpoint(
            name=to_service,
            host=host,
            port=port,
            protocol=protocol,
            environment=environment,
            **kwargs
        )
        
        if environment == 'docker':
            return self._check_docker_connectivity(from_service, endpoint)
        elif environment == 'kubernetes':
            return self._check_kubernetes_connectivity(from_service, endpoint)
        else:
            # Local connectivity check
            checker = self.checkers.get(protocol)
            if not checker:
                return ConnectivityResult(
                    from_service=from_service,
                    to_service=to_service,
                    host=host,
                    port=port,
                    protocol=protocol,
                    status='failed',
                    error_message=f"Unsupported protocol: {protocol}"
                )
                
            result = checker.check(endpoint)
            result.from_service = from_service
            return result
            
    def _check_docker_connectivity(self, from_service: str, endpoint: ServiceEndpoint) -> ConnectivityResult:
        """Check connectivity from within a Docker container"""
        if not self.docker_client:
            return ConnectivityResult(
                from_service=from_service,
                to_service=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                protocol=endpoint.protocol,
                status='failed',
                error_message="Docker client not available"
            )
            
        try:
            # Find the source container
            containers = self.docker_client.containers.list()
            source_container = None
            
            for container in containers:
                if from_service in container.name or from_service == container.id[:12]:
                    source_container = container
                    break
                    
            if not source_container:
                return ConnectivityResult(
                    from_service=from_service,
                    to_service=endpoint.name,
                    host=endpoint.host,
                    port=endpoint.port,
                    protocol=endpoint.protocol,
                    status='failed',
                    error_message=f"Source container '{from_service}' not found"
                )
                
            # Execute connectivity check from within container
            if endpoint.protocol == 'tcp':
                # Use nc (netcat) for TCP check
                cmd = f"nc -zv -w{endpoint.timeout} {endpoint.host} {endpoint.port}"
                
                try:
                    result = source_container.exec_run(cmd, stderr=True, stdout=True)
                    
                    if result.exit_code == 0:
                        return ConnectivityResult(
                            from_service=from_service,
                            to_service=endpoint.name,
                            host=endpoint.host,
                            port=endpoint.port,
                            protocol=endpoint.protocol,
                            status='success'
                        )
                    else:
                        return ConnectivityResult(
                            from_service=from_service,
                            to_service=endpoint.name,
                            host=endpoint.host,
                            port=endpoint.port,
                            protocol=endpoint.protocol,
                            status='refused',
                            error_message=result.output.decode('utf-8')
                        )
                except docker.errors.APIError as e:
                    # Try alternative method with Python
                    python_cmd = f"""python -c "
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout({endpoint.timeout})
result = sock.connect_ex(('{endpoint.host}', {endpoint.port}))
sock.close()
exit(0 if result == 0 else 1)
"
"""
                    result = source_container.exec_run(python_cmd)
                    
                    if result.exit_code == 0:
                        return ConnectivityResult(
                            from_service=from_service,
                            to_service=endpoint.name,
                            host=endpoint.host,
                            port=endpoint.port,
                            protocol=endpoint.protocol,
                            status='success'
                        )
                    else:
                        return ConnectivityResult(
                            from_service=from_service,
                            to_service=endpoint.name,
                            host=endpoint.host,
                            port=endpoint.port,
                            protocol=endpoint.protocol,
                            status='refused'
                        )
                        
            elif endpoint.protocol in ['http', 'https']:
                # Use curl for HTTP/HTTPS
                url = f"{endpoint.protocol}://{endpoint.host}:{endpoint.port}{endpoint.health_check_path or '/'}"
                cmd = f"curl -s -o /dev/null -w '%{{http_code}}' --connect-timeout {endpoint.timeout} {url}"
                
                result = source_container.exec_run(cmd)
                
                try:
                    status_code = int(result.output.decode('utf-8').strip())
                    
                    if status_code in endpoint.expected_status_codes:
                        return ConnectivityResult(
                            from_service=from_service,
                            to_service=endpoint.name,
                            host=endpoint.host,
                            port=endpoint.port,
                            protocol=endpoint.protocol,
                            status='success',
                            additional_info={'status_code': status_code}
                        )
                    else:
                        return ConnectivityResult(
                            from_service=from_service,
                            to_service=endpoint.name,
                            host=endpoint.host,
                            port=endpoint.port,
                            protocol=endpoint.protocol,
                            status='failed',
                            error_message=f"Unexpected status code: {status_code}",
                            additional_info={'status_code': status_code}
                        )
                except:
                    return ConnectivityResult(
                        from_service=from_service,
                        to_service=endpoint.name,
                        host=endpoint.host,
                        port=endpoint.port,
                        protocol=endpoint.protocol,
                        status='failed',
                        error_message=result.output.decode('utf-8')
                    )
                    
        except Exception as e:
            return ConnectivityResult(
                from_service=from_service,
                to_service=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                protocol=endpoint.protocol,
                status='failed',
                error_message=f"Docker check failed: {str(e)}"
            )
            
    def _check_kubernetes_connectivity(self, from_service: str, endpoint: ServiceEndpoint) -> ConnectivityResult:
        """Check connectivity from within a Kubernetes pod"""
        # Use kubectl exec to run connectivity test
        kubectl_cmd = [
            'kubectl', 'exec', from_service, '--',
            'nc', '-zv', f'-w{endpoint.timeout}', endpoint.host, str(endpoint.port)
        ]
        
        try:
            result = subprocess.run(
                kubectl_cmd,
                capture_output=True,
                text=True,
                timeout=endpoint.timeout + 5
            )
            
            if result.returncode == 0:
                return ConnectivityResult(
                    from_service=from_service,
                    to_service=endpoint.name,
                    host=endpoint.host,
                    port=endpoint.port,
                    protocol=endpoint.protocol,
                    status='success'
                )
            else:
                return ConnectivityResult(
                    from_service=from_service,
                    to_service=endpoint.name,
                    host=endpoint.host,
                    port=endpoint.port,
                    protocol=endpoint.protocol,
                    status='refused',
                    error_message=result.stderr
                )
                
        except subprocess.TimeoutExpired:
            return ConnectivityResult(
                from_service=from_service,
                to_service=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                protocol=endpoint.protocol,
                status='timeout',
                error_message=f"kubectl exec timeout"
            )
        except Exception as e:
            return ConnectivityResult(
                from_service=from_service,
                to_service=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                protocol=endpoint.protocol,
                status='failed',
                error_message=f"Kubernetes check failed: {str(e)}"
            )
            
    def check_multiple_endpoints(self, endpoints: List[Dict[str, Any]], 
                               max_workers: int = 10) -> List[ConnectivityResult]:
        """Check multiple endpoints concurrently"""
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            for endpoint_config in endpoints:
                future = executor.submit(
                    self.check_connectivity,
                    **endpoint_config
                )
                futures.append((future, endpoint_config))
                
            for future, config in futures:
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except Exception as e:
                    # Create error result
                    results.append(ConnectivityResult(
                        from_service=config.get('from_service', 'local'),
                        to_service=config.get('to_service', 'unknown'),
                        host=config.get('host', 'unknown'),
                        port=config.get('port', 0),
                        protocol=config.get('protocol', 'tcp'),
                        status='failed',
                        error_message=f"Check failed: {str(e)}"
                    ))
                    
        return results
        
    def diagnose_connectivity_issue(self, result: ConnectivityResult) -> NetworkDiagnostics:
        """Diagnose connectivity issues with detailed network information"""
        diagnostics = NetworkDiagnostics(
            dns_resolution={},
            routing_table=[],
            active_connections=[],
            docker_networks=[],
            firewall_rules=[]
        )
        
        # DNS resolution
        try:
            resolver = dns.resolver.Resolver()
            answers = resolver.resolve(result.host, 'A')
            diagnostics.dns_resolution[result.host] = [str(rdata) for rdata in answers]
        except:
            diagnostics.dns_resolution[result.host] = []
            
        # Routing table
        try:
            if platform.system() == 'Darwin':  # macOS
                route_cmd = ['netstat', '-rn']
            elif platform.system() == 'Linux':
                route_cmd = ['ip', 'route']
            else:  # Windows
                route_cmd = ['route', 'print']
                
            route_output = subprocess.run(route_cmd, capture_output=True, text=True)
            diagnostics.routing_table = route_output.stdout.split('\n')[:20]  # First 20 lines
        except:
            pass
            
        # Active connections
        try:
            connections = psutil.net_connections(kind='inet')
            for conn in connections[:50]:  # First 50 connections
                if conn.laddr and conn.raddr:
                    diagnostics.active_connections.append({
                        'local': f"{conn.laddr.ip}:{conn.laddr.port}",
                        'remote': f"{conn.raddr.ip}:{conn.raddr.port}",
                        'status': conn.status,
                        'pid': conn.pid
                    })
        except:
            pass
            
        # Docker networks (if available)
        if self.docker_client:
            try:
                networks = self.docker_client.networks.list()
                for network in networks:
                    net_info = {
                        'name': network.name,
                        'driver': network.attrs.get('Driver'),
                        'scope': network.attrs.get('Scope'),
                        'containers': list(network.attrs.get('Containers', {}).keys())
                    }
                    diagnostics.docker_networks.append(net_info)
            except:
                pass
                
        # Firewall rules (platform specific)
        try:
            if platform.system() == 'Linux':
                # Check iptables
                iptables_output = subprocess.run(
                    ['sudo', 'iptables', '-L', '-n'],
                    capture_output=True,
                    text=True
                )
                diagnostics.firewall_rules = iptables_output.stdout.split('\n')[:30]
            elif platform.system() == 'Darwin':
                # Check pfctl on macOS
                pfctl_output = subprocess.run(
                    ['sudo', 'pfctl', '-s', 'rules'],
                    capture_output=True,
                    text=True
                )
                diagnostics.firewall_rules = pfctl_output.stdout.split('\n')[:30]
        except:
            pass
            
        return diagnostics
        
    def generate_connectivity_matrix(self, services: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a connectivity matrix between services"""
        matrix = {}
        results = []
        
        # Check connectivity between all service pairs
        for from_service in services:
            for to_service in services:
                if from_service['name'] != to_service['name']:
                    result = self.check_connectivity(
                        from_service=from_service['name'],
                        to_service=to_service['name'],
                        host=to_service.get('host', to_service['name']),
                        port=to_service['port'],
                        protocol=to_service.get('protocol', 'tcp'),
                        environment=from_service.get('environment', 'local')
                    )
                    results.append(result)
                    
                    # Build matrix
                    if from_service['name'] not in matrix:
                        matrix[from_service['name']] = {}
                    matrix[from_service['name']][to_service['name']] = {
                        'status': result.status,
                        'latency': result.latency
                    }
                    
        return {
            'matrix': matrix,
            'results': results,
            'summary': self._generate_summary(results)
        }
        
    def _generate_summary(self, results: List[ConnectivityResult]) -> Dict[str, Any]:
        """Generate summary statistics"""
        total = len(results)
        successful = len([r for r in results if r.status == 'success'])
        failed = len([r for r in results if r.status in ['failed', 'refused']])
        timeout = len([r for r in results if r.status == 'timeout'])
        dns_errors = len([r for r in results if r.status == 'dns_error'])
        
        latencies = [r.latency for r in results if r.latency is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        return {
            'total_checks': total,
            'successful': successful,
            'failed': failed,
            'timeout': timeout,
            'dns_errors': dns_errors,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'average_latency_ms': avg_latency
        }


def format_connectivity_report(results: List[ConnectivityResult], 
                             diagnostics: Optional[NetworkDiagnostics] = None,
                             format: str = 'text') -> str:
    """Format connectivity results into a report"""
    if format == 'json':
        data = {
            'results': [
                {
                    'from_service': r.from_service,
                    'to_service': r.to_service,
                    'host': r.host,
                    'port': r.port,
                    'protocol': r.protocol,
                    'status': r.status,
                    'latency': r.latency,
                    'error_message': r.error_message,
                    'timestamp': r.timestamp.isoformat(),
                    'additional_info': r.additional_info
                }
                for r in results
            ]
        }
        
        if diagnostics:
            data['diagnostics'] = {
                'dns_resolution': diagnostics.dns_resolution,
                'routing_table': diagnostics.routing_table,
                'active_connections': diagnostics.active_connections,
                'docker_networks': diagnostics.docker_networks,
                'firewall_rules': diagnostics.firewall_rules
            }
            
        return json.dumps(data, indent=2)
        
    # Text format
    lines = []
    lines.append("=" * 80)
    lines.append("SERVICE CONNECTIVITY REPORT")
    lines.append("=" * 80)
    
    # Summary
    total = len(results)
    successful = len([r for r in results if r.status == 'success'])
    failed = len([r for r in results if r.status != 'success'])
    
    lines.append(f"\nTotal Checks: {total}")
    lines.append(f"Successful: {successful}")
    lines.append(f"Failed: {failed}")
    
    if total > 0:
        lines.append(f"Success Rate: {successful/total*100:.1f}%")
        
    # Results table
    lines.append("\n" + "-" * 80)
    lines.append("CONNECTIVITY RESULTS")
    lines.append("-" * 80)
    lines.append(f"{'From':<20} {'To':<20} {'Host:Port':<25} {'Status':<10} {'Latency':<10}")
    lines.append("-" * 80)
    
    for result in results:
        from_service = result.from_service[:19]
        to_service = result.to_service[:19]
        host_port = f"{result.host}:{result.port}"[:24]
        status = result.status[:9]
        latency = f"{result.latency:.1f}ms" if result.latency else "N/A"
        
        status_icon = {
            'success': '✓',
            'failed': '✗',
            'timeout': '⏱',
            'refused': '⚠',
            'dns_error': '🔍'
        }.get(result.status, '?')
        
        lines.append(f"{from_service:<20} {to_service:<20} {host_port:<25} {status_icon} {status:<9} {latency:<10}")
        
        if result.error_message:
            lines.append(f"  └─ Error: {result.error_message}")
            
    # Failed connections details
    failed_results = [r for r in results if r.status != 'success']
    if failed_results:
        lines.append("\n" + "-" * 80)
        lines.append("FAILED CONNECTIONS DETAILS")
        lines.append("-" * 80)
        
        for result in failed_results:
            lines.append(f"\n{result.from_service} → {result.to_service} ({result.host}:{result.port})")
            lines.append(f"Status: {result.status}")
            if result.error_message:
                lines.append(f"Error: {result.error_message}")
                
    # Diagnostics
    if diagnostics:
        lines.append("\n" + "-" * 80)
        lines.append("NETWORK DIAGNOSTICS")
        lines.append("-" * 80)
        
        # DNS Resolution
        if diagnostics.dns_resolution:
            lines.append("\nDNS Resolution:")
            for host, ips in diagnostics.dns_resolution.items():
                lines.append(f"  {host}: {', '.join(ips) if ips else 'No resolution'}")
                
        # Docker Networks
        if diagnostics.docker_networks:
            lines.append("\nDocker Networks:")
            for net in diagnostics.docker_networks:
                lines.append(f"  {net['name']} ({net['driver']}): {len(net['containers'])} containers")
                
        # Active Connections (sample)
        if diagnostics.active_connections:
            lines.append(f"\nActive Connections (sample of {len(diagnostics.active_connections)}):")
            for conn in diagnostics.active_connections[:5]:
                lines.append(f"  {conn['local']} → {conn['remote']} [{conn['status']}]")
                
    return '\n'.join(lines)


def load_service_config(config_file: str) -> List[Dict[str, Any]]:
    """Load service configuration from file"""
    config_path = Path(config_file)
    
    with open(config_path, 'r') as f:
        if config_path.suffix in ['.yaml', '.yml']:
            data = yaml.safe_load(f)
        else:
            data = json.load(f)
            
    return data.get('services', [])


def main():
    """CLI interface for service connectivity checker"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Service Connectivity Checker - Verify service connectivity across environments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration file example (services.yaml):

services:
  - name: frontend
    host: frontend
    port: 3000
    protocol: http
    health_check_path: /health
    environment: docker
    
  - name: backend
    host: backend
    port: 8000
    protocol: http
    health_check_path: /api/health
    environment: docker
    expected_status_codes: [200, 204]
    
  - name: database
    host: postgres
    port: 5432
    protocol: tcp
    environment: docker

Examples:
  # Check single connection
  python service_connectivity_checker.py --from local --to backend --host localhost --port 8000
  
  # Check HTTP endpoint
  python service_connectivity_checker.py --from frontend --to backend --host backend --port 8000 --protocol http
  
  # Load services from config and generate matrix
  python service_connectivity_checker.py --config services.yaml --matrix
  
  # Check with diagnostics
  python service_connectivity_checker.py --from frontend --to backend --host backend --port 8000 --diagnose
  
  # Check from Docker container
  python service_connectivity_checker.py --from frontend-container --to backend --host backend --port 8000 --env docker
        """
    )
    
    parser.add_argument('--from', dest='from_service', default='local', help='Source service name')
    parser.add_argument('--to', dest='to_service', help='Target service name')
    parser.add_argument('--host', help='Target host/IP')
    parser.add_argument('--port', type=int, help='Target port')
    parser.add_argument('--protocol', default='tcp', choices=['tcp', 'http', 'https'], help='Protocol to check')
    parser.add_argument('--env', dest='environment', default='local', 
                       choices=['local', 'docker', 'kubernetes'], help='Environment type')
    parser.add_argument('--config', help='Service configuration file (YAML or JSON)')
    parser.add_argument('--matrix', action='store_true', help='Generate connectivity matrix for all services')
    parser.add_argument('--diagnose', action='store_true', help='Include network diagnostics')
    parser.add_argument('--timeout', type=int, default=5, help='Connection timeout in seconds')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', '-o', help='Write report to file')
    
    args = parser.parse_args()
    
    checker = ServiceConnectivityChecker()
    results = []
    diagnostics = None
    
    if args.config:
        # Load service configuration
        services = load_service_config(args.config)
        
        if args.matrix:
            # Generate connectivity matrix
            matrix_result = checker.generate_connectivity_matrix(services)
            
            if args.json:
                output = json.dumps(matrix_result, indent=2)
            else:
                # Format matrix as text
                output = format_connectivity_report(matrix_result['results'])
                output += "\n\nCONNECTIVITY MATRIX:\n"
                output += "-" * 80 + "\n"
                
                # Print matrix
                service_names = [s['name'] for s in services]
                output += f"{'FROM/TO':<20}"
                for name in service_names:
                    output += f"{name[:10]:<12}"
                output += "\n" + "-" * 80 + "\n"
                
                for from_name in service_names:
                    output += f"{from_name[:19]:<20}"
                    for to_name in service_names:
                        if from_name == to_name:
                            output += f"{'--':<12}"
                        else:
                            conn = matrix_result['matrix'].get(from_name, {}).get(to_name, {})
                            status = conn.get('status', 'unknown')
                            icon = '✓' if status == 'success' else '✗'
                            output += f"{icon:<12}"
                    output += "\n"
        else:
            # Check all configured endpoints
            endpoint_configs = []
            for service in services:
                endpoint_configs.append({
                    'from_service': args.from_service,
                    'to_service': service['name'],
                    'host': service.get('host', service['name']),
                    'port': service['port'],
                    'protocol': service.get('protocol', 'tcp'),
                    'environment': service.get('environment', 'local'),
                    'health_check_path': service.get('health_check_path'),
                    'expected_status_codes': service.get('expected_status_codes', [200]),
                    'timeout': service.get('timeout', args.timeout)
                })
                
            results = checker.check_multiple_endpoints(endpoint_configs)
            
    elif args.to_service and args.host and args.port:
        # Single endpoint check
        result = checker.check_connectivity(
            from_service=args.from_service,
            to_service=args.to_service,
            host=args.host,
            port=args.port,
            protocol=args.protocol,
            environment=args.environment,
            timeout=args.timeout
        )
        results = [result]
        
        if args.diagnose and result.status != 'success':
            diagnostics = checker.diagnose_connectivity_issue(result)
            
    else:
        parser.error("Either --config or (--to, --host, --port) must be specified")
        
    # Format output
    if 'output' not in locals():
        output = format_connectivity_report(results, diagnostics, 'json' if args.json else 'text')
        
    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Report written to: {args.output}")
    else:
        print(output)
        
    # Exit code
    if results:
        failed = len([r for r in results if r.status != 'success'])
        sys.exit(1 if failed > 0 else 0)


if __name__ == '__main__':
    main()