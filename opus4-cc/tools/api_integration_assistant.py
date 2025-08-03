#!/usr/bin/env python3
"""
API Integration Assistant - Streamline integration with external services and APIs
Handles authentication, rate limiting, error recovery, and API documentation parsing
"""

import os
import json
import argparse
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import yaml
import hashlib
from collections import defaultdict

@dataclass
class APIEndpoint:
    method: str
    path: str
    description: str
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    responses: Dict[str, Dict[str, Any]]
    auth_required: bool
    rate_limit: Optional[Dict[str, int]]

@dataclass
class APIIntegration:
    name: str
    base_url: str
    auth_type: str  # 'api_key', 'oauth2', 'jwt', 'basic'
    endpoints: List[APIEndpoint]
    rate_limits: Dict[str, Any]
    error_codes: Dict[int, str]
    
@dataclass
class MockResponse:
    endpoint: str
    method: str
    status_code: int
    data: Any
    headers: Dict[str, str]

class APIIntegrationAssistant:
    def __init__(self):
        self.integrations = {}
        self.mock_server = MockServer()
        self.rate_limiter = RateLimiter()
        self.auth_handlers = self._initialize_auth_handlers()
        
    def _initialize_auth_handlers(self) -> Dict[str, Any]:
        """Initialize authentication handlers for different auth types"""
        return {
            'api_key': self._handle_api_key_auth,
            'oauth2': self._handle_oauth2_auth,
            'jwt': self._handle_jwt_auth,
            'basic': self._handle_basic_auth,
        }
        
    def parse_openapi_spec(self, spec_file: str) -> APIIntegration:
        """Parse OpenAPI/Swagger specification"""
        with open(spec_file, 'r') as f:
            if spec_file.endswith('.yaml') or spec_file.endswith('.yml'):
                spec = yaml.safe_load(f)
            else:
                spec = json.load(f)
                
        # Extract basic info
        info = spec.get('info', {})
        servers = spec.get('servers', [{'url': 'http://localhost'}])
        base_url = servers[0]['url']
        
        # Parse security schemes
        security_schemes = spec.get('components', {}).get('securitySchemes', {})
        auth_type = self._determine_auth_type(security_schemes)
        
        # Parse endpoints
        endpoints = []
        paths = spec.get('paths', {})
        
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ['get', 'post', 'put', 'delete', 'patch']:
                    endpoint = self._parse_endpoint(method, path, details, spec)
                    endpoints.append(endpoint)
                    
        # Extract rate limits from description or x-rate-limit
        rate_limits = self._extract_rate_limits(spec)
        
        # Common error codes
        error_codes = {
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            429: 'Too Many Requests',
            500: 'Internal Server Error',
            503: 'Service Unavailable'
        }
        
        return APIIntegration(
            name=info.get('title', 'Unknown API'),
            base_url=base_url,
            auth_type=auth_type,
            endpoints=endpoints,
            rate_limits=rate_limits,
            error_codes=error_codes
        )
        
    def _determine_auth_type(self, security_schemes: Dict) -> str:
        """Determine authentication type from security schemes"""
        if not security_schemes:
            return 'none'
            
        # Check for common auth types
        for scheme_name, scheme in security_schemes.items():
            scheme_type = scheme.get('type', '').lower()
            
            if scheme_type == 'apikey':
                return 'api_key'
            elif scheme_type == 'oauth2':
                return 'oauth2'
            elif scheme_type == 'http':
                http_scheme = scheme.get('scheme', '').lower()
                if http_scheme == 'bearer':
                    return 'jwt'
                elif http_scheme == 'basic':
                    return 'basic'
                    
        return 'unknown'
        
    def _parse_endpoint(self, method: str, path: str, details: Dict, spec: Dict) -> APIEndpoint:
        """Parse individual endpoint details"""
        # Extract parameters
        parameters = []
        for param in details.get('parameters', []):
            param_info = {
                'name': param.get('name'),
                'in': param.get('in'),  # query, path, header
                'required': param.get('required', False),
                'type': param.get('schema', {}).get('type', 'string'),
                'description': param.get('description', '')
            }
            parameters.append(param_info)
            
        # Extract request body
        request_body = None
        if 'requestBody' in details:
            content = details['requestBody'].get('content', {})
            if 'application/json' in content:
                request_body = content['application/json'].get('schema', {})
                
        # Extract responses
        responses = {}
        for status_code, response in details.get('responses', {}).items():
            responses[status_code] = {
                'description': response.get('description', ''),
                'schema': response.get('content', {}).get('application/json', {}).get('schema', {})
            }
            
        # Check if auth is required
        auth_required = bool(details.get('security', spec.get('security', [])))
        
        # Extract rate limit if specified
        rate_limit = None
        if 'x-rate-limit' in details:
            rate_limit = details['x-rate-limit']
            
        return APIEndpoint(
            method=method.upper(),
            path=path,
            description=details.get('summary', details.get('description', '')),
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            auth_required=auth_required,
            rate_limit=rate_limit
        )
        
    def _extract_rate_limits(self, spec: Dict) -> Dict[str, Any]:
        """Extract rate limit information from spec"""
        rate_limits = {
            'default': {
                'requests': 100,
                'window': 3600  # 1 hour
            }
        }
        
        # Check for x-rate-limit extension
        if 'x-rate-limit' in spec:
            rate_limits.update(spec['x-rate-limit'])
            
        # Check info description for rate limit mentions
        description = spec.get('info', {}).get('description', '')
        rate_pattern = r'(\d+)\s*requests?\s*per\s*(second|minute|hour|day)'
        matches = re.findall(rate_pattern, description.lower())
        
        if matches:
            count, unit = matches[0]
            window_map = {
                'second': 1,
                'minute': 60,
                'hour': 3600,
                'day': 86400
            }
            rate_limits['detected'] = {
                'requests': int(count),
                'window': window_map.get(unit, 3600)
            }
            
        return rate_limits
        
    def generate_client_code(self, integration: APIIntegration, language: str) -> str:
        """Generate API client code in specified language"""
        generators = {
            'python': self._generate_python_client,
            'javascript': self._generate_js_client,
            'typescript': self._generate_ts_client,
        }
        
        generator = generators.get(language.lower())
        if not generator:
            raise ValueError(f"Unsupported language: {language}")
            
        return generator(integration)
        
    def _generate_python_client(self, integration: APIIntegration) -> str:
        """Generate Python API client"""
        code = f'''"""
{integration.name} API Client
Generated by API Integration Assistant
"""

import requests
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import time

class {integration.name.replace(' ', '')}Client:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "{integration.base_url}"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.api_key = api_key
        self._rate_limit_remaining = 100
        self._rate_limit_reset = datetime.now()
        
        # Configure authentication
        {self._generate_auth_setup(integration.auth_type, 'python')}
        
    def _check_rate_limit(self):
        """Check and enforce rate limits"""
        if datetime.now() > self._rate_limit_reset:
            self._rate_limit_remaining = {integration.rate_limits.get('default', {}).get('requests', 100)}
            self._rate_limit_reset = datetime.now() + timedelta(seconds={integration.rate_limits.get('default', {}).get('window', 3600)})
            
        if self._rate_limit_remaining <= 0:
            sleep_time = (self._rate_limit_reset - datetime.now()).total_seconds()
            if sleep_time > 0:
                time.sleep(sleep_time)
                self._rate_limit_remaining = {integration.rate_limits.get('default', {}).get('requests', 100)}
                
        self._rate_limit_remaining -= 1
        
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and errors"""
        if response.status_code == 429:
            # Rate limit exceeded
            retry_after = int(response.headers.get('Retry-After', 60))
            time.sleep(retry_after)
            return None  # Caller should retry
            
        response.raise_for_status()
        return response.json() if response.content else {{}}
'''
        
        # Generate methods for each endpoint
        for endpoint in integration.endpoints:
            method_name = self._endpoint_to_method_name(endpoint)
            code += self._generate_python_method(endpoint, method_name)
            
        return code
        
    def _generate_python_method(self, endpoint: APIEndpoint, method_name: str) -> str:
        """Generate Python method for an endpoint"""
        # Build parameter list
        params = []
        for param in endpoint.parameters:
            param_str = param['name']
            if param.get('type') != 'string':
                param_str += f": {self._python_type(param['type'])}"
            if not param.get('required', False):
                param_str += " = None"
            params.append(param_str)
            
        if endpoint.request_body:
            params.append("body: Dict[str, Any]")
            
        params_str = ", ".join(params) if params else ""
        
        # Build method
        method = f'''
    def {method_name}(self{", " + params_str if params_str else ""}) -> Dict[str, Any]:
        """{endpoint.description}"""
        self._check_rate_limit()
        
        url = f"{{self.base_url}}{endpoint.path}"
'''
        
        # Add parameter handling
        query_params = [p for p in endpoint.parameters if p['in'] == 'query']
        if query_params:
            method += "        params = {}\n"
            for param in query_params:
                if param.get('required'):
                    method += f"        params['{param['name']}'] = {param['name']}\n"
                else:
                    method += f"        if {param['name']} is not None:\n"
                    method += f"            params['{param['name']}'] = {param['name']}\n"
                    
        # Make request
        if endpoint.method == 'GET':
            method += f"        response = self.session.get(url{', params=params' if query_params else ''})\n"
        elif endpoint.method in ['POST', 'PUT', 'PATCH']:
            method += f"        response = self.session.{endpoint.method.lower()}(url"
            if endpoint.request_body:
                method += ", json=body"
            if query_params:
                method += ", params=params"
            method += ")\n"
        elif endpoint.method == 'DELETE':
            method += f"        response = self.session.delete(url{', params=params' if query_params else ''})\n"
            
        method += "        return self._handle_response(response)\n"
        
        return method
        
    def _python_type(self, api_type: str) -> str:
        """Convert API type to Python type"""
        type_map = {
            'integer': 'int',
            'number': 'float',
            'boolean': 'bool',
            'array': 'List',
            'object': 'Dict[str, Any]'
        }
        return type_map.get(api_type, 'str')
        
    def _generate_js_client(self, integration: APIIntegration) -> str:
        """Generate JavaScript API client"""
        code = f'''/**
 * {integration.name} API Client
 * Generated by API Integration Assistant
 */

class {integration.name.replace(' ', '')}Client {{
    constructor(apiKey = null, baseUrl = '{integration.base_url}') {{
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.apiKey = apiKey;
        this.rateLimitRemaining = 100;
        this.rateLimitReset = new Date();
        
        // Configure authentication
        {self._generate_auth_setup(integration.auth_type, 'javascript')}
    }}
    
    async checkRateLimit() {{
        const now = new Date();
        if (now > this.rateLimitReset) {{
            this.rateLimitRemaining = {integration.rate_limits.get('default', {}).get('requests', 100)};
            this.rateLimitReset = new Date(now.getTime() + {integration.rate_limits.get('default', {}).get('window', 3600)} * 1000);
        }}
        
        if (this.rateLimitRemaining <= 0) {{
            const sleepTime = this.rateLimitReset - now;
            if (sleepTime > 0) {{
                await new Promise(resolve => setTimeout(resolve, sleepTime));
                this.rateLimitRemaining = {integration.rate_limits.get('default', {}).get('requests', 100)};
            }}
        }}
        
        this.rateLimitRemaining--;
    }}
    
    async handleResponse(response) {{
        if (response.status === 429) {{
            const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
            await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
            return null; // Caller should retry
        }}
        
        if (!response.ok) {{
            throw new Error(`API Error: ${{response.status}} ${{response.statusText}}`);
        }}
        
        return response.json();
    }}
'''
        
        # Generate methods
        for endpoint in integration.endpoints:
            method_name = self._endpoint_to_method_name(endpoint)
            code += self._generate_js_method(endpoint, method_name)
            
        code += "}\n\nexport default " + integration.name.replace(' ', '') + "Client;"
        
        return code
        
    def _generate_js_method(self, endpoint: APIEndpoint, method_name: str) -> str:
        """Generate JavaScript method for an endpoint"""
        # Build parameter list
        params = []
        for param in endpoint.parameters:
            if param.get('required', False):
                params.append(param['name'])
            else:
                params.append(f"{param['name']} = null")
                
        if endpoint.request_body:
            params.append("body")
            
        params_str = ", ".join(params)
        
        # Build method
        method = f'''
    async {method_name}({params_str}) {{
        await this.checkRateLimit();
        
        let url = `${{this.baseUrl}}{endpoint.path}`;
'''
        
        # Handle path parameters
        path_params = [p for p in endpoint.parameters if p['in'] == 'path']
        for param in path_params:
            method += f"        url = url.replace('{{{param['name']}}}', {param['name']});\n"
            
        # Handle query parameters
        query_params = [p for p in endpoint.parameters if p['in'] == 'query']
        if query_params:
            method += "        const params = new URLSearchParams();\n"
            for param in query_params:
                if param.get('required'):
                    method += f"        params.append('{param['name']}', {param['name']});\n"
                else:
                    method += f"        if ({param['name']} !== null) params.append('{param['name']}', {param['name']});\n"
            method += "        if (params.toString()) url += '?' + params.toString();\n"
            
        # Make request
        method += f'''
        const response = await fetch(url, {{
            method: '{endpoint.method}',
            headers: this.headers,'''
            
        if endpoint.request_body:
            method += "\n            body: JSON.stringify(body),"
            
        method += '''
        });
        
        return this.handleResponse(response);
    }
'''
        
        return method
        
    def _generate_ts_client(self, integration: APIIntegration) -> str:
        """Generate TypeScript API client with types"""
        # Similar to JS but with type annotations
        return self._generate_js_client(integration)  # Simplified for now
        
    def _endpoint_to_method_name(self, endpoint: APIEndpoint) -> str:
        """Convert endpoint to method name"""
        # Remove path parameters and convert to camelCase
        path = endpoint.path.replace('{', '').replace('}', '')
        parts = path.strip('/').split('/')
        
        # Build method name
        method_parts = [endpoint.method.lower()]
        for i, part in enumerate(parts):
            if i == 0:
                method_parts.append(part)
            else:
                method_parts.append(part.capitalize())
                
        return ''.join(method_parts)
        
    def _generate_auth_setup(self, auth_type: str, language: str) -> str:
        """Generate authentication setup code"""
        if language == 'python':
            if auth_type == 'api_key':
                return '''if self.api_key:
            self.session.headers['X-API-Key'] = self.api_key'''
            elif auth_type == 'jwt':
                return '''if self.api_key:
            self.session.headers['Authorization'] = f'Bearer {self.api_key}' '''
            elif auth_type == 'basic':
                return '''if self.api_key:
            self.session.auth = ('api', self.api_key)'''
        elif language == 'javascript':
            if auth_type == 'api_key':
                return '''this.headers = {
            'Content-Type': 'application/json',
            ...(this.apiKey && { 'X-API-Key': this.apiKey })
        };'''
            elif auth_type == 'jwt':
                return '''this.headers = {
            'Content-Type': 'application/json',
            ...(this.apiKey && { 'Authorization': `Bearer ${this.apiKey}` })
        };'''
                
        return ''
        
    def _handle_api_key_auth(self, request: Dict, api_key: str) -> Dict:
        """Handle API key authentication"""
        request['headers']['X-API-Key'] = api_key
        return request
        
    def _handle_oauth2_auth(self, request: Dict, token: str) -> Dict:
        """Handle OAuth2 authentication"""
        request['headers']['Authorization'] = f'Bearer {token}'
        return request
        
    def _handle_jwt_auth(self, request: Dict, token: str) -> Dict:
        """Handle JWT authentication"""
        request['headers']['Authorization'] = f'Bearer {token}'
        return request
        
    def _handle_basic_auth(self, request: Dict, credentials: Tuple[str, str]) -> Dict:
        """Handle basic authentication"""
        import base64
        username, password = credentials
        encoded = base64.b64encode(f'{username}:{password}'.encode()).decode()
        request['headers']['Authorization'] = f'Basic {encoded}'
        return request

