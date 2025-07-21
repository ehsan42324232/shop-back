# Domain Management System

This document explains the domain-based multi-store architecture and how to configure custom domains for stores.

## Overview

The platform supports multiple stores operating on different domains, allowing each store to have its own branded web presence while sharing the same infrastructure.

## Architecture

### Domain Resolution Flow

```
Customer Request → Nginx/Load Balancer → Domain Middleware → Store Context → Response
```

1. **Customer visits**: `mystore.com`
2. **Domain middleware** identifies the store based on domain
3. **Store context** is set for the request
4. **All data** is filtered by store context

### Domain Types

#### 1. Subdomain-based (Development)
- `store1.platform.local`
- `store2.platform.local`
- `admin.platform.local`

#### 2. Custom Domains (Production)
- `mystore.com`
- `anothershop.ir`
- `customdomain.net`

#### 3. Platform Domain
- `platform.com` (main platform)
- `platform.com/admin` (platform admin)

## Configuration

### 1. Store Domain Setup

```python
# models.py
class Store(models.Model):
    # ... other fields
    domain = models.CharField(max_length=255, unique=True)
    custom_domain = models.CharField(max_length=255, blank=True, null=True)
    ssl_enabled = models.BooleanField(default=False)
    domain_verified = models.BooleanField(default=False)
```

### 2. Domain Middleware

```python
# middleware.py
class DomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Extract domain from request
        host = request.get_host().split(':')[0]
        
        # Handle platform domain
        if host == settings.PLATFORM_DOMAIN:
            request.store = None
            request.is_platform = True
        else:
            # Find store by domain
            try:
                store = Store.objects.get(
                    models.Q(domain=host) | 
                    models.Q(custom_domain=host),
                    is_active=True
                )
                request.store = store
                request.is_platform = False
            except Store.DoesNotExist:
                # Handle unknown domain
                request.store = None
                request.is_platform = False
                
        response = self.get_response(request)
        return response
```

### 3. Settings Configuration

```python
# settings.py
PLATFORM_DOMAIN = 'platform.com'
ALLOWED_HOSTS = [
    'platform.com',
    '*.platform.com',
    'localhost',
    '127.0.0.1',
    # Add custom domains dynamically
]

# Middleware
MIDDLEWARE = [
    # ... other middleware
    'shop.middleware.DomainMiddleware',
    # ... rest of middleware
]
```

## Domain Management API

### Store Domain Endpoints

```python
# Store owner can update domain settings
PUT /api/store/domain/
{
    "custom_domain": "mystore.com",
    "ssl_enabled": true
}

# Verify domain ownership
POST /api/store/domain/verify/
{
    "domain": "mystore.com"
}

# Check domain availability
GET /api/store/domain/check/?domain=mystore.com

# Get domain status
GET /api/store/domain/status/
```

### Platform Admin Endpoints

```python
# List all domains
GET /api/admin/domains/

# Approve domain
POST /api/admin/domains/{id}/approve/

# Revoke domain
POST /api/admin/domains/{id}/revoke/
```

## DNS Configuration

### Required DNS Records

#### For Custom Domains

```dns
# A Record (for root domain)
mystore.com.    A    1.2.3.4

# CNAME (for www subdomain)
www.mystore.com.    CNAME    mystore.com.

# SSL Certificate validation (Let's Encrypt)
_acme-challenge.mystore.com.    TXT    "validation-token"
```

#### For Subdomain Setup

```dns
# Wildcard CNAME for all subdomains
*.platform.com.    CNAME    platform.com.

# Or individual CNAMEs
store1.platform.com.    CNAME    platform.com.
store2.platform.com.    CNAME    platform.com.
```

## Domain Verification

### Verification Methods

#### 1. DNS TXT Record

```python
def verify_dns_txt(domain, token):
    """Verify domain ownership via DNS TXT record"""
    import dns.resolver
    
    try:
        answers = dns.resolver.resolve(f'_platform-verification.{domain}', 'TXT')
        for rdata in answers:
            if token in str(rdata):
                return True
    except:
        pass
    return False
```

#### 2. HTML File Upload

```python
def verify_html_file(domain, token):
    """Verify domain ownership via HTML file"""
    import requests
    
    try:
        response = requests.get(f'http://{domain}/.well-known/platform-verification.html')
        return token in response.text
    except:
        return False
```

#### 3. Meta Tag Verification

```python
def verify_meta_tag(domain, token):
    """Verify domain ownership via meta tag"""
    import requests
    from bs4 import BeautifulSoup
    
    try:
        response = requests.get(f'http://{domain}')
        soup = BeautifulSoup(response.content, 'html.parser')
        meta_tag = soup.find('meta', {'name': 'platform-site-verification'})
        return meta_tag and token in meta_tag.get('content', '')
    except:
        return False
```

## SSL Certificate Management

### Automatic SSL with Let's Encrypt

```python
# Certificate management
class SSLCertificate(models.Model):
    store = models.OneToOneField(Store, on_delete=models.CASCADE)
    domain = models.CharField(max_length=255)
    certificate = models.TextField()
    private_key = models.TextField()
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)

def issue_ssl_certificate(domain):
    """Issue SSL certificate using Let's Encrypt"""
    # Integration with certbot or ACME client
    pass

def renew_expiring_certificates():
    """Automatically renew expiring certificates"""
    from datetime import timedelta
    
    expiring_soon = SSLCertificate.objects.filter(
        expires_at__lte=timezone.now() + timedelta(days=30),
        auto_renew=True
    )
    
    for cert in expiring_soon:
        try:
            issue_ssl_certificate(cert.domain)
        except Exception as e:
            # Log error and notify admins
            pass
```

## Nginx Configuration

