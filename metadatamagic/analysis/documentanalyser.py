import logging
import os
import re
import sys

import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
import torch
from doctr.datasets import vocabs
from doctr.io import DocumentFile
from doctr.models import crnn_vgg16_bn, ocr_predictor
from price_parser import Price

from ..io import ADDITIONAL_VOCAB, DEFAULT_LANGUAGE, METADATA
from ..model import (Block, BoundingBox, Metadata, DateMetadata, Document, DocumentCluster, DocumentType, Line,
                     MoneyMetadata, Page, Word, create_page_map)
from .parser import parse_dates, parse_prices, parse_matching_strings

__all__ = ['ocr_document', 'locate_metadata', 'find_best_cluster', 'predict_metadata']

_logger = logging.getLogger(__name__)

# TODO: Use language settings (FR, EN, DE)


def find_recognition_model():
    model_path = os.path.join('metadatamagic', 'dist', 'models')
    pattern = re.compile(r'crnn_vgg16_bn_(\d{8}-\d{6}).pt')
    model_files = [file for file in os.listdir(model_path)
                   if pattern.fullmatch(file)]
    file_name = (max(model_files, key=lambda f: datetime.strptime(
        pattern.match(f)[1], '%Y%m%d-%H%M%S')))
    return os.path.join(model_path, file_name)


def get_position(geometry):
    return ((geometry[0][0], geometry[0][1]), (geometry[1][0], geometry[1][1]))


def ocr_document(document: Document):

    model = crnn_vgg16_bn(
        pretrained=False, vocab=vocabs.VOCABS['german'] + ADDITIONAL_VOCAB)

    model_file = find_recognition_model()
    if model_file:
        model.load_state_dict(torch.load(model_file))

    predictor = ocr_predictor(
        reco_arch=model, pretrained=True, detect_language=True)

    doc = DocumentFile.from_pdf(document.pdf, scale=4)
    result = predictor(doc)
    #result.show(doc)
    dictionary = result.export()

    for page_dict in dictionary['pages']:
        dimensions = (page_dict['dimensions'][0], page_dict['dimensions'][1])
        index = page_dict['page_idx'] + 1
        language = page_dict['language']['value']
        if not language:
            language = 'unknown'
        page = Page(index, language, document, dimensions)
        for block_dict in page_dict['blocks']:
            block_position = get_position(block_dict['geometry'])
            block = Block(page, block_position)
            for line_dict in block_dict['lines']:
                line_position = get_position(line_dict['geometry'])
                line = Line(block, line_position)
                for word_dict in line_dict['words']:
                    word_position = get_position(word_dict['geometry'])
                    word = Word(word_dict['value'], line, word_position)
                    line.add_word(word)
                block.add_line(line)
            page.add_block(block)
        document.pages.append(page)


def locate_metadata(document: Document):
    for metadata_name, metadata_value in document.mayan_metadata.items():
        if metadata_name in METADATA:
            metadata_type = METADATA[metadata_name]['type']
            if metadata_type == 'date':
                date_format = METADATA[metadata_name]['format']
                metadata_value_date = datetime.strptime(
                    metadata_value, date_format)
                metadata = DateMetadata(
                    metadata_name, metadata_type, metadata_value_date)
                document.metadata.append(metadata)

                for page in document.pages:
                    date_tuples = parse_dates(page)
                    for date_tuple in date_tuples:
                        date = date_tuple[0]
                        if date == metadata_value_date:
                            source_words = date_tuple[1]
                            position = calculate_position(source_words)
                            metadata.add_position(page, date_tuple[1], position)

            if metadata_type == 'money':
                metadata_value_price = Price.fromstring(metadata_value)
                metadata = MoneyMetadata(
                    metadata_name, metadata_type, metadata_value_price)
                document.metadata.append(metadata)
                for page in document.pages:
                    prices = parse_prices(page, metadata_value_price.currency)
                    for price in prices:
                        if price[0].amount == metadata_value_price.amount and price[0].currency == metadata_value_price.currency:
                            position = calculate_position(price[1])
                            metadata.add_position(page, price[1], position)
            
            if metadata_type == 'string':
                metadata = Metadata(metadata_name, metadata_type, metadata_value)
                document.metadata.append(metadata)
                for page in document.pages:
                    results = parse_matching_strings(page, metadata_value)
                    for result in results:
                        position = calculate_position(result[0])
                        metadata.add_position(page, result[0], position)

