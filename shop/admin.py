# shop app admin registrations

import pandas as pd
from django import forms
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html
from .models import Product, Store
from django.core.files.storage import default_storage

class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField()

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    change_list_template = "admin/store_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.admin_site.admin_view(self.upload_excel))
        ]
        return custom_urls + urls

    def upload_excel(self, request):
        from django.contrib import messages
        if request.method == "POST":
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                file = form.cleaned_data["excel_file"]
                path = default_storage.save('tmp/products.xlsx', file)
                df = pd.read_excel(default_storage.path(path))

                # Assuming columns: name, price, stock, store_id
                for _, row in df.iterrows():
                    try:
                        store = Store.objects.get(id=row["store_id"])
                        Product.objects.create(
                            name=row["name"],
                            price=row["price"],
                            stock=row["stock"],
                            store=store
                        )
                    except Store.DoesNotExist:
                        continue

                messages.success(request, "Products uploaded successfully.")
                return redirect("..")
        else:
            form = ExcelUploadForm()
        from django.shortcuts import render
        return render(request, "admin/excel_upload.html", {"form": form})

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "price", "stock", "store")
