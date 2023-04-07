import json
import logging
import os

_logger = logging.getLogger(__name__)

__all__ = ['DEFAULT_LANGUAGE', 'ADDITIONAL_VOCAB', 'METADATA', 'MIN_CONFIDENCE', 'MODEL_STORAGE_LOCATION']

#TODO: Load global settings from config file
DEFAULT_LANGUAGE = 'de'
ADDITIONAL_VOCAB = '§ñéç'
MIN_CONFIDENCE = 75
MODEL_STORAGE_LOCATION = 'modelstorage'

# Metadata Settings
METADATA = {'receiptdate': {'type': 'date', 'format': '%Y-%m-%d', 'groupby': False}, 'issuer': {'type': 'string', 'groupby': True}, 'invoiceamount': {'type': 'money', 'groupby': False}, 'documentcontent': {'type': 'string', 'groupby': True}, 'invoicenumber': {'type': 'string', 'groupby': False}}

def load_config():
    with open(os.path.join('metadatamagic', 'config', 'config.json')) as f:
        config = json.load(f)
    #TODO: Validate config and make config accessible
    return config