# TODO: If we have a line break between words we get huge areas
def calculate_position(words: list[Word]) -> BoundingBox:
    if len(words) == 1:
        return words[0].position
    l_top_x = sys.maxsize
    l_top_y = sys.maxsize
    r_bot_x = 0
    r_bot_y = 0
    for word in words:
        l_top_x = min(l_top_x, word.position.left_top.x)
        l_top_y = min(l_top_y, word.position.left_top.y)
        r_bot_x = max(r_bot_x, word.position.right_bot.x)
        r_bot_y = max(r_bot_y, word.position.right_bot.y)
    return BoundingBox(((l_top_x, l_top_y), (r_bot_x, r_bot_y)))

# TODO: Find a way to better match filled than empty metadata
def find_best_cluster(document_type: DocumentType, document: Document):
    best_match_score = 0
    best_match_cluster = None
    for cluster in document_type.cluster_map.values():
        cluster_scores = {}
        for meta_key in cluster.metadata.keys():
            if METADATA[meta_key]['groupby']:
                if meta_key not in cluster_scores:
                    cluster_scores[meta_key] = 0
                stop_search = False
                candidates = [synonym for synonym, actual in cluster.synonyms.items() if actual == cluster.metadata[meta_key]]
                candidates.append(cluster.metadata[meta_key])
                for candidate in candidates:
                    for page in document.pages:
                        matches = parse_matching_strings(page, candidate, 1)
                        if matches and len(matches) == 1:
                            page_match = matches[0][1]
                            if page_match > cluster_scores[meta_key]:
                                cluster_scores[meta_key] = page_match
                                if page_match == 100:
                                    stop_search = True
                                    break
                    if stop_search:
                        break
        avg_score = sum(cluster_scores.values()) / len(cluster_scores.values())
        if avg_score > best_match_score:
            best_match_score = avg_score
            best_match_cluster = cluster
    return best_match_cluster, best_match_score

def predict_metadata(cluster: DocumentCluster, document: Document):
    temp_dict = cluster.dictionary
    for word in document.words:
        if word.text not in temp_dict:
            temp_dict[word.text] = len(temp_dict) + 1
    reversed_dict = {key: value for value, key in temp_dict.items()}
    for page in document.pages:
        page_type = cluster.get_page_type_for_document_page(page)
        if page_type:
            page_map = create_page_map(temp_dict, page)
            # Use the same logic as for add_document to find best matching page_type
            plt.imshow(page_type.metadata_map, cmap='hot', interpolation='nearest')
            plt.imshow(page_map, cmap='hot', interpolation='nearest')
            metadata_names = np.unique(page_type.metadata_map)
            for metadata_name in metadata_names:
                # Only search like this for metadata that is expected at this location
                if metadata_name > 0:
                    if not METADATA[reversed_dict[metadata_name]]['groupby']:
                        mask = np.divide(page_type.metadata_map, page_type.metadata_map, where=page_type.metadata_map == metadata_name)
                        plt.imshow(mask, cmap='hot', interpolation='nearest')
                        words, word_counts = np.unique(np.multiply(mask, page_map), return_counts=True)
                        _logger.warning('Page {0} of document {2} contains the following candidates for metadata {1}:'.format(str(page.index), str(reversed_dict[metadata_name]), str(document.mayan_document_id)))
                        i = 0
                        while i < len(words):
                            if words[i] > 0:
                                _logger.warning(str(reversed_dict[words[i]]) + ' -> ' + str(word_counts[i]))
                            i+=1
                        # Add logic to find floating metadata

