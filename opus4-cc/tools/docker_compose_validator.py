#!/usr/bin/env python3
"""
Docker Compose Validator Tool

Validates Docker Compose configurations for common issues including:
- Service connectivity and networking
- Environment variable configuration
- Volume and port mappings
- Resource limits and constraints
- Security best practices
"""

import os
import re
import sys
import yaml
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import ipaddress
import urllib.parse


@dataclass
class ValidationIssue:
    """Represents a Docker Compose configuration issue"""
    type: str  # 'error', 'warning', 'info'
    severity: str  # 'critical', 'high', 'medium', 'low'
    service: Optional[str]
    category: str  # 'networking', 'security', 'resources', 'volumes', 'environment', 'general'
    message: str
    suggestion: Optional[str] = None
    line_number: Optional[int] = None


class DockerComposeValidator:
    """Validates Docker Compose configurations"""
    
    # Common port mappings that might indicate issues
    LOCALHOST_PATTERNS = [
        r'localhost:\d+',
        r'127\.0\.0\.1:\d+',
        r'0\.0\.0\.0:\d+',
        r'\[::\]:\d+',
    ]
    
    # Insecure environment variable patterns
    SENSITIVE_ENV_PATTERNS = [
        r'password',
        r'passwd',
        r'pwd',
        r'secret',
        r'key',
        r'token',
        r'api_key',
        r'apikey',
        r'auth',
        r'credential',
        r'private',
        r'cert',
        r'certificate',
    ]
    
    # Common Docker networks
    DEFAULT_NETWORKS = ['bridge', 'host', 'none']
    
    # Security-sensitive capabilities
    DANGEROUS_CAPABILITIES = [
        'SYS_ADMIN',
        'SYS_PTRACE',
        'SYS_MODULE',
        'SYS_RAWIO',
        'SYS_BOOT',
        'SYS_TIME',
        'MKNOD',
        'AUDIT_WRITE',
        'NET_ADMIN',
        'NET_RAW',
    ]
    
    # Reserved port ranges
    RESERVED_PORTS = {
        (1, 1023): "Well-known ports (requires root)",
        (6000, 6063): "X11 ports",
        (11211, 11211): "Memcached",
        (27017, 27019): "MongoDB",
        (3306, 3306): "MySQL",
        (5432, 5432): "PostgreSQL",
        (6379, 6379): "Redis",
        (9200, 9300): "Elasticsearch",
        (5672, 5672): "RabbitMQ",
        (9092, 9092): "Kafka",
        (2181, 2181): "Zookeeper",
    }
    
    def __init__(self, compose_file: str):
        self.compose_file = Path(compose_file)
        self.compose_dir = self.compose_file.parent
        self.compose_data: Dict[str, Any] = {}
        self.issues: List[ValidationIssue] = []
        self.services: Dict[str, Any] = {}
        self.networks: Dict[str, Any] = {}
        self.volumes: Dict[str, Any] = {}
        
    def validate(self, check_networking: bool = True,
                check_env_vars: bool = True,
                check_security: bool = True,
                check_resources: bool = True,
                check_volumes: bool = True,
                check_best_practices: bool = True) -> List[ValidationIssue]:
        """
        Validate the Docker Compose file
        
        Returns:
            List of validation issues found
        """
        # Load and parse the compose file
        if not self._load_compose_file():
            return self.issues
            
        # Extract main sections
        self.services = self.compose_data.get('services', {})
        self.networks = self.compose_data.get('networks', {})
        self.volumes = self.compose_data.get('volumes', {})
        
        # Run validation checks
        if check_networking:
            self._validate_networking()
            
        if check_env_vars:
            self._validate_environment_variables()
            
        if check_security:
            self._validate_security()
            
        if check_resources:
            self._validate_resources()
            
        if check_volumes:
            self._validate_volumes()
            
        if check_best_practices:
            self._validate_best_practices()
            
        # Sort issues by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        self.issues.sort(key=lambda x: (severity_order.get(x.severity, 4), x.service or ''))
        
        return self.issues
        
    def _load_compose_file(self) -> bool:
        """Load and parse the Docker Compose file"""
        try:
            with open(self.compose_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Try to parse as YAML
            self.compose_data = yaml.safe_load(content)
            
            if not isinstance(self.compose_data, dict):
                self.issues.append(ValidationIssue(
                    type='error',
                    severity='critical',
                    service=None,
                    category='general',
                    message="Invalid Docker Compose file: root element must be a dictionary"
                ))
                return False
                
            # Check version
            version = self.compose_data.get('version')
            if version:
                try:
                    ver_num = float(version)
                    if ver_num < 3.0:
                        self.issues.append(ValidationIssue(
                            type='warning',
                            severity='low',
                            service=None,
                            category='general',
                            message=f"Using older Compose file version {version}",
                            suggestion="Consider upgrading to version 3.8 or later for better features"
                        ))
                except ValueError:
                    pass
                    
            return True
            
        except yaml.YAMLError as e:
            self.issues.append(ValidationIssue(
                type='error',
                severity='critical',
                service=None,
                category='general',
                message=f"Failed to parse YAML: {str(e)}"
            ))
            return False
        except Exception as e:
            self.issues.append(ValidationIssue(
                type='error',
                severity='critical',
                service=None,
                category='general',
                message=f"Failed to load compose file: {str(e)}"
            ))
            return False
            
    def _validate_networking(self):
        """Validate networking configuration"""
        # Check for localhost references in service configurations
        for service_name, service_config in self.services.items():
            if not isinstance(service_config, dict):
                continue
                
            # Check environment variables for localhost references
            env_vars = self._get_environment_variables(service_config)
            for key, value in env_vars.items():
                if value and any(pattern in str(value).lower() for pattern in ['localhost', '127.0.0.1']):
                    self.issues.append(ValidationIssue(
                        type='error',
                        severity='high',
                        service=service_name,
                        category='networking',
                        message=f"Environment variable '{key}' contains localhost reference: {value}",
                        suggestion=f"Use service name instead (e.g., 'http://{service_name}:port' or 'http://other_service:port')"
                    ))
                    
            # Check command and entrypoint for localhost
            for field in ['command', 'entrypoint']:
                field_value = service_config.get(field)
                if field_value:
                    cmd_str = ' '.join(field_value) if isinstance(field_value, list) else str(field_value)
                    if any(pattern in cmd_str for pattern in ['localhost', '127.0.0.1']):
                        self.issues.append(ValidationIssue(
                            type='error',
                            severity='high',
                            service=service_name,
                            category='networking',
                            message=f"{field.capitalize()} contains localhost reference",
                            suggestion="Use service names for inter-service communication"
                        ))
                        
            # Check port mappings
            ports = service_config.get('ports', [])
            for port in ports:
                port_str = str(port)
                
                # Check for privileged ports
                if ':' in port_str:
                    host_port = port_str.split(':')[0]
                    try:
                        port_num = int(host_port.split('.')[-1] if '.' in host_port else host_port)
                        if port_num < 1024:
                            self.issues.append(ValidationIssue(
                                type='warning',
                                severity='medium',
                                service=service_name,
                                category='networking',
                                message=f"Using privileged port {port_num} (requires root)",
                                suggestion="Consider using a port >= 1024 or run with appropriate permissions"
                            ))
                    except ValueError:
                        pass
                        
            # Check for missing network configuration
            if 'networks' not in service_config and len(self.services) > 1:
                self.issues.append(ValidationIssue(
                    type='info',
                    severity='low',
                    service=service_name,
                    category='networking',
                    message="Service not explicitly assigned to a network",
                    suggestion="Consider explicitly defining networks for better isolation"
                ))
                
        # Validate network definitions
        for network_name, network_config in self.networks.items():
            if isinstance(network_config, dict):
                driver = network_config.get('driver', 'bridge')
                
                # Check for host network mode with multiple services
                if driver == 'host' and len(self.services) > 1:
                    self.issues.append(ValidationIssue(
                        type='warning',
                        severity='high',
                        service=None,
                        category='networking',
                        message=f"Network '{network_name}' uses host driver with multiple services",
                        suggestion="Host network mode shares the host's network stack and can cause conflicts"
                    ))
                    
                # Check for custom subnet configurations
                ipam = network_config.get('ipam', {})
                if isinstance(ipam, dict) and 'config' in ipam:
                    for subnet_config in ipam['config']:
                        if 'subnet' in subnet_config:
                            try:
                                subnet = ipaddress.ip_network(subnet_config['subnet'])
                                # Check for common conflicts
                                common_subnets = [
                                    ipaddress.ip_network('172.17.0.0/16'),  # Docker default
                                    ipaddress.ip_network('192.168.0.0/16'),  # Common home networks
                                    ipaddress.ip_network('10.0.0.0/8'),      # Common corporate networks
                                ]
                                for common in common_subnets:
                                    if subnet.overlaps(common):
                                        self.issues.append(ValidationIssue(
                                            type='warning',
                                            severity='medium',
                                            service=None,
                                            category='networking',
                                            message=f"Network '{network_name}' subnet {subnet} may conflict with common networks",
                                            suggestion="Consider using a less common subnet to avoid conflicts"
                                        ))
                                        break
                            except ValueError:
                                self.issues.append(ValidationIssue(
                                    type='error',
                                    severity='high',
                                    service=None,
                                    category='networking',
                                    message=f"Invalid subnet configuration for network '{network_name}'",
                                ))
                                
        # Check for inter-service dependencies
        self._validate_service_dependencies()
        
    def _validate_service_dependencies(self):
        """Validate service dependencies and links"""
        for service_name, service_config in self.services.items():
            if not isinstance(service_config, dict):
                continue
                
            # Check depends_on
            depends_on = service_config.get('depends_on', [])
            if isinstance(depends_on, dict):
                depends_on = list(depends_on.keys())
            elif not isinstance(depends_on, list):
                depends_on = [depends_on]
                
            for dep in depends_on:
                if dep not in self.services:
                    self.issues.append(ValidationIssue(
                        type='error',
                        severity='high',
                        service=service_name,
                        category='networking',
                        message=f"Depends on non-existent service '{dep}'",
                    ))
                    
            # Check links (deprecated but still used)
            links = service_config.get('links', [])
            if links:
                self.issues.append(ValidationIssue(
                    type='warning',
                    severity='low',
                    service=service_name,
                    category='networking',
                    message="Using deprecated 'links' option",
                    suggestion="Use user-defined networks instead of links"
                ))
                
            # Check for circular dependencies
            if depends_on:
                visited = set()
                if self._has_circular_dependency(service_name, visited):
                    self.issues.append(ValidationIssue(
                        type='error',
                        severity='critical',
                        service=service_name,
                        category='networking',
                        message="Circular dependency detected",
                        suggestion="Review and break the circular dependency chain"
                    ))
                    
    def _has_circular_dependency(self, service: str, visited: Set[str], path: List[str] = None) -> bool:
        """Check for circular dependencies"""
        if path is None:
            path = []
            
        if service in path:
            return True
            
        if service in visited:
            return False
            
        visited.add(service)
        path.append(service)
        
        service_config = self.services.get(service, {})
        depends_on = service_config.get('depends_on', [])
        if isinstance(depends_on, dict):
            depends_on = list(depends_on.keys())
        elif not isinstance(depends_on, list):
            depends_on = [depends_on]
            
        for dep in depends_on:
            if dep in self.services and self._has_circular_dependency(dep, visited, path.copy()):
                return True
                
        return False
        
    def _validate_environment_variables(self):
        """Validate environment variable configurations"""
        # Check for .env file
        env_file = self.compose_dir / '.env'
        env_file_exists = env_file.exists()
        
        for service_name, service_config in self.services.items():
            if not isinstance(service_config, dict):
                continue
                
            # Get all environment variables
            env_vars = self._get_environment_variables(service_config)
            
            # Check for sensitive values in plain text
            for key, value in env_vars.items():
                key_lower = key.lower()
                
                # Check if it's a sensitive variable
                is_sensitive = any(pattern in key_lower for pattern in self.SENSITIVE_ENV_PATTERNS)
                
                if is_sensitive and value and not str(value).startswith('${'):
                    # Check if value looks like a real credential
                    if len(str(value)) > 3 and value != 'changeme' and value != 'password':
                        self.issues.append(ValidationIssue(
                            type='error',
                            severity='critical',
                            service=service_name,
                            category='security',
                            message=f"Sensitive environment variable '{key}' has hardcoded value",
                            suggestion="Use Docker secrets or environment variable substitution (${VAR_NAME})"
                        ))
                        
                # Check for missing variable substitutions
                if value and '${' in str(value):
                    # Extract variable names
                    var_pattern = r'\$\{([^}]+)\}'
                    variables = re.findall(var_pattern, str(value))
                    
                    for var in variables:
                        # Remove default value syntax
                        var_name = var.split(':-')[0].split(':?')[0]
                        
                        # Check if it's likely to be defined
                        if not env_file_exists and ':' not in var:
                            self.issues.append(ValidationIssue(
                                type='warning',
                                severity='medium',
                                service=service_name,
                                category='environment',
                                message=f"Environment variable substitution '${{{var_name}}}' used but no .env file found",
                                suggestion="Create a .env file or ensure the variable is set in the shell environment"
                            ))
                            
            # Check env_file entries
            env_files = service_config.get('env_file', [])
            if isinstance(env_files, str):
                env_files = [env_files]
                
            for env_file_path in env_files:
                full_path = self.compose_dir / env_file_path
                if not full_path.exists():
                    self.issues.append(ValidationIssue(
                        type='error',
                        severity='high',
                        service=service_name,
                        category='environment',
                        message=f"Environment file '{env_file_path}' not found",
                        suggestion=f"Create the file at {full_path}"
                    ))
                    
    def _get_environment_variables(self, service_config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract environment variables from service configuration"""
        env_vars = {}
        
        # Handle environment as dict
        if 'environment' in service_config:
            env = service_config['environment']
            if isinstance(env, dict):
                env_vars.update(env)
            elif isinstance(env, list):
                # Handle list format (KEY=VALUE)
                for item in env:
                    if '=' in str(item):
                        key, value = str(item).split('=', 1)
                        env_vars[key] = value
                    else:
                        env_vars[str(item)] = None
                        
        return env_vars
        
    def _validate_security(self):
        """Validate security configurations"""
        for service_name, service_config in self.services.items():
            if not isinstance(service_config, dict):
                continue
                
            # Check for privileged mode
            if service_config.get('privileged'):
                self.issues.append(ValidationIssue(
                    type='warning',
                    severity='high',
                    service=service_name,
                    category='security',
                    message="Service running in privileged mode",
                    suggestion="Avoid privileged mode; use specific capabilities instead if needed"
                ))
                
            # Check for dangerous capabilities
            cap_add = service_config.get('cap_add', [])
            if isinstance(cap_add, str):
                cap_add = [cap_add]
                
            for cap in cap_add:
                if cap in self.DANGEROUS_CAPABILITIES:
                    self.issues.append(ValidationIssue(
                        type='warning',
                        severity='high',
                        service=service_name,
                        category='security',
                        message=f"Service has dangerous capability: {cap}",
                        suggestion="Review if this capability is truly necessary"
                    ))
                    
            # Check for running as root
            user = service_config.get('user')
            if user in ['root', '0', '0:0']:
                self.issues.append(ValidationIssue(
                    type='warning',
                    severity='medium',
                    service=service_name,
                    category='security',
                    message="Service explicitly running as root user",
                    suggestion="Run as a non-root user for better security"
                ))
                
            # Check for host network mode
            network_mode = service_config.get('network_mode')
            if network_mode == 'host':
                self.issues.append(ValidationIssue(
                    type='warning',
                    severity='medium',
                    service=service_name,
                    category='security',
                    message="Service using host network mode",
                    suggestion="Use bridge networking for better isolation"
                ))
                
            # Check for host PID/IPC namespace
            if service_config.get('pid') == 'host':
                self.issues.append(ValidationIssue(
                    type='warning',
                    severity='high',
                    service=service_name,
                    category='security',
                    message="Service sharing host PID namespace",
                    suggestion="Avoid sharing host PID namespace unless necessary"
                ))
                
            if service_config.get('ipc') == 'host':
                self.issues.append(ValidationIssue(
                    type='warning',
                    severity='high',
                    service=service_name,
                    category='security',
                    message="Service sharing host IPC namespace",
                    suggestion="Avoid sharing host IPC namespace unless necessary"
                ))
                
            # Check for insecure registries
            image = service_config.get('image', '')
            if image and not image.startswith(('localhost', '127.0.0.1')):
                # Check if using HTTP registry
                if re.match(r'^https?://', image):
                    if image.startswith('http://'):
                        self.issues.append(ValidationIssue(
                            type='error',
                            severity='high',
                            service=service_name,
                            category='security',
                            message="Using insecure HTTP registry",
                            suggestion="Use HTTPS for registry connections"
                        ))
                        
            # Check security_opt
            security_opt = service_config.get('security_opt', [])
            if isinstance(security_opt, str):
                security_opt = [security_opt]
                
            for opt in security_opt:
                if 'apparmor:unconfined' in opt or 'seccomp:unconfined' in opt:
                    self.issues.append(ValidationIssue(
                        type='warning',
                        severity='high',
                        service=service_name,
                        category='security',
                        message=f"Disabling security features: {opt}",
                        suggestion="Keep security features enabled unless absolutely necessary"
                    ))
                    
    def _validate_resources(self):
        """Validate resource limits and reservations"""
        total_memory_limit = 0
        total_memory_reservation = 0
        
        for service_name, service_config in self.services.items():
            if not isinstance(service_config, dict):
                continue
                
            # Check for resource limits
            deploy = service_config.get('deploy', {})
            resources = deploy.get('resources', {})
            
            # Check if resources are defined at all
            if not resources and service_config.get('mem_limit') is None and service_config.get('cpu_shares') is None:
                self.issues.append(ValidationIssue(
                    type='info',
                    severity='low',
                    service=service_name,
                    category='resources',
                    message="No resource limits defined",
                    suggestion="Consider setting memory and CPU limits to prevent resource exhaustion"
                ))
                
            # Check memory limits
            limits = resources.get('limits', {})
            reservations = resources.get('reservations', {})
            
            memory_limit = limits.get('memory')
            memory_reservation = reservations.get('memory')
            
            # Handle legacy mem_limit
            if service_config.get('mem_limit'):
                memory_limit = service_config['mem_limit']
                
            if memory_limit:
                limit_bytes = self._parse_memory_value(memory_limit)
                if limit_bytes:
                    total_memory_limit += limit_bytes
                    
                    # Check if limit is very high
                    if limit_bytes > 8 * 1024**3:  # 8GB
                        self.issues.append(ValidationIssue(
                            type='warning',
                            severity='medium',
                            service=service_name,
                            category='resources',
                            message=f"Very high memory limit: {memory_limit}",
                            suggestion="Ensure this service really needs this much memory"
                        ))
                        
            if memory_reservation:
                reservation_bytes = self._parse_memory_value(memory_reservation)
                if reservation_bytes:
                    total_memory_reservation += reservation_bytes
                    
                    # Check if reservation > limit
                    if memory_limit and reservation_bytes > self._parse_memory_value(memory_limit):
                        self.issues.append(ValidationIssue(
                            type='error',
                            severity='high',
                            service=service_name,
                            category='resources',
                            message="Memory reservation exceeds memory limit",
                        ))
                        
            # Check CPU limits
            cpu_limit = limits.get('cpus')
            cpu_reservation = reservations.get('cpus')
            
            if cpu_limit:
                try:
                    cpu_float = float(cpu_limit)
                    if cpu_float > 16:
                        self.issues.append(ValidationIssue(
                            type='warning',
                            severity='medium',
                            service=service_name,
                            category='resources',
                            message=f"Very high CPU limit: {cpu_limit}",
                            suggestion="Ensure this service really needs this many CPUs"
                        ))
                except ValueError:
                    self.issues.append(ValidationIssue(
                        type='error',
                        severity='high',
                        service=service_name,
                        category='resources',
                        message=f"Invalid CPU limit value: {cpu_limit}",
                    ))
                    
            # Check replicas with resource constraints
            replicas = deploy.get('replicas', 1)
            if replicas > 1 and memory_limit:
                total_memory_needed = self._parse_memory_value(memory_limit) * replicas
                if total_memory_needed > 16 * 1024**3:  # 16GB
                    self.issues.append(ValidationIssue(
                        type='warning',
                        severity='medium',
                        service=service_name,
                        category='resources',
                        message=f"High total memory usage with {replicas} replicas: {total_memory_needed / 1024**3:.1f}GB",
                        suggestion="Ensure the host has sufficient memory"
                    ))
                    
    def _parse_memory_value(self, memory_str: Any) -> Optional[int]:
        """Parse memory value to bytes"""
        if isinstance(memory_str, int):
            return memory_str
            
        if not isinstance(memory_str, str):
            return None
            
        # Parse memory string (e.g., "512m", "2g", "1gb")
        match = re.match(r'^(\d+(?:\.\d+)?)\s*([kmgt]?)i?b?$', memory_str.lower())
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            
            multipliers = {
                '': 1,
                'k': 1024,
                'm': 1024**2,
                'g': 1024**3,
                't': 1024**4,
            }
            
            return int(value * multipliers.get(unit, 1))
            
        return None
        
    def _validate_volumes(self):
        """Validate volume configurations"""
        # Track volume usage
        volume_usage = defaultdict(list)
        
        for service_name, service_config in self.services.items():
            if not isinstance(service_config, dict):
                continue
                
            volumes = service_config.get('volumes', [])
            
            for volume in volumes:
                if isinstance(volume, str):
                    parts = volume.split(':')
                    source = parts[0]
                    target = parts[1] if len(parts) > 1 else None
                    mode = parts[2] if len(parts) > 2 else 'rw'
                    
                    # Check for absolute paths on host
                    if source.startswith('/'):
                        # Host mount
                        self.issues.append(ValidationIssue(
                            type='info',
                            severity='low',
                            service=service_name,
                            category='volumes',
                            message=f"Using host mount: {source}",
                            suggestion="Consider using named volumes for better portability"
                        ))
                        
                        # Check for sensitive host paths
                        sensitive_paths = ['/etc', '/root', '/home', '/var/run/docker.sock']
                        for sensitive in sensitive_paths:
                            if source.startswith(sensitive):
                                severity = 'critical' if sensitive == '/var/run/docker.sock' else 'high'
                                self.issues.append(ValidationIssue(
                                    type='warning',
                                    severity=severity,
                                    service=service_name,
                                    category='security',
                                    message=f"Mounting sensitive host path: {source}",
                                    suggestion="Avoid mounting sensitive system directories"
                                ))
                                break
                                
                    # Check for relative paths
                    elif source.startswith('./') or source.startswith('../'):
                        # Relative path - check if it exists
                        full_path = self.compose_dir / source
                        if not full_path.exists():
                            self.issues.append(ValidationIssue(
                                type='warning',
                                severity='medium',
                                service=service_name,
                                category='volumes',
                                message=f"Volume source path does not exist: {source}",
                                suggestion=f"Create the directory: {full_path}"
                            ))
                            
                    else:
                        # Named volume
                        volume_usage[source].append(service_name)
                        
                        # Check if volume is defined
                        if source not in self.volumes and ':' not in source:
                            self.issues.append(ValidationIssue(
                                type='info',
                                severity='low',
                                service=service_name,
                                category='volumes',
                                message=f"Using undefined named volume: {source}",
                                suggestion="Define the volume in the 'volumes' section for better control"
                            ))
                            
                elif isinstance(volume, dict):
                    volume_type = volume.get('type', 'volume')
                    source = volume.get('source')
                    
                    if volume_type == 'bind' and source:
                        # Similar checks as string format
                        if source.startswith('/'):
                            sensitive_paths = ['/etc', '/root', '/home', '/var/run/docker.sock']
                            for sensitive in sensitive_paths:
                                if source.startswith(sensitive):
                                    severity = 'critical' if sensitive == '/var/run/docker.sock' else 'high'
                                    self.issues.append(ValidationIssue(
                                        type='warning',
                                        severity=severity,
                                        service=service_name,
                                        category='security',
                                        message=f"Mounting sensitive host path: {source}",
                                        suggestion="Avoid mounting sensitive system directories"
                                    ))
                                    break
                                    
        # Check for volumes used by multiple services
        for volume_name, services in volume_usage.items():
            if len(services) > 1:
                self.issues.append(ValidationIssue(
                    type='info',
                    severity='low',
                    service=None,
                    category='volumes',
                    message=f"Volume '{volume_name}' shared by multiple services: {', '.join(services)}",
                    suggestion="Ensure this is intentional and consider data consistency"
                ))
                
    def _validate_best_practices(self):
        """Validate against Docker Compose best practices"""
        # Check compose file version
        if 'version' not in self.compose_data:
            self.issues.append(ValidationIssue(
                type='warning',
                severity='low',
                service=None,
                category='general',
                message="No version specified in compose file",
                suggestion="Specify a version (e.g., version: '3.8') for compatibility"
            ))
            
        # Check service naming
        for service_name in self.services:
            if not re.match(r'^[a-z][a-z0-9_-]*$', service_name):
                self.issues.append(ValidationIssue(
                    type='warning',
                    severity='low',
                    service=service_name,
                    category='general',
                    message="Service name doesn't follow naming conventions",
                    suggestion="Use lowercase letters, numbers, underscores, and hyphens"
                ))
                
            # Check for too generic names
            generic_names = ['app', 'web', 'api', 'service', 'server', 'main']
            if service_name in generic_names and len(self.services) > 1:
                self.issues.append(ValidationIssue(
                    type='info',
                    severity='low',
                    service=service_name,
                    category='general',
                    message=f"Service name '{service_name}' is too generic",
                    suggestion="Use more descriptive names (e.g., 'frontend-web', 'auth-api')"
                ))
                
        # Check for missing health checks
        for service_name, service_config in self.services.items():
            if isinstance(service_config, dict) and 'healthcheck' not in service_config:
                self.issues.append(ValidationIssue(
                    type='info',
                    severity='low',
                    service=service_name,
                    category='general',
                    message="No health check defined",
                    suggestion="Add a healthcheck for better container management"
                ))
                
        # Check for missing restart policies
        for service_name, service_config in self.services.items():
            if isinstance(service_config, dict):
                restart_policy = service_config.get('restart')
                deploy = service_config.get('deploy', {})
                restart_policy_deploy = deploy.get('restart_policy', {})
                
                if not restart_policy and not restart_policy_deploy:
                    self.issues.append(ValidationIssue(
                        type='info',
                        severity='low',
                        service=service_name,
                        category='general',
                        message="No restart policy defined",
                        suggestion="Consider adding restart: unless-stopped or restart: on-failure"
                    ))
                    
        # Check for missing logging configuration
        for service_name, service_config in self.services.items():
            if isinstance(service_config, dict) and 'logging' not in service_config:
                self.issues.append(ValidationIssue(
                    type='info',
                    severity='low',
                    service=service_name,
                    category='general',
                    message="No logging configuration defined",
                    suggestion="Consider configuring logging driver and options"
                ))
                
    def generate_report(self) -> str:
        """Generate a detailed validation report"""
        report = []
        report.append("=" * 80)
        report.append("DOCKER COMPOSE VALIDATION REPORT")
        report.append("=" * 80)
        report.append(f"\nFile: {self.compose_file}")
        report.append(f"Services: {len(self.services)}")
        report.append(f"Networks: {len(self.networks)}")
        report.append(f"Volumes: {len(self.volumes)}")
        report.append(f"Total Issues: {len(self.issues)}")
        
        # Count by severity
        severity_counts = defaultdict(int)
        for issue in self.issues:
            severity_counts[issue.severity] += 1
            
        report.append(f"\nIssues by Severity:")
        for severity in ['critical', 'high', 'medium', 'low']:
            count = severity_counts.get(severity, 0)
            if count > 0:
                report.append(f"  {severity.upper()}: {count}")
                
        # Group issues by category
        category_issues = defaultdict(list)
        for issue in self.issues:
            category_issues[issue.category].append(issue)
            
        # Report each category
        for category in ['security', 'networking', 'resources', 'environment', 'volumes', 'general']:
            if category in category_issues:
                report.append(f"\n{'-' * 60}")
                report.append(f"{category.upper()} ISSUES")
                report.append('-' * 60)
                
                for issue in category_issues[category]:
                    icon = '❌' if issue.type == 'error' else '⚠️' if issue.type == 'warning' else 'ℹ️'
                    service_tag = f"[{issue.service}] " if issue.service else ""
                    report.append(f"\n{icon} {service_tag}{issue.message}")
                    if issue.suggestion:
                        report.append(f"   💡 {issue.suggestion}")
                        
        # Summary
        report.append("\n" + "=" * 80)
        report.append("SUMMARY")
        report.append("=" * 80)
        
        critical_count = severity_counts.get('critical', 0)
        high_count = severity_counts.get('high', 0)
        
        if critical_count > 0:
            report.append(f"\n⚠️  {critical_count} CRITICAL issues found that must be fixed!")
        elif high_count > 0:
            report.append(f"\n⚠️  {high_count} HIGH severity issues found that should be addressed.")
        else:
            report.append("\n✅ No critical issues found.")
            
        return '\n'.join(report)
        
    def to_json(self) -> str:
        """Export validation results as JSON"""
        result = {
            'file': str(self.compose_file),
            'services': list(self.services.keys()),
            'networks': list(self.networks.keys()),
            'volumes': list(self.volumes.keys()),
            'issues': [
                {
                    'type': issue.type,
                    'severity': issue.severity,
                    'service': issue.service,
                    'category': issue.category,
                    'message': issue.message,
                    'suggestion': issue.suggestion,
                }
                for issue in self.issues
            ],
            'summary': {
                'total_issues': len(self.issues),
                'by_severity': dict(self._count_by_severity()),
                'by_category': dict(self._count_by_category()),
            }
        }
        
        return json.dumps(result, indent=2)
        
    def _count_by_severity(self) -> Dict[str, int]:
        """Count issues by severity"""
        counts = defaultdict(int)
        for issue in self.issues:
            counts[issue.severity] += 1
        return counts
        
    def _count_by_category(self) -> Dict[str, int]:
        """Count issues by category"""
        counts = defaultdict(int)
        for issue in self.issues:
            counts[issue.category] += 1
        return counts


def main():
    """CLI interface for the Docker Compose validator"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate Docker Compose configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate with all checks
  python docker_compose_validator.py docker-compose.yml
  
  # Only check networking issues
  python docker_compose_validator.py docker-compose.yml --only-networking
  
  # Skip security checks
  python docker_compose_validator.py docker-compose.yml --skip-security
  
  # Output as JSON
  python docker_compose_validator.py docker-compose.yml --json
  
  # Check multiple compose files
  python docker_compose_validator.py docker-compose.yml docker-compose.prod.yml
        """
    )
    
    parser.add_argument('compose_files', nargs='+', help='Docker Compose file(s) to validate')
    parser.add_argument('--json', action='store_true', help='Output results in JSON format')
    parser.add_argument('--only-networking', action='store_true', help='Only check networking issues')
    parser.add_argument('--only-security', action='store_true', help='Only check security issues')
    parser.add_argument('--only-resources', action='store_true', help='Only check resource issues')
    parser.add_argument('--only-volumes', action='store_true', help='Only check volume issues')
    parser.add_argument('--only-env', action='store_true', help='Only check environment variables')
    parser.add_argument('--skip-networking', action='store_true', help='Skip networking checks')
    parser.add_argument('--skip-security', action='store_true', help='Skip security checks')
    parser.add_argument('--skip-resources', action='store_true', help='Skip resource checks')
    parser.add_argument('--skip-volumes', action='store_true', help='Skip volume checks')
    parser.add_argument('--skip-env', action='store_true', help='Skip environment variable checks')
    parser.add_argument('--skip-best-practices', action='store_true', help='Skip best practices checks')
    
    args = parser.parse_args()
    
    # Determine which checks to run
    if any([args.only_networking, args.only_security, args.only_resources, args.only_volumes, args.only_env]):
        # If any "only" flag is set, disable all by default
        check_networking = args.only_networking
        check_security = args.only_security
        check_resources = args.only_resources
        check_volumes = args.only_volumes
        check_env = args.only_env
        check_best_practices = False
    else:
        # Otherwise, enable all except those skipped
        check_networking = not args.skip_networking
        check_security = not args.skip_security
        check_resources = not args.skip_resources
        check_volumes = not args.skip_volumes
        check_env = not args.skip_env
        check_best_practices = not args.skip_best_practices
        
    all_issues = []
    
    for compose_file in args.compose_files:
        validator = DockerComposeValidator(compose_file)
        issues = validator.validate(
            check_networking=check_networking,
            check_env_vars=check_env,
            check_security=check_security,
            check_resources=check_resources,
            check_volumes=check_volumes,
            check_best_practices=check_best_practices
        )
        
        if args.json:
            print(validator.to_json())
        else:
            print(validator.generate_report())
            if len(args.compose_files) > 1:
                print("\n" + "=" * 80 + "\n")
                
        all_issues.extend(issues)
        
    # Exit with error code if critical issues found
    critical_count = len([i for i in all_issues if i.severity == 'critical'])
    sys.exit(1 if critical_count > 0 else 0)


if __name__ == '__main__':
    main()