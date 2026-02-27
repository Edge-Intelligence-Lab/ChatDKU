from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
import time
import logging

class RateLimitMiddleware:
    """
    Rate limiting middleware - only applies to users already authenticated by NetIDMiddleware.
    
    Core Principle: Users without NetID have already been rejected by NetIDMiddleware
    and will never reach this middleware.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('app')
        
        # Different restrictions among different API calls
        self.rate_limits = {
            'default': {
                'requests': getattr(settings, 'RATE_LIMIT_DEFAULT', 60),
                'window': getattr(settings, 'RATE_LIMIT_WINDOW', 60),
            },
            'api': {
                'requests': getattr(settings, 'RATE_LIMIT_API', 50),
                'window': getattr(settings, 'RATE_LIMIT_WINDOW', 60),
            },
            'strict': {
                'requests': getattr(settings, 'RATE_LIMIT_STRICT', 20),
                'window': getattr(settings, 'RATE_LIMIT_STRICT_WINDOW', 30),
            }
        }
        
        # Exempt paths (no rate limiting)
        self.exempt_paths = getattr(settings, 'RATE_LIMIT_EXEMPT_PATHS', [
            '/admin/',
            '/static/',
            '/media/',
            '/health/',
            '/docs/',
            '/metrics',  "metrics added"
        ])
        
        # Path to rate limit type mapping
        self.path_limits = getattr(settings, 'RATE_LIMIT_PATH_MAPPINGS', {
            '/api/': 'api',
            '/chat/': 'api',
            '/query/': 'api',
            '/upload/': 'strict',
            '/scrape/': 'strict',
            '/batch/': 'strict',
        })

    def extract_netid(self, request):
        """
        Extract NetID from request.
    
        Assumption: NetIDMiddleware has already verified and set the netid.
    
        Args:
            request: Django HttpRequest object
        
        Returns:
            str: The NetID (guaranteed to exist)
        """
        # NetIDMiddleware sets request.netid for all authenticated requests
        netid = getattr(request, 'netid', None)
    
        # Also check session as backup (set by NetIDMiddleware)
        if not netid and hasattr(request, 'session'):
            netid = request.session.get("netid")
    
        # At this point, netid should always exist
        # If it doesn't, it's a system error that should be investigated
        return netid

    def _get_client_ip(self, request):
        """
        Get client IP address (for logging purposes only).
        
        Args:
            request: Django HttpRequest object
            
        Returns:
            str: Client IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    def get_limit_type_for_path(self, path):
        """
        Determine rate limit type based on API endpoint path.
        
        Args:
            path: Request path (e.g., '/api/chat/', '/upload/file/')
            
        Returns:
            str: Rate limit type - 'api', 'strict', or 'default'
        """
        for path_prefix, limit_type in self.path_limits.items():
            if path.startswith(path_prefix):
                return limit_type
        return 'default'

    def is_path_exempt(self, path):
        """
        Check if path is exempt from rate limiting.
        
        Args:
            path: Request path
            
        Returns:
            bool: True if path is exempt, False otherwise
        """
        for exempt_path in self.exempt_paths:
            if path.startswith(exempt_path):
                return True
        return False

    def check_rate_limit(self, netid, path, limit_type):
        """
        Execute rate limit check using sliding window algorithm.
    
        Important: netid is guaranteed to exist (validated by NetIDMiddleware).
    
        Args:
            netid: User NetID (guaranteed to exist)
            path: Request path
            limit_type: Type of rate limit ('default', 'api', 'strict')
            
        Returns:
            tuple: (allowed, retry_after)
                - allowed: Boolean indicating if request is allowed
                - retry_after: Seconds to wait before retry (if not allowed)
        """
        config = self.rate_limits[limit_type]
        window = config['window']
        max_requests = config['requests']
    
        # Use sliding window algorithm
        current_time = int(time.time())
        window_key = current_time // window

        # Generate cache key
        cache_key = f'ratelimit:{netid}:{path}:{limit_type}:{window_key}'
    
        # Get current count
        current_count = cache.get(cache_key, 0)
    
        if current_count >= max_requests:
            # Calculate remaining time
            reset_time = (window_key + 1) * window
            retry_after = reset_time - current_time
            return False, retry_after
    
        # Increment count
        if current_count == 0:
            cache.set(cache_key, 1, timeout=window * 2)
        else:
            cache.incr(cache_key)
    
        return True, None

    def __call__(self, request):
        """
        Middleware entry point - called for each request.
    
        Args:
            request: Django HttpRequest object
        
        Returns:
            HttpResponse: Processed response
        """

        # 1. Check if path is exempt
        if self.is_path_exempt(request.path):
            return self.get_response(request)
    
        # 2. Extract NetID (guaranteed to exist)
        netid = self.extract_netid(request)
    
        # 3. Determine limit type
        limit_type = self.get_limit_type_for_path(request.path)
    
        # 4. Check rate limit
        allowed, retry_after = self.check_rate_limit(netid, request.path, limit_type)
    
        if not allowed:
            # Log rate limit event
            self.logger.warning(
                f"Rate limit exceeded: netid={netid}, "
                f"path={request.path}, limit_type={limit_type}"
            )
        
            return JsonResponse({
                "error": "rate_limit_exceeded",
                "message": f"Too many requests. Please try again in {retry_after} seconds.",
                "retry_after": retry_after,
                "limit": self.rate_limits[limit_type]['requests'],
                "window": self.rate_limits[limit_type]['window'],
            }, status=429)
    
        # 5. Process request
        response = self.get_response(request)
    
        # 6. Add rate limit headers
        config = self.rate_limits[limit_type]
        current_time = int(time.time())
        window_key = current_time // config['window']
        cache_key = f'ratelimit:{netid}:{request.path}:{limit_type}:{window_key}'
        current_count = cache.get(cache_key, 0)
    
        response['X-RateLimit-Limit'] = str(config['requests'])
        response['X-RateLimit-Remaining'] = str(max(0, config['requests'] - current_count))
        response['X-RateLimit-Reset'] = str((window_key + 1) * config['window'])
        response['X-RateLimit-Policy'] = f'{config["requests"]};w={config["window"]}'
    
        return response
