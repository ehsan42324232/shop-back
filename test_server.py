#!/usr/bin/env python
"""
Temporary server runner to bypass GDAL issues
"""
import os
import sys
import django

# Disable GIS imports completely
class DummyGIS:
    def __getattr__(self, name):
        raise ImportError(f"GIS module '{name}' is disabled")

# Block GIS imports
sys.modules['django.contrib.gis'] = DummyGIS()
sys.modules['django.contrib.gis.geos'] = DummyGIS()
sys.modules['django.contrib.gis.gdal'] = DummyGIS()

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shop_platform.settings')

def main():
    """Run administrative tasks."""
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
