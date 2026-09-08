"""Constants for the Ista integration."""
from datetime import timedelta

DOMAIN = "ista"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DOWNLOAD_INVOICES = "download_invoices"
CONF_INVOICES_PATH = "invoices_path"

DEFAULT_SCAN_INTERVAL_HOURS = 6
DEFAULT_SCAN_INTERVAL = timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS)
DEFAULT_DOWNLOAD_INVOICES = True
DEFAULT_INVOICES_PATH = "/config/www/ista_facturas"

# Events & Services
EVENT_NEW_INVOICE = "ista_new_invoice"
SERVICE_DOWNLOAD_RECEIPT = "download_receipt"

# Sensor Types / Keys
ATTR_READING_DATE = "reading_date"
ATTR_LAST_BILLED_DATE = "last_billed_date"
ATTR_LAST_BILLED_READING = "last_billed_reading"
ATTR_PREVIOUS_BILLED_READING = "previous_billed_reading"
ATTR_UNBILLED_CONSUMPTION = "unbilled_consumption"
ATTR_PDF_URL = "pdf_url"
ATTR_RECEIPT_ID = "receipt_id"
ATTR_EQUIPMENT_TYPE = "equipment_type"
ATTR_SERIAL_NUMBER = "serial_number"
ATTR_SUBSCRIBER_NUMBER = "subscriber_number"
ATTR_SUBSCRIBER_NAME = "subscriber_name"
