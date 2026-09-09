"""Constants for the Ista integration."""
from datetime import timedelta

DOMAIN = "ista"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DOWNLOAD_INVOICES = "download_invoices"
CONF_INVOICES_PATH = "invoices_path"
CONF_HOT_WATER_PRICE = "hot_water_price"
CONF_HEATING_PRICE = "heating_price"

DEFAULT_SCAN_INTERVAL_HOURS = 12
DEFAULT_SCAN_INTERVAL = timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS)
DEFAULT_DOWNLOAD_INVOICES = True
DEFAULT_INVOICES_PATH = "/config/www/ista_facturas"
DEFAULT_HOT_WATER_PRICE = 0.0
DEFAULT_HEATING_PRICE = 0.0

# Events & Services
EVENT_NEW_INVOICE = "ista_new_invoice"
SERVICE_DOWNLOAD_RECEIPT = "download_receipt"
SERVICE_IMPORT_HISTORY = "import_history"

# Sensor Types / Keys
ATTR_READING_DATE = "reading_date"
ATTR_LAST_BILLED_DATE = "last_billed_date"
ATTR_LAST_BILLED_READING = "last_billed_reading"
ATTR_PREVIOUS_BILLED_READING = "previous_billed_reading"
ATTR_UNBILLED_CONSUMPTION = "unbilled_consumption"
ATTR_ESTIMATED_UNBILLED_COST = "estimated_unbilled_cost"
ATTR_TOTAL_BILLED_COST = "total_billed_cost"
ATTR_BILLS_COUNT = "bills_count"
ATTR_UNIT_PRICE = "unit_price"
ATTR_CALCULATION_METHOD = "calculation_method"
ATTR_DAILY_READINGS = "daily_readings"
ATTR_MONTHLY_HISTORY = "monthly_history"
ATTR_PDF_URL = "pdf_url"
ATTR_RECEIPT_ID = "receipt_id"
ATTR_EQUIPMENT_TYPE = "equipment_type"
ATTR_SERIAL_NUMBER = "serial_number"
ATTR_SUBSCRIBER_NUMBER = "subscriber_number"
ATTR_SUBSCRIBER_NAME = "subscriber_name"
