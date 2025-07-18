import pandas as pd
import os
import json
from datetime import datetime
from django.utils.text import slugify
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import models
from .models import Store, Category, Product, ProductAttribute, ProductAttributeValue, BulkImportLog


def process_bulk_import(uploaded_file, store, user):
    """
    Process bulk import of products from CSV/Excel file
    Expected CSV format:
    title,category_level_1,category_level_2,category_level_3,price,stock,description,sku,attribute_name_1,attribute_value_1,attribute_name_2,attribute_value_2,...
    """
    
    # Save file temporarily
    filename = f"imports/{store.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
    file_path = default_storage.save(filename, ContentFile(uploaded_file.read()))
    
    # Create import log
    import_log = BulkImportLog.objects.create(
        store=store,
        user=user,
        filename=uploaded_file.name,
        file_path=file_path,
        status='processing'
    )
    
    try:
        # Read file based on extension
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        
        if file_extension == '.csv':
            df = pd.read_csv(default_storage.path(file_path))
        elif file_extension in ['.xlsx', '.xls']:
            df = pd.read_excel(default_storage.path(file_path))
        else:
            raise ValueError("فرمت فایل پشتیبانی نمی‌شود")
        
        import_log.total_rows = len(df)
        import_log.save()
        
        successful_rows = 0
        failed_rows = 0
        categories_created = 0
        products_created = 0
        products_updated = 0
        errors = []
        
        # Required columns
        required_columns = ['title', 'price']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"ستون‌های اجباری موجود نیستند: {', '.join(missing_columns)}")
        
        for index, row in df.iterrows():
            try:
                # Process categories
                category = None
                category_levels = []
                
                # Check for category columns (category_level_1, category_level_2, etc.)
                for i in range(1, 6):  # Support up to 5 levels
                    level_col = f'category_level_{i}'
                    if level_col in df.columns and pd.notna(row[level_col]):
                        category_levels.append(str(row[level_col]).strip())
                
                # Create categories hierarchy
                parent_category = None
                for level_name in category_levels:
                    category, created = Category.objects.get_or_create(
                        store=store,
                        name=level_name,
                        parent=parent_category,
                        defaults={
                            'slug': slugify(level_name),
                            'is_active': True
                        }
                    )
                    if created:
                        categories_created += 1
                    parent_category = category
                
                # Prepare product data
                product_data = {
                    'title': str(row['title']).strip(),
                    'price': float(row['price']) if pd.notna(row['price']) else 0,
                    'store': store,
                    'category': category,
                    'is_active': True
                }
                
                # Optional fields
                optional_fields = {
                    'description': 'description',
                    'short_description': 'short_description',
                    'sku': 'sku',
                    'barcode': 'barcode',
                    'stock': 'stock',
                    'compare_price': 'compare_price',
                    'cost_price': 'cost_price',
                    'weight': 'weight',
                    'dimensions': 'dimensions',
                    'meta_title': 'meta_title',
                    'meta_description': 'meta_description',
                }
                
                for field, column in optional_fields.items():
                    if column in df.columns and pd.notna(row[column]):
                        if field in ['stock']:
                            product_data[field] = int(row[column])
                        elif field in ['compare_price', 'cost_price', 'weight']:
                            product_data[field] = float(row[column])
                        else:
                            product_data[field] = str(row[column]).strip()
                
                # Check if product exists (by title or SKU)
                existing_product = None
                if 'sku' in product_data and product_data['sku']:
                    existing_product = Product.objects.filter(
                        store=store, 
                        sku=product_data['sku']
                    ).first()
                
                if not existing_product:
                    existing_product = Product.objects.filter(
                        store=store,
                        title=product_data['title']
                    ).first()
                
                if existing_product:
                    # Update existing product
                    for field, value in product_data.items():
                        if field not in ['store']:  # Don't update store
                            setattr(existing_product, field, value)
                    existing_product.save()
                    product = existing_product
                    products_updated += 1
                else:
                    # Create new product
                    product = Product.objects.create(**product_data)
                    products_created += 1
                
                # Process attributes
                attribute_columns = [col for col in df.columns if col.startswith('attribute_')]
                
                # Group attribute columns by pairs (name, value)
                attribute_pairs = {}
                for col in attribute_columns:
                    if col.endswith('_name'):
                        attr_num = col.replace('attribute_', '').replace('_name', '')
                        value_col = f'attribute_{attr_num}_value'
                        if value_col in df.columns:
                            if pd.notna(row[col]) and pd.notna(row[value_col]):
                                attribute_pairs[str(row[col]).strip()] = str(row[value_col]).strip()
                
                # Create/update product attributes
                for attr_name, attr_value in attribute_pairs.items():
                    # Get or create attribute definition
                    attribute, created = ProductAttribute.objects.get_or_create(
                        store=store,
                        name=attr_name,
                        defaults={
                            'slug': slugify(attr_name),
                            'attribute_type': 'text',
                            'is_filterable': True
                        }
                    )
                    
                    # Set attribute value for product
                    ProductAttributeValue.objects.update_or_create(
                        product=product,
                        attribute=attribute,
                        defaults={'value': attr_value}
                    )
                
                successful_rows += 1
                
            except Exception as e:
                failed_rows += 1
                errors.append({
                    'row': index + 1,
                    'error': str(e),
                    'data': row.to_dict() if hasattr(row, 'to_dict') else str(row)
                })
        
        # Update import log
        import_log.successful_rows = successful_rows
        import_log.failed_rows = failed_rows
        import_log.categories_created = categories_created
        import_log.products_created = products_created
        import_log.products_updated = products_updated
        import_log.error_details = errors
        
        if failed_rows == 0:
            import_log.status = 'completed'
        elif successful_rows > 0:
            import_log.status = 'partial'
        else:
            import_log.status = 'failed'
        
        import_log.save()
        
        # Clean up temporary file
        try:
            default_storage.delete(file_path)
        except:
            pass
        
        return {
            'status': import_log.status,
            'message': f'ایمپورت تکمیل شد. {successful_rows} محصول موفق، {failed_rows} ناموفق',
            'details': {
                'total_rows': import_log.total_rows,
                'successful_rows': successful_rows,
                'failed_rows': failed_rows,
                'categories_created': categories_created,
                'products_created': products_created,
                'products_updated': products_updated,
                'errors': errors[:10]  # Return first 10 errors
            }
        }
        
    except Exception as e:
        import_log.status = 'failed'
        import_log.error_details = [{'error': str(e)}]
        import_log.save()
        
        # Clean up temporary file
        try:
            default_storage.delete(file_path)
        except:
            pass
        
        return {
            'status': 'failed',
            'message': f'خطا در پردازش فایل: {str(e)}',
            'details': {'error': str(e)}
        }