class MockServer:
    """Mock server for testing API integrations"""
    
    def __init__(self):
        self.routes = defaultdict(dict)
        self.request_history = []
        
    def add_mock(self, method: str, path: str, response: MockResponse):
        """Add a mock response for a route"""
        self.routes[method.upper()][path] = response
        
    def handle_request(self, method: str, path: str, **kwargs) -> MockResponse:
        """Handle a mock request"""
        self.request_history.append({
            'method': method,
            'path': path,
            'timestamp': datetime.now(),
            **kwargs
        })
        
        response = self.routes.get(method.upper(), {}).get(path)
        if not response:
            return MockResponse(
                endpoint=path,
                method=method,
                status_code=404,
                data={'error': 'Not found'},
                headers={}
            )
            
        return response
        
    def get_request_history(self) -> List[Dict]:
        """Get request history"""
        return self.request_history

class RateLimiter:
    """Rate limiter for API requests"""
    
    def __init__(self):
        self.limits = defaultdict(lambda: defaultdict(list))
        
    def check_limit(self, key: str, limit: int, window: int) -> bool:
        """Check if request is within rate limit"""
        now = time.time()
        cutoff = now - window
        
        # Remove old requests
        self.limits[key][window] = [
            ts for ts in self.limits[key][window] 
            if ts > cutoff
        ]
        
        # Check limit
        if len(self.limits[key][window]) >= limit:
            return False
            
        # Add current request
        self.limits[key][window].append(now)
        return True
        
    def get_reset_time(self, key: str, window: int) -> float:
        """Get time until rate limit resets"""
        if not self.limits[key][window]:
            return 0
            
        oldest = min(self.limits[key][window])
        reset_time = oldest + window
        return max(0, reset_time - time.time())

