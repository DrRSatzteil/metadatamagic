import logging
import os
import pickle
from typing import Any

import mgzip

from ..io import MODEL_STORAGE_LOCATION

__all__ = ['load_document_type', 'save_document_type', 'load_document_cluster', 'save_document_cluster', 'save_dictionary', 'load_dictionary', 'save_synonyms', 'load_synonyms', 'save_page_types', 'load_page_types']

_logger = logging.getLogger(__name__)

def save_object(obj: Any, folder: str, file_name: str):
    try:
        folder = os.path.join(MODEL_STORAGE_LOCATION, folder)
        if not os.path.exists(folder):
            os.makedirs(folder)
        full_path = os.path.join(folder, file_name)
        with mgzip.open(full_path, 'wb') as f:
            pickle.dump(obj, f)
    except Exception as e:
        _logger.warning('Could not save object to file: {0}'.format(str(e)))

def load_object(folder: str, file_name: str):
    try:
        path = os.path.join(MODEL_STORAGE_LOCATION, folder, file_name)
        if os.path.exists(path):
            with mgzip.open(path, 'rb') as f:
                obj = pickle.load(f)
                return obj
    except Exception as e:
        _logger.warning('Could not load object from file: {0}'.format(str(e)))

def save_dictionary(cluster):
    save_object(cluster.dictionary, 'dict', cluster.cluster_id)

def load_dictionary(cluster):
    cluster.dictionary = load_object('dict', cluster.cluster_id)
    if cluster.dictionary is None:
        cluster.dictionary = {}
        for metadata_name, metadata_value in cluster.metadata.items():
            cluster.dictionary[metadata_name] = len(cluster.dictionary) + 1
            cluster.dictionary[metadata_value] = len(cluster.dictionary) + 1

def save_synonyms(cluster):
    save_object(cluster.synonyms, 'syn', cluster.cluster_id)

def load_synonyms(cluster):
    cluster.synonyms = load_object('syn', cluster.cluster_id)
    if cluster.synonyms is None:
        cluster.synonyms = {}

def save_page_types(cluster):
    save_object(cluster.page_types, 'ptype', cluster.cluster_id)

def load_page_types(cluster):
    cluster.page_types = load_object('ptype', cluster.cluster_id)
    if cluster.page_types is None:
        cluster.page_types = []
    
def save_document_cluster(cluster):
    save_dictionary(cluster)
    save_synonyms(cluster)
    save_page_types(cluster)

def load_document_cluster(cluster, dictionary=True, synonyms=True, page_types=True):
    if dictionary:
        load_dictionary(cluster)
    if synonyms:
        load_synonyms(cluster)
    if page_types:
        load_page_types(cluster)

def save_document_type(document_type):
    keys = [key for key in document_type.cluster_map.keys()]
    save_object(keys, 'doctype', document_type.mayan_document_type)

def load_document_type(document_type):
    keys = load_object('doctype', document_type.mayan_document_type)
    if keys and len(keys) > 0:
        document_type.cluster_map = dict.fromkeys(keys)