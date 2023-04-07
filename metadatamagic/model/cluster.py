import logging
import hashlib
import numpy as np

from .document import BoundingBox, Document, Page

CLUSTER_RESOLUTION = (round(3508/2), round(2480/2))
PAGE_TYPE_MIN_FIT = 20

__all__ = ['DocumentCluster', 'DocumentType', 'create_page_map']

_logger = logging.getLogger(__name__)

def get_cluster_id(mayan_document_type, metadata):
    id_string = str(mayan_document_type) + ''.join([metadata_name for metadata_name in sorted(metadata.keys())])
    return hashlib.md5(str.encode(id_string)).hexdigest()

def get_page_metadata(page: Page):
    page_metadata = []
    for metadata in page.parentdocument.metadata:
        for occurrence in metadata.occurrences:
            if occurrence[0] == page:
                page_metadata.append((metadata, occurrence))
                break
    return page_metadata

def get_best_fit_page_type():
    pass

def create_page_map(dictionary: dict, page: Page) -> np.array:
    page_map = np.zeros(shape=CLUSTER_RESOLUTION, dtype=int)
    for word in page.words:
        top = round(word.position.left_top.y * CLUSTER_RESOLUTION[0])
        bot = round(word.position.right_bot.y * CLUSTER_RESOLUTION[0])
        left = round(word.position.left_top.x * CLUSTER_RESOLUTION[1])
        right = round(word.position.right_bot.x * CLUSTER_RESOLUTION[1])
        page_map[top: bot, left: right] = dictionary[word.text]
    return page_map

# TODO: Make removal of pages possible...


class PageType:

    def __init__(self, parent_cluster) -> None:
        self.parent_cluster = parent_cluster
        self.number_of_pages = 0
        self.words = None
        self.metadata_map = None
    
    def remove_page(self, page: Page):
        # TODO: Do stuff
        pass

    def add_page(self, page: Page):
        self.remove_page(page)
        if self.words is None:
            self.words = page.words
        else:
            delete = []
            for word in self.words:
                overlap = False
                for new_word in page.words:
                    if word.text == new_word.text:
                        if word.position.overlaps(new_word.position):
                            overlap = True
                            break
                if not overlap:
                    delete.append(word)
            self.words = [word for word in self.words if word not in delete]
        # TODO Return an easier to handle data structure and/or make an occurrence class in Metadata class
        metadatas = get_page_metadata(page)
        for metadata in metadatas:
            text = ' '.join([word.text for word in metadata[1][1]])
            mayan_metadata_value = self.parent_cluster.metadata[metadata[0].metadata_name]
            if text != mayan_metadata_value:
                # There could be collisions here but this probably won't hurt too much
                self.parent_cluster.add_synonym(mayan_metadata_value, text)
            # TODO: Skip the location mapping for metadata that is part of the cluster id
            position = metadata[1][2]
            # There could be collisions here as well (especially when metadata is split across lines). This might hurt more...
            self.__map_metadata(metadata[0].metadata_name, position)
        self.number_of_pages += 1

    def __map_metadata(self, mayan_metadata_name: str, position: BoundingBox):
        if self.metadata_map is None:
            self.metadata_map = np.zeros(shape=CLUSTER_RESOLUTION, dtype=int)
        top = round(position.left_top.y * CLUSTER_RESOLUTION[0])
        bot = round(position.right_bot.y * CLUSTER_RESOLUTION[0])
        left = round(position.left_top.x * CLUSTER_RESOLUTION[1])
        right = round(position.right_bot.x * CLUSTER_RESOLUTION[1])
        self.metadata_map[top: bot,
                          left: right] = self.parent_cluster.dictionary[mayan_metadata_name]

    def calculate_fit(self, page: Page):
        if self.words is None or len(self.words) == 0:
            return 0
        else:
            matches = 0
            for new_word in page.words:
                found_current = False
                for block in page.blocks:
                    if block.position.overlaps(new_word.position):
                        for line in block.lines:
                            if line.position.overlaps(new_word.position):
                                for word in self.words:
                                    if word.text == new_word.text:
                                        if word.position.overlaps(new_word.position):
                                            matches += 1
                                            found_current = True
                                            break
                            if found_current:
                                break
                    if found_current:
                        break
            return round((matches / len(self.words)) * 100)

class DocumentType:

    def __init__(self, mayan_document_type: str) -> None:
        self.mayan_document_type = mayan_document_type
        self.cluster_map = {}
    
    def get_document_cluster(self, metadata: dict[str, str]):
        cluster_id = get_cluster_id(self.mayan_document_type, metadata)
        if cluster_id in self.cluster_map and self.cluster_map[cluster_id] is not None:
            return self.cluster_map[cluster_id]
        else:
            cluster = DocumentCluster(self, cluster_id, metadata)
            self.cluster_map[cluster.cluster_id] = cluster
            return cluster

class DocumentCluster:

    def __init__(self, document_type: DocumentType, cluster_id: str, metadata: dict[str, str]) -> None:
        self.document_type = document_type
        self.cluster_id = cluster_id
        self.metadata = metadata
        self.dictionary = None
        self.synonyms = None
        self.page_types = None

    def add_document(self, document: Document):
        self.__update_dictionary(document)
        self.__update_page_types(document)

    def add_synonym(self, word: str, synonym: str):
        self.synonyms[synonym] = word
        self.document_type

    def __update_dictionary(self, document: Document):
        for word in document.words:
            if word.text not in self.dictionary:
                self.dictionary[word.text] = len(self.dictionary) + 1
    
    def get_page_type_for_document_page(self, page: Page) -> PageType:
        best_fit = 0
        best_fit_page_type = None
        for page_type in self.page_types:
            fit = page_type.calculate_fit(page)
            if fit > best_fit:
                best_fit = fit
                best_fit_page_type = page_type
            min_fit = PAGE_TYPE_MIN_FIT
            # When we already merged two pages we should come close to 100 in the following successions (OCR errors and the like )
        if page_type.number_of_pages > 1:
            min_fit = 95
        if best_fit >= min_fit:
            return best_fit_page_type

    def __update_page_types(self, document: Document):
        for page in document.pages:
            metadata = get_page_metadata(page)
            if len(metadata) > 0:
                if len(self.page_types) == 0:
                    self.page_types.append(PageType(self))
                    self.page_types[0].add_page(page)
                else:
                    page_type = self.get_page_type_for_document_page(page)
                    if not page_type:
                        page_type = PageType(self)
                        self.page_types.append(page_type)
                    page_type.add_page(page)
