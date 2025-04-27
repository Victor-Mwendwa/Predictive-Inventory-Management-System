from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.db.models import Sum, F
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import admin
from .models import Inventory
from .models import (
    Product, Inventory, Order, OrderItem,
    DemandForecast, Retailer, ProductCategory,
    InventoryAudit
)
from .forms import RetailerUserCreationForm

class NeedsRestockFilter(admin.SimpleListFilter):
    title = 'Needs restock'
    parameter_name = 'needs_restock'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(quantity__lt=10)  # Adjust logic
        elif self.value() == 'no':
            return queryset.filter(quantity__gte=10)
        return queryset
    
    
class InventoryInline(admin.StackedInline):
    model = Inventory
    fields = ['current_stock', 'safety_stock', 'reorder_point', 'stock_status']
    readonly_fields = ['stock_status']
    extra = 0

    def stock_status(self, instance):
        if instance.current_stock == 0:
            color = 'danger'
            status = 'Out of Stock'
        elif instance.current_stock <= instance.reorder_point:
            color = 'warning'
            status = 'Low Stock'
        else:
            color = 'success'
            status = 'In Stock'
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, status
        )
    stock_status.short_description = 'Status'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    fields = ['product', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['unit_price', 'subtotal']
    extra = 0

    def subtotal(self, instance):
        return instance.subtotal
    subtotal.short_description = 'Subtotal'


class DemandForecastInline(admin.TabularInline):
    model = DemandForecast
    fields = ['forecast_date', 'predicted_demand', 'confidence_score', 'suggested_order']
    readonly_fields = ['suggested_order']
    extra = 0

    def suggested_order(self, instance):
        return instance.suggested_order_quantity
    suggested_order.short_description = 'Suggested Qty'


class InventoryAuditInline(admin.TabularInline):
    model = InventoryAudit
    fields = ['action', 'quantity', 'previous_quantity', 'new_quantity', 'created_at']
    readonly_fields = ['previous_quantity', 'new_quantity', 'created_at']
    extra = 0
    can_delete = False
    max_num = 10


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_count']
    search_fields = ['name']
    ordering = ['name']

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'sku', 'category', 'price',
        'current_stock', 'stock_status', 'monthly_sales'
    ]
    list_filter = ['category', 'perishable']
    search_fields = ['name', 'sku', 'description']
    list_select_related = ['category', 'inventory']
    inlines = [InventoryInline, DemandForecastInline, InventoryAuditInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'sku', 'category', 'description')
        }),
        ('Pricing & Details', {
            'fields': ('price', 'image', 'perishable', 'expiry_days')
        }),
    )
    readonly_fields = ['stock_status']

    def current_stock(self, obj):
        return obj.inventory.current_stock
    current_stock.short_description = 'Stock'
    current_stock.admin_order_field = 'inventory__current_stock'

    def stock_status(self, obj):
        inventory = obj.inventory
        if inventory.current_stock == 0:
            color = 'danger'
            status = 'Out of Stock'
        elif inventory.current_stock <= inventory.reorder_point:
            color = 'warning'
            status = 'Low Stock'
        else:
            color = 'success'
            status = 'In Stock'
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, status
        )
    stock_status.short_description = 'Status'

    def monthly_sales(self, obj):
        return obj.monthly_sales
    monthly_sales.short_description = '30-Day Sales'


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'current_stock', 'safety_stock',
        'reorder_point', 'needs_restock', 'days_of_supply'
    ]
    list_filter = [NeedsRestockFilter]
    search_fields = ['product__name', 'product__sku']
    list_select_related = ['product']
    actions = ['generate_restock_orders']
    readonly_fields = ['days_of_supply']

    def needs_restock(self, obj):
        return obj.current_stock < obj.reorder_point
    needs_restock.boolean = True
    needs_restock.short_description = 'Needs Restock'

    def days_of_supply(self, obj):
        return obj.days_of_supply
    days_of_supply.short_description = 'Days of Supply'

def generate_restock_orders(self, request, queryset):
        for inventory in queryset:
            if inventory.current_stock < inventory.reorder_point:
                suggested_qty = max(
                    inventory.reorder_point + inventory.safety_stock - inventory.current_stock,
                    inventory.safety_stock
                )
                # Send a message to the admin about the suggested restocking
                self.message_user(
                    request,
                    f"Suggested to restock {inventory.product.name} with {suggested_qty} units",
                    level=messages.INFO
                )

        # Return a success message after the action is completed
        self.message_user(
            request,
            "Restock order suggestions have been generated for selected items.",
            level=messages.SUCCESS
        )

    # Add the action to the list of actions available for the admin interface
        actions = ['generate_restock_orders']