### Dynamic Virtual Hosts

```nginx
# /etc/nginx/sites-available/platform
server {
    listen 80;
    listen 443 ssl http2;
    server_name ~^(?<subdomain>.+)\.platform\.com$;
    
    # SSL configuration
    ssl_certificate /path/to/wildcard-cert.pem;
    ssl_certificate_key /path/to/wildcard-key.pem;
    
    location / {
        proxy_pass http://django_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Custom domains
server {
    listen 80;
    listen 443 ssl http2;
    server_name mystore.com www.mystore.com;
    
    # SSL configuration for custom domain
    ssl_certificate /path/to/mystore-cert.pem;
    ssl_certificate_key /path/to/mystore-key.pem;
    
    location / {
        proxy_pass http://django_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Frontend Domain Handling

### Angular Domain Service

```typescript
@Injectable({
  providedIn: 'root'
})
export class DomainService {
  private currentDomain: string;
  private storeInfo: Store | null = null;

  constructor(private http: HttpClient) {
    this.currentDomain = window.location.hostname;
    this.loadStoreInfo();
  }

  getCurrentDomain(): string {
    return this.currentDomain;
  }

  getStoreInfo(): Observable<Store> {
    return this.http.get<Store>('/api/store/info/');
  }

  isPlatformDomain(): boolean {
    return this.currentDomain === environment.platformDomain;
  }

  isCustomDomain(): boolean {
    return !this.isPlatformDomain() && 
           !this.currentDomain.endsWith(environment.platformDomain);
  }

  getStoreDomainType(): 'platform' | 'subdomain' | 'custom' {
    if (this.isPlatformDomain()) {
      return 'platform';
    } else if (this.currentDomain.endsWith(environment.platformDomain)) {
      return 'subdomain';
    } else {
      return 'custom';
    }
  }
}
```

### Domain-based Routing

```typescript
// app-routing.module.ts
const routes: Routes = [
  {
    path: '',
    canActivate: [DomainGuard],
    children: [
      // Store routes (for store domains)
      {
        path: '',
        loadChildren: () => import('./store/store.module').then(m => m.StoreModule),
        data: { domain: 'store' }
      },
      // Platform routes (for platform domain)
      {
        path: 'admin',
        loadChildren: () => import('./admin/admin.module').then(m => m.AdminModule),
        data: { domain: 'platform' }
      }
    ]
  }
];
```

## Security Considerations

### 1. Domain Validation

- Verify domain ownership before activation
- Implement domain takeover protection
- Monitor for unauthorized domain changes

### 2. SSL/TLS Security

- Force HTTPS for all custom domains
- Implement HSTS headers
- Use strong SSL configurations

### 3. CORS Configuration

```python
# settings.py
CORS_ALLOWED_ORIGINS = [
    "https://platform.com",
    "https://mystore.com",
    # Add allowed origins dynamically
]

def get_allowed_origins():
    """Dynamically get allowed origins from active stores"""
    origins = [settings.PLATFORM_DOMAIN]
    
    for store in Store.objects.filter(is_active=True, domain_verified=True):
        if store.domain:
            origins.append(f"https://{store.domain}")
        if store.custom_domain:
            origins.append(f"https://{store.custom_domain}")
    
    return origins
```

## Monitoring and Analytics

### Domain Health Monitoring

```python
def monitor_domain_health():
    """Monitor domain accessibility and SSL status"""
    import requests
    import ssl
    import socket
    
    for store in Store.objects.filter(is_active=True):
        domain = store.custom_domain or store.domain
        
        # Check HTTP accessibility
        try:
            response = requests.get(f'https://{domain}', timeout=10)
            store.domain_accessible = response.status_code == 200
        except:
            store.domain_accessible = False
        
        # Check SSL certificate
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    store.ssl_valid = True
                    store.ssl_expires = parse_cert_expiry(cert)
        except:
            store.ssl_valid = False
        
        store.save()
```

## Migration and Deployment

### Adding Custom Domain to Existing Store

```python
def migrate_to_custom_domain(store, new_domain):
    """Migrate store from subdomain to custom domain"""
    
    # 1. Verify domain ownership
    if not verify_domain_ownership(new_domain):
        raise ValueError("Domain ownership verification failed")
    
    # 2. Issue SSL certificate
    ssl_cert = issue_ssl_certificate(new_domain)
    
    # 3. Update nginx configuration
    update_nginx_config(new_domain, ssl_cert)
    
    # 4. Update store domain
    store.custom_domain = new_domain
    store.domain_verified = True
    store.ssl_enabled = True
    store.save()
    
    # 5. Set up redirects from old domain
    setup_domain_redirect(store.domain, new_domain)
```

## Troubleshooting

### Common Issues

1. **Domain not resolving**
   - Check DNS configuration
   - Verify A/CNAME records

2. **SSL certificate issues**
   - Check certificate validity
   - Verify domain verification

3. **Store not found**
   - Check domain middleware configuration
   - Verify store domain settings

### Debug Commands

```bash
# Check DNS resolution
dig mystore.com
nslookup mystore.com

# Test SSL certificate
openssl s_client -connect mystore.com:443 -servername mystore.com

# Check nginx configuration
nginx -t
nginx -s reload
```

## Best Practices

1. **Domain Security**
   - Always verify domain ownership
   - Use strong SSL configurations
   - Monitor for domain hijacking

2. **Performance**
   - Use CDN for static assets
   - Implement proper caching
   - Monitor domain response times

3. **User Experience**
   - Provide clear domain setup instructions
   - Show domain verification status
   - Handle domain errors gracefully

4. **Maintenance**
   - Automate SSL certificate renewal
   - Monitor domain health
   - Regular security audits
