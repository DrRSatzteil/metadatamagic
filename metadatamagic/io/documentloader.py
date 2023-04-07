import io
import logging
import os

import numpy as np
import pypdfium2 as pdfium

from ..api import mayan
from ..model import Document

__all__ = ['load_document']

_logger = logging.getLogger(__name__)


def get_mayan_options() -> dict:
    _logger.info('Retrieve initial mayan configuration from environment')
    options = {}
    options['username'] = os.getenv('MAYAN_USER')
    options['password'] = os.getenv('MAYAN_PASSWORD')
    options['url'] = os.getenv('MAYAN_URL')
    return options


def get_mayan() -> mayan.Mayan:
    options = get_mayan_options()
    m = mayan.Mayan(options['url'])
    m.login(options['username'], options['password'])
    _logger.info('Load meta informations from mayan')
    m.load()
    return m


def load_document(document_id):
    m = get_mayan()

    _logger.info('Loading document %s', document_id)

    # Check if document exists
    document, status = m.get(m.ep(f'documents/{str(document_id)}'))
    if not isinstance(document, dict) or status != 200:
        _logger.error('Could not retrieve document')
        return None

    # Load document metadata
    document_metadata = {x['metadata_type']['name']: x for x in m.all(
        m.ep('metadata', base=document['url']))}
    
    document_type = document['document_type']['label']
    document_metadata = {metadata_name: metadata_value['value'] for metadata_name,
                         metadata_value in document_metadata.items()}

    # Load document pdf
    with io.BytesIO(m.downloadfile(document['file_latest']['download_url'])) as buffer:
        buffer.seek(0)
        optimized_pdf = optimize_pdf_for_detection(buffer)

    document = Document(document_id, document_type, document_metadata, optimized_pdf)
    return document

# TODO: Make this work with later versions of pypdfium2


def optimize_pdf_for_detection(pdf):
    _logger.info('Optimizing document for text detection')
    pdf = pdfium.PdfDocument(pdf)
    fontpath = os.path.join('metadatamagic', 'dist', 'fonts', 'FreeMono.otf')
    hb_font = pdfium.HarfbuzzFont(fontpath)
    pdf_font = pdf.add_font(
        fontpath,
        type=pdfium.FPDF_FONT_TRUETYPE,
        is_cid=True,
    )
    for page in pdf:
        for y in np.arange(0, page.get_height(), 50):
            page.insert_text(
                text="___",
                pos_x=page.get_width() * 0.97,
                pos_y=y,
                font_size=10,
                hb_font=hb_font,
                pdf_font=pdf_font
            )
        page.generate_content()

    with io.BytesIO() as buffer:
        pdf.save(buffer, version=17)
        return buffer.getvalue()
