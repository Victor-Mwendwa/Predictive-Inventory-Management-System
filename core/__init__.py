# This makes the core directory a Django app
# Can be used to expose important functionality at package level

default_app_config = 'core.apps.CoreConfig'

# Optionally expose key components at package level
# from .models import Product, Inventory, Order  # noqa
#from .utils.ml_model import DemandForecaster  # noqa

#__all__ = ['Product', 'Inventory', 'Order', 'DemandForecaster']