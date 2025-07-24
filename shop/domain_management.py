# shop/domain_management.py
"""
Mall Platform - Independent Domain Management
Custom domain configuration for store owners
"""
from django.db import models
from django.contrib.auth.models import User
import ssl
import socket
import dns.resolver
import requests
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class StoreDomain(models.Model):
    """Store custom domain management"""
    DOMAIN_STATUS = [
        ('pending', 'در انتظار تایید'),
        ('active', 'فعال'),
        ('inactive', 'غیرفعال'),
        ('failed', 'ناموفق'),
        ('expired', 'منقضی شده')
    ]
    
    store = models.OneToOneField('Store', on_delete=models.CASCADE, related_name='custom_domain')
    domain_name = models.CharField(max_length=255, unique=True, verbose_name='نام دامنه')
    subdomain = models.CharField(max_length=100, blank=True, verbose_name='زیردامنه')
    
    # SSL Configuration
    ssl_enabled = models.BooleanField(default=False, verbose_name='SSL فعال')
    ssl_certificate = models.TextField(blank=True, verbose_name='گواهی SSL')
    ssl_private_key = models.TextField(blank=True, verbose_name='کلید خصوصی SSL')
    ssl_expires_at = models.DateTimeField(null=True, blank=True, verbose_name='انقضای SSL')
    
    # Domain Status
    status = models.CharField(max_length=20, choices=DOMAIN_STATUS, default='pending')
    dns_configured = models.BooleanField(default=False, verbose_name='DNS پیکربندی شده')
    last_checked = models.DateTimeField(auto_now=True)
    
    # Configuration
    redirect_www = models.BooleanField(default=True, verbose_name='هدایت WWW')
    force_https = models.BooleanField(default=True, verbose_name='اجبار HTTPS')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'دامنه فروشگاه'
        verbose_name_plural = 'دامنه‌های فروشگاه'
    
    def __str__(self):
        return f"{self.domain_name} - {self.store.name}"
    
    def get_full_domain(self):
        """Get full domain with subdomain"""
        if self.subdomain:
            return f"{self.subdomain}.{self.domain_name}"
        return self.domain_name
    
    def check_dns_configuration(self) -> Dict[str, Any]:
        """Check DNS configuration"""
        try:
            domain = self.get_full_domain()
            
            # Check A record
            a_records = dns.resolver.resolve(domain, 'A')
            a_record_ips = [str(record) for record in a_records]
            
            # Check CNAME if subdomain
            cname_records = []
            if self.subdomain:
                try:
                    cname_records = dns.resolver.resolve(domain, 'CNAME')
                    cname_records = [str(record) for record in cname_records]
                except:
                    pass
            
            # Expected IP (your server IP)
            expected_ip = "YOUR_SERVER_IP"  # Configure this
            
            dns_correct = expected_ip in a_record_ips or any('mall.ir' in cname for cname in cname_records)
            
            return {
                'success': True,
                'dns_configured': dns_correct,
                'a_records': a_record_ips,
                'cname_records': cname_records,
                'expected_ip': expected_ip
            }
            
        except Exception as e:
            logger.error(f"DNS check error for {domain}: {e}")
            return {
                'success': False,
                'error': str(e),
                'dns_configured': False
            }
    
    def check_ssl_status(self) -> Dict[str, Any]:
        """Check SSL certificate status"""
        try:
            domain = self.get_full_domain()
            
            # Get SSL certificate info
            context = ssl.create_default_context()
            sock = socket.create_connection((domain, 443), timeout=10)
            ssock = context.wrap_socket(sock, server_hostname=domain)
            cert = ssock.getpeercert()
            ssock.close()
            
            # Check expiration
            import datetime
            expire_date = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            days_until_expire = (expire_date - datetime.datetime.now()).days
            
            return {
                'success': True,
                'ssl_valid': True,
                'issuer': cert.get('issuer', [{}])[0].get('organizationName', 'Unknown'),
                'expires': expire_date,
                'days_until_expire': days_until_expire,
                'subject': cert.get('subject', [{}])[0].get('commonName', domain)
            }
            
        except Exception as e:
            logger.error(f"SSL check error for {domain}: {e}")
            return {
                'success': False,
                'ssl_valid': False,
                'error': str(e)
            }
    
    def verify_domain_ownership(self) -> Dict[str, Any]:
        """Verify domain ownership via file verification"""
        try:
            domain = self.get_full_domain()
            verification_code = f"mall-verification-{self.store.id}"
            verification_url = f"http://{domain}/.well-known/mall-verification.txt"
            
            response = requests.get(verification_url, timeout=10)
            
            if response.status_code == 200 and verification_code in response.text:
                return {
                    'success': True,
                    'verified': True,
                    'method': 'file_verification'
                }
            else:
                return {
                    'success': False,
                    'verified': False,
                    'error': 'فایل تایید یافت نشد یا محتوای آن صحیح نیست'
                }
                
        except Exception as e:
            logger.error(f"Domain verification error: {e}")
            return {
                'success': False,
                'verified': False,
                'error': str(e)
            }
    
    def update_status(self):
        """Update domain status based on checks"""
        dns_result = self.check_dns_configuration()
        
        if dns_result['success'] and dns_result['dns_configured']:
            ssl_result = self.check_ssl_status()
            
            if ssl_result['success'] and ssl_result['ssl_valid']:
                self.status = 'active'
                self.ssl_enabled = True
            else:
                self.status = 'active'  # HTTP only
                self.ssl_enabled = False
            
            self.dns_configured = True
        else:
            self.status = 'failed'
            self.dns_configured = False
        
        self.save()


