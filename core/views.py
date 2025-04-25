from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Sum, F, Q
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
from django.shortcuts import render
# core/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.views.generic import ListView
from .models import Inventory  # make sure the model name is correct

from .models import (
    Product, Inventory, Order, OrderItem, 
    DemandForecast, Retailer, ProductCategory,
    InventoryAudit
)
from .forms import (
    ProductForm, InventoryForm, OrderForm,
    OrderItemFormSet, RetailerForm, ProductCategoryForm
)
from .utils.ml_model import DemandForecaster
import json
from django.shortcuts import render
from django.shortcuts import render
from core.models import DemandForecast
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import OrderForm
from .models import Order, Retailer  # Adjust if your model names differ
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ProductForm

@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Product created successfully.")
            return redirect('product_list')  # or your desired redirect
    else:
        form = ProductForm()
    
    return render(request, 'core/create_product.html', {'form': form})

@login_required
def order_create(request):
    retailer = getattr(request.user, 'retailer', None)  # assuming a OneToOne relation

    if not retailer:
        messages.error(request, "Only retailer accounts can place orders.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.retailer = retailer  # assign from logged-in user
            order.save()
            messages.success(request, "Order created successfully.")
            return redirect('order_list')
    else:
        form = OrderForm(initial={'retailer': retailer})
    return render(request, 'core/create_order.html', {'form': form})

def forecast_report(request):
    return render(request, 'core/forecast_report.html', {})

def sales_report(request):
    return render(request, 'reports/sales_report.html')

def reports(request):
    return render(request, 'core/reports.html')

def profile(request):
    return render(request, 'core/profile.html')
 
def profile(request):
    return render(request, 'core/base.html')

def dashboard(request):
    return render(request, 'dashboard.html')

class DashboardView(LoginRequiredMixin, ListView):
    template_name = 'core/dashboard.html'
    context_object_name = 'alerts'

    def get_queryset(self):
        return {
            'low_stock': Inventory.objects.filter(
                current_stock__lte=F('reorder_point'),
                current_stock__gt=0
            ).select_related('product'),
            'out_of_stock': Inventory.objects.filter(
                current_stock=0
            ).select_related('product'),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recent orders
        context['recent_orders'] = Order.objects.order_by('-order_date')[:5]
        
        # Recent forecasts
        context['recent_forecasts'] = DemandForecast.objects.order_by('-forecast_date')[:5]
        
        # Sales summary
        thirty_days_ago = timezone.now() - timedelta(days=30)
        context['total_sales'] = OrderItem.objects.filter(
            order__order_date__gte=thirty_days_ago
        ).aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or 0
        
        return context

class InventoryList(ListView):
    model = Inventory
    template_name = 'api/inventory_list.html'  # or any template you create
    context_object_name = 'inventory_items'
    
class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'core/product_list.html'
    context_object_name = 'products'
    paginate_by = 20
    ordering = ['name']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('category', 'inventory')
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(sku__icontains=search_query) |
                Q(description__icontains=search_query))
        
        # Filter by category
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filter by stock status
        stock_status = self.request.GET.get('stock_status')
        if stock_status == 'low':
            queryset = queryset.filter(inventory__current_stock__lte=F('inventory__reorder_point'))
        elif stock_status == 'out':
            queryset = queryset.filter(inventory__current_stock=0)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ProductCategory.objects.all()
        return context


class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'core/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        
        # Sales data for charts
        sales_data = OrderItem.objects.filter(product=product).values(
            'order__order_date__date'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('unit_price'))
        ).order_by('order__order_date__date')[:30]
        
        context['sales_data'] = list(sales_data)
        
        # Forecasts
        context['forecasts'] = DemandForecast.objects.filter(
            product=product
        ).order_by('-forecast_date')[:5]
        
        # Inventory history
        context['inventory_history'] = InventoryAudit.objects.filter(
            product=product
        ).order_by('-created_at')[:10]
        
        return context


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'core/product_form.html'
    success_url = reverse_lazy('product_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        # Create inventory record for new product
        Inventory.objects.create(
            product=self.object,
            current_stock=0,
            safety_stock=10,
            reorder_point=20
        )
        messages.success(self.request, f"Product {self.object.name} created successfully!")
        return response


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'core/product_form.html'
    
    def get_success_url(self):
        return reverse_lazy('product_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Product {self.object.name} updated successfully!")
        return response


@login_required
def inventory_restock(request, pk):
    inventory = get_object_or_404(Inventory, pk=pk)
    
    if request.method == 'POST':
        form = InventoryForm(request.POST, instance=inventory)
        if form.is_valid():
            # Record previous quantity for audit
            previous_quantity = inventory.current_stock
            
            # Save the form
            inventory = form.save()
            
            # Create audit record
            quantity_change = inventory.current_stock - previous_quantity
            if quantity_change != 0:
                InventoryAudit.objects.create(
                    product=inventory.product,
                    action='RESTOCK' if quantity_change > 0 else 'ADJUSTMENT',
                    quantity=quantity_change,
                    previous_quantity=previous_quantity,
                    new_quantity=inventory.current_stock,
                    reference=f"Manual restock by {request.user.username}",
                    created_by=request.user
                )
            
            messages.success(request, "Inventory updated successfully!")
            return redirect('product_detail', pk=inventory.product.pk)
    else:
        form = InventoryForm(instance=inventory)
    
    return render(request, 'core/inventory_restock.html', {
        'form': form,
        'inventory': inventory,
    })


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'core/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    ordering = ['-order_date']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('retailer__user')
        
        # Filter by retailer (for retailer users)
        if not self.request.user.is_staff and hasattr(self.request.user, 'retailer'):
            queryset = queryset.filter(retailer=self.request.user.retailer)
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(reference__icontains=search_query) |
                Q(retailer__user__username__icontains=search_query) |
                Q(notes__icontains=search_query))
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'core/order_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('retailer__user')
        if not self.request.user.is_staff and hasattr(self.request.user, 'retailer'):
            queryset = queryset.filter(retailer=self.request.user.retailer)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.select_related('product')
        return context


class OrderCreateView(LoginRequiredMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'core/order_create.html'
    
    def get_success_url(self):
        return reverse_lazy('order_detail', kwargs={'pk': self.object.pk})

    def get_initial(self):
        initial = super().get_initial()
        if hasattr(self.request.user, 'retailer'):
            initial['retailer'] = self.request.user.retailer
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = OrderItemFormSet(self.request.POST)
        else:
            context['formset'] = OrderItemFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        if formset.is_valid():
            # Set retailer for staff users
            if self.request.user.is_staff and not form.cleaned_data.get('retailer'):
                form.instance.retailer = self.request.user.retailer
            
            self.object = form.save()
            
            # Save order items
            formset.instance = self.object
            formset.save()
            
            messages.success(self.request, "Order created successfully!")
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))