def generate_sample_import_template():
    """
    Generate a sample CSV template for bulk import
    """
    sample_data = [
        {
            'title': 'گوشی سامسونگ گلکسی A54',
            'category_level_1': 'الکترونیک',
            'category_level_2': 'موبایل و تبلت',
            'category_level_3': 'گوشی موبایل',
            'price': 15000000,
            'compare_price': 18000000,
            'stock': 10,
            'description': 'گوشی هوشمند سامسونگ با صفحه نمایش 6.4 اینچی',
            'short_description': 'گوشی سامسونگ گلکسی A54 با 128 گیگابایت حافظه',
            'sku': 'SAM-A54-128',
            'barcode': '8801643943790',
            'weight': 202.0,
            'dimensions': '158.2 x 76.7 x 8.2',
            'attribute_1_name': 'رنگ',
            'attribute_1_value': 'مشکی',
            'attribute_2_name': 'حافظه داخلی',
            'attribute_2_value': '128 گیگابایت',
            'attribute_3_name': 'رم',
            'attribute_3_value': '6 گیگابایت'
        },
        {
            'title': 'لپ تاپ ایسوس VivoBook',
            'category_level_1': 'الکترونیک',
            'category_level_2': 'کامپیوتر و لپ تاپ',
            'category_level_3': 'لپ تاپ',
            'price': 25000000,
            'stock': 5,
            'description': 'لپ تاپ ایسوس با پردازنده Intel Core i5',
            'sku': 'ASUS-VB-I5',
            'attribute_1_name': 'پردازنده',
            'attribute_1_value': 'Intel Core i5',
            'attribute_2_name': 'رم',
            'attribute_2_value': '8 گیگابایت',
            'attribute_3_name': 'هارد',
            'attribute_3_value': '256 گیگابایت SSD'
        }
    ]
    
    df = pd.DataFrame(sample_data)
    return df


