from __future__ import annotations

from homeassistant.const import Platform


DOMAIN = "nice_gate"
PLATFORMS = [Platform.COVER, Platform.BUTTON, Platform.SWITCH]

CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_INDEX = "device_index"
CONF_CLOUD_ID = "cloud_id"
CONF_PRODUCT_TYPE = "product_type"
CONF_HOME_ID = "home_id"
CONF_PERMISSION = "permission"