@login_required
def update_order_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status and order.update_status(new_status):
            messages.success(request, f"Order status updated to {new_status}")
        else:
            messages.error(request, "Invalid status transition")
    
    return redirect('order_detail', pk=order.pk)


@login_required
def generate_forecasts(request):
    if not request.user.is_staff:
        messages.error(request, "Only staff members can generate forecasts")
        return redirect('dashboard')
    
    forecaster = DemandForecaster()
    forecasts = forecaster.generate_forecasts()
    
    messages.success(request, f"Generated {len(forecasts)} new demand forecasts")
    return redirect('dashboard')


@login_required
def forecast_detail(request, pk):
    forecast = get_object_or_404(DemandForecast, pk=pk)
    return render(request, 'core/forecast_detail.html', {
        'forecast': forecast,
        'product': forecast.product,
    })


class RetailerListView(LoginRequiredMixin, ListView):
    model = Retailer
    template_name = 'core/retailer_list.html'
    context_object_name = 'retailers'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related('user')
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(user__username__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(contact__icontains=search_query))
        
        return queryset


class RetailerDetailView(LoginRequiredMixin, DetailView):
    model = Retailer
    template_name = 'core/retailer_detail.html'
    context_object_name = 'retailer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recent orders
        context['recent_orders'] = self.object.orders.order_by('-order_date')[:5]
        
        # Order statistics
        thirty_days_ago = timezone.now() - timedelta(days=30)
        context['monthly_order_count'] = self.object.orders.filter(
            order_date__gte=thirty_days_ago
        ).count()
        
        context['monthly_order_value'] = OrderItem.objects.filter(
            order__retailer=self.object,
            order__order_date__gte=thirty_days_ago
        ).aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or 0
        
        return context