def validate_domain_setup(domain):
    """
    Validate that a domain is properly configured for the store
    """
    import socket
    import requests
    
    try:
        # Check if domain resolves
        socket.gethostbyname(domain)
        
        # Try to make a request to the domain
        response = requests.get(f"http://{domain}", timeout=5)
        return True, "Domain is properly configured"
        
    except socket.gaierror:
        return False, "Domain does not resolve"
    except requests.exceptions.RequestException as e:
        return False, f"Domain is not accessible: {str(e)}"


def get_store_analytics(store, date_from=None, date_to=None):
    """
    Get analytics data for a store
    """
    from django.db.models import Sum, Count, Avg, F
    from datetime import datetime, timedelta
    
    if not date_from:
        date_from = datetime.now() - timedelta(days=30)
    if not date_to:
        date_to = datetime.now()
    
    # Orders analytics
    orders = store.orders.filter(created_at__range=[date_from, date_to])
    
    # Product analytics
    products = store.products.filter(is_active=True)
    
    # Calculate metrics
    analytics = {
        'orders': {
            'total_orders': orders.count(),
            'total_revenue': orders.aggregate(total=Sum('total_amount'))['total'] or 0,
            'average_order_value': orders.aggregate(avg=Avg('total_amount'))['avg'] or 0,
            'pending_orders': orders.filter(status='pending').count(),
            'completed_orders': orders.filter(status='delivered').count(),
        },
        'products': {
            'total_products': products.count(),
            'active_products': products.filter(is_active=True).count(),
            'featured_products': products.filter(is_featured=True).count(),
            'low_stock_products': products.filter(
                track_inventory=True,
                stock__lte=F('low_stock_threshold')
            ).count(),
            'out_of_stock_products': products.filter(
                track_inventory=True,
                stock=0
            ).count(),
        },
        'categories': {
            'total_categories': store.categories.filter(is_active=True).count(),
        }
    }
    
    # Top selling products - import OrderItem from storefront_models
    try:
        from .storefront_models import OrderItem
        top_products = OrderItem.objects.filter(
            order__store=store,
            order__created_at__range=[date_from, date_to]
        ).values('product__title').annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('price_at_order')
        ).order_by('-total_sold')[:10]
        
        analytics['top_products'] = list(top_products)
    except ImportError:
        analytics['top_products'] = []
    
    return analytics


def send_store_notification(store, message, notification_type='info'):
    """
    Send notification to store owner
    """
    # This could be extended to send email, SMS, or push notifications
    # For now, we'll just log it
    from django.contrib.admin.models import LogEntry, ADDITION
    from django.contrib.contenttypes.models import ContentType
    
    LogEntry.objects.log_action(
        user_id=store.owner.id,
        content_type_id=ContentType.objects.get_for_model(store).pk,
        object_id=store.pk,
        object_repr=str(store),
        action_flag=ADDITION,
        change_message=f"[{notification_type.upper()}] {message}"
    )


def export_products_to_csv(store, queryset=None):
    """
    Export store products to CSV format
    """
    if queryset is None:
        queryset = store.products.filter(is_active=True)
    
    # Prepare data for export
    export_data = []
    
    for product in queryset.prefetch_related('category', 'attribute_values__attribute'):
        row = {
            'title': product.title,
            'sku': product.sku,
            'price': product.price,
            'compare_price': product.compare_price,
            'stock': product.stock,
            'description': product.description,
            'short_description': product.short_description,
            'weight': product.weight,
            'dimensions': product.dimensions,
            'is_active': product.is_active,
            'is_featured': product.is_featured,
            'created_at': product.created_at,
        }
        
        # Add category hierarchy
        if product.category:
            category_path = product.category.get_full_path().split(' > ')
            for i, level in enumerate(category_path[:5], 1):
                row[f'category_level_{i}'] = level
        
        # Add attributes
        attributes = product.attribute_values.all()
        for i, attr_value in enumerate(attributes[:10], 1):  # Limit to 10 attributes
            row[f'attribute_{i}_name'] = attr_value.attribute.name
            row[f'attribute_{i}_value'] = attr_value.value
        
        export_data.append(row)
    
    df = pd.DataFrame(export_data)
    return df


def cleanup_old_import_files():
    """
    Clean up old import files (older than 30 days)
    """
    from datetime import datetime, timedelta
    import os
    
    cutoff_date = datetime.now() - timedelta(days=30)
    old_logs = BulkImportLog.objects.filter(created_at__lt=cutoff_date)
    
    for log in old_logs:
        try:
            if os.path.exists(log.file_path):
                os.remove(log.file_path)
        except:
            pass
        log.delete()