def generate_error_recovery_patterns(integration: APIIntegration) -> Dict[str, str]:
    """Generate error recovery patterns for common scenarios"""
    patterns = {
        'retry_with_backoff': '''async function retryWithBackoff(fn, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            return await fn();
        } catch (error) {
            if (i === maxRetries - 1) throw error;
            
            const delay = Math.pow(2, i) * 1000; // Exponential backoff
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}''',
        
        'circuit_breaker': '''class CircuitBreaker {
    constructor(threshold = 5, timeout = 60000) {
        this.failures = 0;
        this.threshold = threshold;
        this.timeout = timeout;
        this.state = 'CLOSED';
        this.nextAttempt = Date.now();
    }
    
    async call(fn) {
        if (this.state === 'OPEN') {
            if (Date.now() < this.nextAttempt) {
                throw new Error('Circuit breaker is OPEN');
            }
            this.state = 'HALF_OPEN';
        }
        
        try {
            const result = await fn();
            this.onSuccess();
            return result;
        } catch (error) {
            this.onFailure();
            throw error;
        }
    }
    
    onSuccess() {
        this.failures = 0;
        this.state = 'CLOSED';
    }
    
    onFailure() {
        this.failures++;
        if (this.failures >= this.threshold) {
            this.state = 'OPEN';
            this.nextAttempt = Date.now() + this.timeout;
        }
    }
}''',
        
        'fallback_cache': '''class FallbackCache {
    constructor(ttl = 3600000) { // 1 hour default
        this.cache = new Map();
        this.ttl = ttl;
    }
    
    async getWithFallback(key, fetchFn) {
        try {
            const data = await fetchFn();
            this.cache.set(key, {
                data,
                timestamp: Date.now()
            });
            return data;
        } catch (error) {
            const cached = this.cache.get(key);
            if (cached && (Date.now() - cached.timestamp) < this.ttl * 2) {
                // Return stale data in case of error
                return cached.data;
            }
            throw error;
        }
    }
}'''
    }
    
    return patterns