class RetailerCreateView(LoginRequiredMixin, CreateView):
    model = Retailer
    form_class = RetailerForm
    template_name = 'core/retailer_form.html'
    success_url = reverse_lazy('retailer_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Retailer {self.object.user.username} created successfully!")
        return response


class RetailerUpdateView(LoginRequiredMixin, UpdateView):
    model = Retailer
    form_class = RetailerForm
    template_name = 'core/retailer_form.html'
    
    def get_success_url(self):
        return reverse_lazy('retailer_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Retailer {self.object.user.username} updated successfully!")
        return response


@login_required
def sales_report(request):
    # Default to last 30 days
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
    
    # Get sales data
    sales_data = OrderItem.objects.filter(
        order__order_date__date__range=[start_date, end_date]
    ).values(
        'product__name',
        'product__category__name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum(F('quantity') * F('unit_price'))
    ).order_by('-total_revenue')
    
    # Get top products
    top_products = sales_data.order_by('-total_quantity')[:5]
    
    # Get sales by day for chart
    daily_sales = OrderItem.objects.filter(
        order__order_date__date__range=[start_date, end_date]
    ).values(
        'order__order_date__date'
    ).annotate(
        daily_total=Sum(F('quantity') * F('unit_price'))
    ).order_by('order__order_date__date')
    
    return render(request, 'core/sales_report.html', {
        'sales_data': sales_data,
        'top_products': top_products,
        'daily_sales': list(daily_sales),
        'start_date': start_date,
        'end_date': end_date,
    })


@login_required
def inventory_report(request):
    # Get inventory status
    inventory_status = Inventory.objects.select_related('product').order_by('product__name')
    
    # Get inventory valuation
    total_value = sum(
        inv.current_stock * inv.product.price 
        for inv in inventory_status if inv.product.price
    )
    
    # Get aging inventory (products not sold in last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    active_products = OrderItem.objects.filter(
        order__order_date__gte=thirty_days_ago
    ).values_list('product_id', flat=True).distinct()
    
    aging_inventory = inventory_status.exclude(product_id__in=active_products)
    
    return render(request, 'core/inventory_report.html', {
        'inventory_status': inventory_status,
        'total_value': total_value,
        'aging_inventory': aging_inventory,
    })


@login_required
def get_product_details(request):
    """AJAX endpoint to get product details for order form"""
    product_id = request.GET.get('product_id')
    product = get_object_or_404(Product, pk=product_id)
    
    data = {
        'price': str(product.price),
        'current_stock': product.current_stock,
        'sku': product.sku,
    }
    
    return JsonResponse(data)


@login_required
def audit_log(request):
    """View inventory audit log"""
    audit_entries = InventoryAudit.objects.select_related(
        'product', 'created_by'
    ).order_by('-created_at')
    
    return render(request, 'core/audit_log.html', {
        'audit_entries': audit_entries,
    })
    
# Product views
def product_list(request):
    return HttpResponse("Product list")

def product_create(request):
    return HttpResponse("Create product")

def product_detail(request, pk):
    return HttpResponse(f"Product detail: {pk}")

def product_update(request, pk):
    return HttpResponse(f"Update product: {pk}")

def product_delete(request, pk):
    return HttpResponse(f"Delete product: {pk}")

# Stock views
def stock_list(request):
    return HttpResponse("Stock list")

def low_stock(request):
    return HttpResponse("Low stock")

def stock_update(request):
    return HttpResponse("Update stock")

# Forecast views
def forecast_list(request):
    return HttpResponse("Forecast list")

def generate_forecasts(request):
    return HttpResponse("Generate forecasts")

# Order views
def order_list(request):
    return HttpResponse("Order list")

def order_create(request):
    return HttpResponse("Create order")

def order_detail(request, pk):
    return HttpResponse(f"Order detail: {pk}")

# Reorder views
def reorder_list(request):
    return HttpResponse("Reorder list")

def auto_reorder(request):
    return HttpResponse("Auto reorder")

def manual_reorder(request):
    return HttpResponse("Manual reorder")

# Supplier views
def supplier_list(request):
    return HttpResponse("Supplier list")

def supplier_create(request):
    return HttpResponse("Create supplier")

def supplier_detail(request, pk):
    return HttpResponse(f"Supplier detail: {pk}")