class DomainVerification(models.Model):
    """Domain ownership verification"""
    VERIFICATION_METHODS = [
        ('file', 'فایل HTML'),
        ('dns', 'رکورد DNS'),
        ('email', 'ایمیل'),
        ('meta_tag', 'متا تگ')
    ]
    
    domain = models.ForeignKey(StoreDomain, on_delete=models.CASCADE, related_name='verifications')
    method = models.CharField(max_length=20, choices=VERIFICATION_METHODS)
    verification_code = models.CharField(max_length=255)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'تایید دامنه'
        verbose_name_plural = 'تایید دامنه‌ها'


class DomainSSLCertificate(models.Model):
    """SSL Certificate management"""
    CERT_PROVIDERS = [
        ('letsencrypt', "Let's Encrypt"),
        ('custom', 'سفارشی'),
        ('cloudflare', 'Cloudflare')
    ]
    
    domain = models.OneToOneField(StoreDomain, on_delete=models.CASCADE, related_name='ssl_cert')
    provider = models.CharField(max_length=20, choices=CERT_PROVIDERS, default='letsencrypt')
    certificate_data = models.TextField()
    private_key_data = models.TextField()
    chain_data = models.TextField(blank=True)
    
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    def days_until_expiry(self):
        from django.utils import timezone
        delta = self.expires_at - timezone.now()
        return delta.days


def get_available_subdomains() -> list:
    """Get list of available subdomains"""
    return [
        'shop', 'store', 'market', 'mall', 'buy', 'sell', 
        'online', 'web', 'digital', 'bazaar', 'outlet'
    ]


def suggest_domain_name(store_name: str) -> list:
    """Suggest domain names based on store name"""
    import re
    
    # Clean store name
    clean_name = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF]', '', store_name.lower())
    
    suggestions = []
    
    # Direct name
    suggestions.append(f"{clean_name}.com")
    suggestions.append(f"{clean_name}.ir")
    
    # With prefixes
    prefixes = ['shop', 'store', 'my', 'online']
    for prefix in prefixes:
        suggestions.append(f"{prefix}{clean_name}.com")
        suggestions.append(f"{prefix}{clean_name}.ir")
    
    # With suffixes
    suffixes = ['shop', 'store', 'online', 'market']
    for suffix in suffixes:
        suggestions.append(f"{clean_name}{suffix}.com")
        suggestions.append(f"{clean_name}{suffix}.ir")
    
    return suggestions[:10]  # Return top 10 suggestions


def check_domain_availability(domain_name: str) -> Dict[str, Any]:
    """Check if domain is available (simplified)"""
    try:
        # Try to resolve domain
        dns.resolver.resolve(domain_name, 'A')
        return {
            'available': False,
            'status': 'registered',
            'message': 'دامنه قبلاً ثبت شده است'
        }
    except dns.resolver.NXDOMAIN:
        return {
            'available': True,
            'status': 'available',
            'message': 'دامنه در دسترس است'
        }
    except Exception as e:
        return {
            'available': None,
            'status': 'error',
            'message': f'خطا در بررسی دامنه: {str(e)}'
        }
