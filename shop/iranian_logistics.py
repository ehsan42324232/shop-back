# shop/iranian_logistics.py
"""
Mall Platform - Iranian Logistics Integration
Integration with major Iranian shipping providers
"""
import requests
import logging
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.conf import settings
import json

logger = logging.getLogger(__name__)

class LogisticsProviderBase:
    """Base class for logistics providers"""
    
    def __init__(self, api_key: str, sandbox: bool = True):
        self.api_key = api_key
        self.sandbox = sandbox
        
    def calculate_shipping_cost(self, from_city: str, to_city: str, weight: float, **kwargs) -> Dict[str, Any]:
        """Calculate shipping cost"""
        raise NotImplementedError
        
    def create_shipment(self, shipment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create shipment"""
        raise NotImplementedError
        
    def track_shipment(self, tracking_number: str) -> Dict[str, Any]:
        """Track shipment"""
        raise NotImplementedError


class PostCompanyProvider(LogisticsProviderBase):
    """Iranian Post Company integration"""
    
    def __init__(self, api_key: str, sandbox: bool = True):
        super().__init__(api_key, sandbox)
        self.base_url = "https://api.post.ir" if not sandbox else "https://sandbox.post.ir"
        
    def calculate_shipping_cost(self, from_city: str, to_city: str, weight: float, **kwargs) -> Dict[str, Any]:
        """Calculate Post shipping cost"""
        try:
            # Convert weight to grams
            weight_grams = int(weight * 1000)
            
            # Post pricing based on zones and weight
            base_cost = self._get_base_cost(from_city, to_city, weight_grams)
            
            return {
                'success': True,
                'provider': 'post',
                'cost': base_cost,
                'delivery_days': self._get_delivery_days(from_city, to_city),
                'service_type': 'standard',
                'description': 'پست ایران - ارسال عادی'
            }
            
        except Exception as e:
            logger.error(f"Post shipping cost error: {e}")
            return {
                'success': False,
                'error': 'خطا در محاسبه هزینه پست'
            }
    
    def _get_base_cost(self, from_city: str, to_city: str, weight_grams: int) -> int:
        """Calculate base cost for Post"""
        # Simplified pricing - in reality would use Post API
        same_province = self._same_province(from_city, to_city)
        
        if weight_grams <= 500:
            return 15000 if same_province else 25000
        elif weight_grams <= 1000:
            return 20000 if same_province else 35000
        elif weight_grams <= 2000:
            return 30000 if same_province else 50000
        else:
            # Additional cost per kg
            extra_kg = (weight_grams - 2000) // 1000
            base = 30000 if same_province else 50000
            return base + (extra_kg * (10000 if same_province else 15000))
    
    def _get_delivery_days(self, from_city: str, to_city: str) -> int:
        """Estimate delivery days"""
        same_province = self._same_province(from_city, to_city)
        return 2 if same_province else 5
    
    def _same_province(self, city1: str, city2: str) -> bool:
        """Check if cities are in same province - simplified"""
        # In real implementation, would use geographic database
        major_cities = {
            'تهران': 'تهران', 'کرج': 'البرز', 'اصفهان': 'اصفهان',
            'مشهد': 'خراسان رضوی', 'شیراز': 'فارس', 'تبریز': 'آذربایجان شرقی'
        }
        return major_cities.get(city1) == major_cities.get(city2)


class TipaxProvider(LogisticsProviderBase):
    """Tipax logistics integration"""
    
    def __init__(self, api_key: str, sandbox: bool = True):
        super().__init__(api_key, sandbox)
        self.base_url = "https://api.tipax.com" if not sandbox else "https://sandbox.tipax.com"
        
    def calculate_shipping_cost(self, from_city: str, to_city: str, weight: float, **kwargs) -> Dict[str, Any]:
        """Calculate Tipax shipping cost"""
        try:
            service_type = kwargs.get('service_type', 'normal')
            
            data = {
                'origin_city': from_city,
                'destination_city': to_city,
                'weight': weight,
                'service_type': service_type
            }
            
            # Simulate API call
            cost = self._calculate_tipax_cost(from_city, to_city, weight, service_type)
            
            return {
                'success': True,
                'provider': 'tipax',
                'cost': cost,
                'delivery_days': 1 if service_type == 'express' else 3,
                'service_type': service_type,
                'description': f'تیپاکس - {"فوری" if service_type == "express" else "عادی"}'
            }
            
        except Exception as e:
            logger.error(f"Tipax shipping cost error: {e}")
            return {
                'success': False,
                'error': 'خطا در محاسبه هزینه تیپاکس'
            }
    
    def _calculate_tipax_cost(self, from_city: str, to_city: str, weight: float, service_type: str) -> int:
        """Calculate Tipax cost"""
        base_cost = 35000 if service_type == 'express' else 25000
        
        # Weight-based pricing
        if weight <= 1:
            weight_cost = 0
        elif weight <= 5:
            weight_cost = (weight - 1) * 8000
        else:
            weight_cost = 4 * 8000 + (weight - 5) * 12000
        
        # Distance factor
        distance_factor = 1.5 if not self._same_city_cluster(from_city, to_city) else 1.0
        
        return int((base_cost + weight_cost) * distance_factor)
    
    def _same_city_cluster(self, city1: str, city2: str) -> bool:
        """Check if cities are in same cluster"""
        clusters = [
            ['تهران', 'کرج', 'ورامین'],
            ['اصفهان', 'نجف‌آباد', 'خمینی‌شهر'],
            ['مشهد', 'نیشابور']
        ]
        
        for cluster in clusters:
            if city1 in cluster and city2 in cluster:
                return True
        return False


class SnapExpressProvider(LogisticsProviderBase):
    """Snap Express (اسنپ اکسپرس) integration"""
    
    def __init__(self, api_key: str, sandbox: bool = True):
        super().__init__(api_key, sandbox)
        self.base_url = "https://api.snapp.express" if not sandbox else "https://sandbox.snapp.express"
        
    def calculate_shipping_cost(self, from_city: str, to_city: str, weight: float, **kwargs) -> Dict[str, Any]:
        """Calculate Snap Express shipping cost"""
        try:
            # Snap Express is mainly for same-day delivery in major cities
            if not self._supports_route(from_city, to_city):
                return {
                    'success': False,
                    'error': 'این مسیر توسط اسنپ اکسپرس پشتیبانی نمی‌شود'
                }
            
            service_type = kwargs.get('service_type', 'standard')
            cost = self._calculate_snap_cost(from_city, to_city, weight, service_type)
            
            return {
                'success': True,
                'provider': 'snap_express',
                'cost': cost,
                'delivery_days': 1,
                'service_type': service_type,
                'description': 'اسنپ اکسپرس - ارسال سریع همان روز'
            }
            
        except Exception as e:
            logger.error(f"Snap Express cost error: {e}")
            return {
                'success': False,
                'error': 'خطا در محاسبه هزینه اسنپ اکسپرس'
            }
    
    def _supports_route(self, from_city: str, to_city: str) -> bool:
        """Check if route is supported by Snap Express"""
        supported_cities = ['تهران', 'کرج', 'اصفهان', 'مشهد', 'شیراز']
        return from_city in supported_cities and to_city in supported_cities
    
    def _calculate_snap_cost(self, from_city: str, to_city: str, weight: float, service_type: str) -> int:
        """Calculate Snap Express cost"""
        base_cost = 45000 if service_type == 'express' else 35000
        
        # Same city delivery
        if from_city == to_city:
            return base_cost + int(weight * 5000)
        
        # Inter-city delivery
        return int((base_cost + weight * 8000) * 1.3)


class LogisticsManager:
    """Central logistics management"""
    
    def __init__(self):
        self.providers = {}
        self._load_providers()
    
    def _load_providers(self):
        """Load configured logistics providers"""
        logistics_config = getattr(settings, 'LOGISTICS_PROVIDERS', {})
        
        for provider_name, config in logistics_config.items():
            if config.get('enabled', False):
                try:
                    if provider_name == 'post':
                        self.providers[provider_name] = PostCompanyProvider(
                            config['api_key'], config.get('sandbox', True)
                        )
                    elif provider_name == 'tipax':
                        self.providers[provider_name] = TipaxProvider(
                            config['api_key'], config.get('sandbox', True)
                        )
                    elif provider_name == 'snap_express':
                        self.providers[provider_name] = SnapExpressProvider(
                            config['api_key'], config.get('sandbox', True)
                        )
                except Exception as e:
                    logger.error(f"Failed to load provider {provider_name}: {e}")
    
    def get_shipping_options(self, from_city: str, to_city: str, weight: float, **kwargs) -> List[Dict[str, Any]]:
        """Get shipping options from all providers"""
        options = []
        
        for provider_name, provider in self.providers.items():
            try:
                result = provider.calculate_shipping_cost(from_city, to_city, weight, **kwargs)
                if result['success']:
                    options.append(result)
            except Exception as e:
                logger.error(f"Error getting options from {provider_name}: {e}")
        
        # Sort by cost
        return sorted(options, key=lambda x: x['cost'])
    
    def get_cheapest_option(self, from_city: str, to_city: str, weight: float, **kwargs) -> Optional[Dict[str, Any]]:
        """Get cheapest shipping option"""
        options = self.get_shipping_options(from_city, to_city, weight, **kwargs)
        return options[0] if options else None
    
    def get_fastest_option(self, from_city: str, to_city: str, weight: float, **kwargs) -> Optional[Dict[str, Any]]:
        """Get fastest shipping option"""
        options = self.get_shipping_options(from_city, to_city, weight, **kwargs)
        if not options:
            return None
        
        return min(options, key=lambda x: x['delivery_days'])
    
    def create_shipment(self, provider_name: str, shipment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create shipment with specific provider"""
        if provider_name not in self.providers:
            return {
                'success': False,
                'error': f'Provider {provider_name} not available'
            }
        
        try:
            return self.providers[provider_name].create_shipment(shipment_data)
        except Exception as e:
            logger.error(f"Create shipment error with {provider_name}: {e}")
            return {
                'success': False,
                'error': 'خطا در ایجاد مرسوله'
            }
    
    def track_shipment(self, provider_name: str, tracking_number: str) -> Dict[str, Any]:
        """Track shipment"""
        if provider_name not in self.providers:
            return {
                'success': False,
                'error': f'Provider {provider_name} not available'
            }
        
        try:
            return self.providers[provider_name].track_shipment(tracking_number)
        except Exception as e:
            logger.error(f"Track shipment error with {provider_name}: {e}")
            return {
                'success': False,
                'error': 'خطا در پیگیری مرسوله'
            }


# Global logistics manager instance
logistics_manager = LogisticsManager()

# Helper functions for common logistics operations
def calculate_shipping_costs(from_city: str, to_city: str, weight: float, **kwargs) -> List[Dict[str, Any]]:
    """Calculate shipping costs from all available providers"""
    return logistics_manager.get_shipping_options(from_city, to_city, weight, **kwargs)

def get_recommended_shipping(from_city: str, to_city: str, weight: float, preference: str = 'cost') -> Optional[Dict[str, Any]]:
    """Get recommended shipping option based on preference"""
    if preference == 'cost':
        return logistics_manager.get_cheapest_option(from_city, to_city, weight)
    elif preference == 'speed':
        return logistics_manager.get_fastest_option(from_city, to_city, weight)
    else:
        options = logistics_manager.get_shipping_options(from_city, to_city, weight)
        return options[0] if options else None

def validate_iranian_address(address_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate Iranian address format"""
    required_fields = ['province', 'city', 'address', 'postal_code']
    errors = []
    
    for field in required_fields:
        if not address_data.get(field):
            errors.append(f'{field} is required')
    
    # Validate postal code format (Iranian format: NNNNNNNNN)
    postal_code = address_data.get('postal_code', '')
    if postal_code and not (postal_code.isdigit() and len(postal_code) == 10):
        errors.append('کد پستی باید ۱۰ رقم باشد')
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }

# City and province data for Iranian logistics
IRANIAN_CITIES = {
    'تهران': ['تهران', 'ری', 'شمیرانات', 'اسلامشهر', 'ورامین'],
    'اصفهان': ['اصفهان', 'کاشان', 'نجف‌آباد', 'خمینی‌شهر'],
    'فارس': ['شیراز', 'مرودشت', 'کازرون', 'لار'],
    'خراسان رضوی': ['مشهد', 'نیشابور', 'سبزوار', 'تربت حیدریه'],
    'آذربایجان شرقی': ['تبریز', 'مراغه', 'میانه', 'اهر'],
    'البرز': ['کرج', 'نظرآباد', 'ساوجبلاغ', 'طالقان']
}

def get_province_by_city(city_name: str) -> Optional[str]:
    """Get province name by city"""
    for province, cities in IRANIAN_CITIES.items():
        if city_name in cities:
            return province
    return None

def get_cities_in_province(province_name: str) -> List[str]:
    """Get all cities in a province"""
    return IRANIAN_CITIES.get(province_name, [])
