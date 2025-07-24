"""
Domain Management System for Independent Store Domains
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.db import transaction
import requests
import logging

from .models import Store
from .domain_models import StoreDomain, DomainRecord
from .authentication import MallTokenAuthentication

logger = logging.getLogger(__name__)

class DomainSetupView(APIView):
    """
    Setup custom domain for store
    """
    authentication_classes = [MallTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Setup custom domain for store
        
        Expected payload:
        {
            "store_id": 123,
            "domain": "mystore.com",
            "subdomain": "shop",
            "domain_type": "custom|subdomain"
        }
        """
        try:
            store_id = request.data.get('store_id')
            domain = request.data.get('domain', '').strip().lower()
            subdomain = request.data.get('subdomain', '').strip().lower()
            domain_type = request.data.get('domain_type', 'subdomain')

            # Get store
            try:
                store = Store.objects.get(id=store_id, owner=request.user)
            except Store.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'فروشگاه یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)

            # Validate domain
            if domain_type == 'custom':
                if not domain or not self._is_valid_domain(domain):
                    return Response({
                        'success': False,
                        'message': 'دامنه وارد شده معتبر نیست'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                final_domain = domain
            else:
                if not subdomain:
                    return Response({
                        'success': False,
                        'message': 'زیردامنه الزامی است'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                final_domain = f"{subdomain}.{settings.PLATFORM_DOMAIN}"

            # Check if domain already exists
            if StoreDomain.objects.filter(domain=final_domain).exists():
                return Response({
                    'success': False,
                    'message': 'این دامنه قبلاً استفاده شده است'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create domain record
            with transaction.atomic():
                store_domain = StoreDomain.objects.create(
                    store=store,
                    domain=final_domain,
                    domain_type=domain_type,
                    is_primary=True,
                    status='pending'
                )

                # Deactivate previous primary domain
                StoreDomain.objects.filter(
                    store=store,
                    is_primary=True
                ).exclude(id=store_domain.id).update(is_primary=False)

                # Setup DNS records
                if domain_type == 'custom':
                    dns_setup = self._setup_custom_domain_dns(final_domain)
                else:
                    dns_setup = self._setup_subdomain_dns(subdomain)

                if dns_setup['success']:
                    store_domain.status = 'active'
                    store_domain.save()

                    return Response({
                        'success': True,
                        'message': 'دامنه با موفقیت تنظیم شد',
                        'data': {
                            'domain': final_domain,
                            'type': domain_type,
                            'status': 'active',
                            'dns_records': dns_setup.get('dns_records', [])
                        }
                    })
                else:
                    store_domain.status = 'failed'
                    store_domain.error_message = dns_setup.get('message', 'خطا در تنظیم DNS')
                    store_domain.save()

                    return Response({
                        'success': False,
                        'message': dns_setup.get('message', 'خطا در تنظیم دامنه'),
                        'dns_instructions': dns_setup.get('instructions', [])
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Domain setup error: {e}")
            return Response({
                'success': False,
                'message': 'خطا در تنظیم دامنه'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _is_valid_domain(self, domain):
        """
        Validate domain format
        """
        import re
        domain_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$'
        return re.match(domain_pattern, domain) is not None

    def _setup_custom_domain_dns(self, domain):
        """
        Setup DNS for custom domain
        """
        try:
            # Create DNS records
            dns_records = [
                {
                    'type': 'A',
                    'name': '@',
                    'value': settings.SERVER_IP,
                    'ttl': 300
                },
                {
                    'type': 'CNAME',
                    'name': 'www',
                    'value': domain,
                    'ttl': 300
                }
            ]

            # For production, integrate with DNS provider API
            # For now, return manual instructions
            return {
                'success': True,
                'dns_records': dns_records,
                'instructions': [
                    f'رکورد A با نام @ و مقدار {settings.SERVER_IP} اضافه کنید',
                    f'رکورد CNAME با نام www و مقدار {domain} اضافه کنید'
                ]
            }

        except Exception as e:
            return {
                'success': False,
                'message': 'خطا در تنظیم DNS سفارشی'
            }

    def _setup_subdomain_dns(self, subdomain):
        """
        Setup DNS for subdomain
        """
        try:
            # Subdomain setup (handled by platform)
            full_domain = f"{subdomain}.{settings.PLATFORM_DOMAIN}"
            
            # Create internal DNS record
            DomainRecord.objects.create(
                domain=full_domain,
                record_type='CNAME',
                name=subdomain,
                value=settings.PLATFORM_DOMAIN,
                ttl=300
            )

            return {
                'success': True,
                'dns_records': [{
                    'type': 'CNAME',
                    'name': subdomain,
                    'value': settings.PLATFORM_DOMAIN,
                    'ttl': 300
                }]
            }

        except Exception as e:
            return {
                'success': False,
                'message': 'خطا در تنظیم زیردامنه'
            }

class DomainStatusView(APIView):
    """
    Check domain status and verification
    """
    authentication_classes = [MallTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, domain_id):
        """
        Get domain status
        """
        try:
            store_domain = StoreDomain.objects.get(
                id=domain_id,
                store__owner=request.user
            )

            # Check domain connectivity
            verification = self._verify_domain(store_domain.domain)

            return Response({
                'success': True,
                'data': {
                    'domain': store_domain.domain,
                    'status': store_domain.status,
                    'type': store_domain.domain_type,
                    'is_primary': store_domain.is_primary,
                    'verification': verification,
                    'created_at': store_domain.created_at,
                    'ssl_status': self._check_ssl_status(store_domain.domain)
                }
            })

        except StoreDomain.DoesNotExist:
            return Response({
                'success': False,
                'message': 'دامنه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)

    def _verify_domain(self, domain):
        """
        Verify domain is pointing to our servers
        """
        try:
            import socket
            ip = socket.gethostbyname(domain)
            is_pointing = ip == settings.SERVER_IP
            
            return {
                'is_pointing': is_pointing,
                'current_ip': ip,
                'expected_ip': settings.SERVER_IP,
                'status': 'verified' if is_pointing else 'not_pointing'
            }
        except Exception:
            return {
                'is_pointing': False,
                'status': 'dns_error'
            }

    def _check_ssl_status(self, domain):
        """
        Check SSL certificate status
        """
        try:
            import ssl
            import socket
            
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    return {
                        'has_ssl': True,
                        'issuer': cert.get('issuer', []),
                        'expires': cert.get('notAfter'),
                        'subject': cert.get('subject', [])
                    }
        except Exception:
            return {
                'has_ssl': False,
                'status': 'no_ssl'
            }