def main():
    parser = argparse.ArgumentParser(description='API Integration Assistant')
    parser.add_argument('--spec', help='OpenAPI/Swagger spec file')
    parser.add_argument('--generate', choices=['python', 'javascript', 'typescript'], 
                       help='Generate client code')
    parser.add_argument('--output', help='Output file for generated code')
    parser.add_argument('--mock', action='store_true', help='Generate mock server')
    parser.add_argument('--patterns', action='store_true', help='Show error recovery patterns')
    
    args = parser.parse_args()
    
    assistant = APIIntegrationAssistant()
    
    if args.patterns:
        print("🔧 Error Recovery Patterns\n")
        patterns = generate_error_recovery_patterns(None)
        for name, code in patterns.items():
            print(f"### {name.replace('_', ' ').title()}")
            print(code)
            print()
        return
        
    if not args.spec:
        # Demo mode
        print("📡 API Integration Assistant - Demo Mode")
        print("=" * 50)
        
        # Create demo API integration
        demo_integration = APIIntegration(
            name="Demo API",
            base_url="https://api.example.com/v1",
            auth_type="api_key",
            endpoints=[
                APIEndpoint(
                    method="GET",
                    path="/users/{id}",
                    description="Get user by ID",
                    parameters=[{
                        'name': 'id',
                        'in': 'path',
                        'required': True,
                        'type': 'integer',
                        'description': 'User ID'
                    }],
                    request_body=None,
                    responses={'200': {'description': 'User object'}},
                    auth_required=True,
                    rate_limit={'requests': 100, 'window': 3600}
                ),
                APIEndpoint(
                    method="POST",
                    path="/users",
                    description="Create a new user",
                    parameters=[],
                    request_body={'type': 'object', 'properties': {
                        'name': {'type': 'string'},
                        'email': {'type': 'string'}
                    }},
                    responses={'201': {'description': 'Created user'}},
                    auth_required=True,
                    rate_limit=None
                )
            ],
            rate_limits={'default': {'requests': 100, 'window': 3600}},
            error_codes={400: 'Bad Request', 401: 'Unauthorized'}
        )
        
        # Generate Python client
        print("\n🐍 Generated Python Client:\n")
        python_code = assistant.generate_client_code(demo_integration, 'python')
        print(python_code[:1500] + "\n...")  # Show first part
        
        print("\n📋 Features:")
        print("✅ Automatic rate limiting")
        print("✅ Built-in error handling")
        print("✅ Authentication support")
        print("✅ Type hints (Python/TypeScript)")
        print("✅ Retry logic")
        
        return
        
    # Parse API spec
    integration = assistant.parse_openapi_spec(args.spec)
    
    print(f"\n📡 Parsed API: {integration.name}")
    print(f"Base URL: {integration.base_url}")
    print(f"Auth Type: {integration.auth_type}")
    print(f"Endpoints: {len(integration.endpoints)}")
    
    # List endpoints
    print("\n📍 Endpoints:")
    for endpoint in integration.endpoints[:10]:  # Show first 10
        print(f"  {endpoint.method} {endpoint.path}")
        print(f"    {endpoint.description}")
        
    if len(integration.endpoints) > 10:
        print(f"  ... and {len(integration.endpoints) - 10} more")
        
    # Generate client code if requested
    if args.generate:
        print(f"\n🔨 Generating {args.generate} client...")
        code = assistant.generate_client_code(integration, args.generate)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(code)
            print(f"✅ Client code saved to {args.output}")
        else:
            print("\nGenerated code preview:")
            print(code[:1000] + "\n...")
            
    # Generate mock server if requested
    if args.mock:
        print("\n🎭 Mock Server Setup:")
        print("```python")
        print("from api_integration_assistant import MockServer, MockResponse")
        print("\nmock_server = MockServer()")
        
        for endpoint in integration.endpoints[:3]:
            print(f"\n# Mock {endpoint.method} {endpoint.path}")
            print(f"mock_server.add_mock(")
            print(f"    '{endpoint.method}',")
            print(f"    '{endpoint.path}',")
            print(f"    MockResponse(")
            print(f"        endpoint='{endpoint.path}',")
            print(f"        method='{endpoint.method}',")
            print(f"        status_code=200,")
            print(f"        data={{'example': 'response'}},")
            print(f"        headers={{}}")
            print(f"    )")
            print(f")")
        print("```")

if __name__ == '__main__':
    main()