class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'retailer', 'order_date',
        'status', 'total_amount', 'item_count'
    ]
    list_filter = ['status', 'order_date']
    search_fields = ['reference', 'retailer__user__username']
    list_select_related = ['retailer__user']
    inlines = [OrderItemInline]  # Ensure OrderItemInline is defined somewhere
    date_hierarchy = 'order_date'
    actions = ['mark_as_processing', 'mark_as_shipped']  # Register actions here
    readonly_fields = ['total_amount']

    def total_amount(self, obj):
        return sum(item.subtotal for item in obj.items.all())
    total_amount.short_description = 'Total'

    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Items'

    # Action to mark selected orders as 'PROCESSING'
    def mark_as_processing(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='PROCESSING')
        self.message_user(
            request,
            f"{updated} orders marked as Processing",
            level=messages.SUCCESS
        )

    # Action to mark selected orders as 'SHIPPED'
    def mark_as_shipped(self, request, queryset):
        updated = queryset.filter(status='PROCESSING').update(status='SHIPPED')
        self.message_user(
            request,
            f"{updated} orders marked as Shipped",
            level=messages.SUCCESS
        )

# Register the Order model with the custom admin


class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order_link', 'product_link', 'quantity', 'unit_price', 'subtotal']
    list_select_related = ['order', 'product']
    search_fields = ['product__name', 'order__reference']

    def order_link(self, obj):
        url = reverse('admin:core_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.reference)
    order_link.short_description = 'Order'

    def product_link(self, obj):
        url = reverse('admin:core_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_link.short_description = 'Product'

    def subtotal(self, obj):
        return obj.subtotal
    subtotal.short_description = 'Subtotal'

class DemandForecastAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'forecast_date', 'predicted_demand',
        'confidence_score', 'suggested_order'
    ]
    list_filter = ['forecast_date']
    search_fields = ['product__name']
    list_select_related = ['product']
    date_hierarchy = 'forecast_date'

    def suggested_order(self, obj):
        return obj.suggested_order_quantity
    suggested_order.short_description = 'Suggested Qty'


class RetailerInline(admin.StackedInline):
    model = Retailer
    can_delete = False
    verbose_name_plural = 'Retailer Profile'
    fields = ['location', 'storage_capacity', 'contact', 'is_active']


class CustomUserAdmin(UserAdmin):
    add_form = RetailerUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )
    list_display = UserAdmin.list_display + ('is_retailer',)
    inlines = [RetailerInline]

    def is_retailer(self, obj):
        return hasattr(obj, 'retailer')
    is_retailer.boolean = True
    is_retailer.short_description = 'Retailer'


@admin.register(Retailer)
class RetailerAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'location', 'storage_capacity',
        'contact', 'is_active', 'order_count'
    ]
    list_filter = ['is_active']
    search_fields = ['user__username', 'location', 'contact']
    list_select_related = ['user']
    actions = ['activate_retailers', 'deactivate_retailers']

    def order_count(self, obj):
        return obj.orders.count()
    order_count.short_description = 'Orders'

    def activate_retailers(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"{updated} retailers activated",
            level='SUCCESS'
        )
    activate_retailers.short_description = 'Activate selected retailers'

    def deactivate_retailers(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"{updated} retailers deactivated",
            level='SUCCESS'
        )
    deactivate_retailers.short_description = 'Deactivate selected retailers'

from django.contrib import admin
from django.utils.html import format_html
from .models import InventoryAudit  # Adjust according to your import

@admin.register(InventoryAudit)
class InventoryAuditAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'action', 'quantity_change',
        'previous_quantity', 'new_quantity', 'created_at'
    ]
    list_filter = ['action', 'created_at']
    search_fields = ['product__name', 'reference']
    list_select_related = ['product', 'created_by']
    date_hierarchy = 'created_at'
    readonly_fields = [
        'product', 'action', 'quantity',
        'previous_quantity', 'new_quantity',
        'reference', 'notes', 'created_by',
        'created_at'
    ]

    def quantity_change(self, obj):
        if obj.quantity > 0:
            return format_html(
                '<span style="color:green">+{}</span>',
                obj.quantity
            )
        return format_html(
            '<span style="color:red">{}</span>',
            obj.quantity
        )
    quantity_change.short_description = 'Change'



# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Admin site customization
admin.site.site_header = "Kyosk Inventory Administration"
admin.site.site_title = "Kyosk Inventory Admin"
admin.site.index_title = "Inventory Management"
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(DemandForecast, DemandForecastAdmin)



