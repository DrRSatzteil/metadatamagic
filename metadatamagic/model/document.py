import logging
from datetime import datetime
from typing import Any
from price_parser import Price

__all__ = ['Document', 'Page', 'Block', 'Line', 'Word', 'Metadata', 'DateMetadata', 'MoneyMetadata', 'BoundingBox', 'Point']

_logger = logging.getLogger(__name__)


class Point:

    def __init__(self, x, y) -> None:
        self.x = x
        self.y = y
    
    def is_inside_box(self, box):
        return (box.left_top.x <= self.x <= box.right_bot.x and box.left_top.y <= self.y <= box.right_bot.y)


class BoundingBox:

    def __init__(self, position) -> None:
        self.left_top = Point(position[0][0], position[0][1])
        self.left_bot = Point(position[0][0], position[1][1])
        self.right_top = Point(position[1][0], position[0][1])
        self.right_bot = Point(position[1][0], position[1][1])
    
    def __iter__(self):
        yield self.left_top
        yield self.right_top
        yield self.right_bot
        yield self.left_bot
    
    def overlaps(self, box) -> bool:
        for corner in self:
            if corner.is_inside_box(box):
                return True
        for corner in box:
            if corner.is_inside_box(self):
                return True
        return False

class Document:

    def __init__(self, mayan_document_id, mayan_document_type, mayan_metadata, pdf) -> None:
        self.mayan_document_id = mayan_document_id
        self.mayan_document_type = mayan_document_type
        self.mayan_metadata = mayan_metadata
        self.pdf = pdf
        self.pages = []
        self.blocks = []
        self.lines = []
        self.words = []
        self.metadata = []


class PageElement():

    def __init__(self, parent, position=None, dimensions=None) -> None:
        if isinstance(self, Page):
            self.parentdocument = parent
            # (height, width)
            self.dimensions = dimensions
            self.blocks = []
            self.lines = []
            self.words = []
            return
        if isinstance(self, Block):
            self.parentpage = parent
            self.parentdocument = self.parentpage.parentdocument
            self.lines = []
            self.words = []
        if isinstance(self, Line):
            self.parentblock = parent
            self.parentpage = self.parentblock.parentpage
            self.parentdocument = self.parentpage.parentdocument
            self.words = []
        if isinstance(self, Word):
            self.parentline = parent
            self.parentblock = self.parentline.parentblock
            self.parentpage = self.parentblock.parentpage
            self.parentdocument = self.parentpage.parentdocument
        if position:
            self.position = BoundingBox(position)

    def get_parent(self):
        if isinstance(self, Page):
            return self.parentdocument
        if isinstance(self, Block) or isinstance(self, Metadata):
            return self.parentpage
        if isinstance(self, Line):
            return self.parentblock
        if isinstance(self, Word):
            return self.parentline

    def add_word(self, word):
        if not isinstance(self, Word):
            self.words.append(word)
            parent = self.get_parent()
            if isinstance(parent, Document):
                parent.words.append(word)
            else:
                parent.add_word(word)

    def add_line(self, line):
        if not isinstance(self, Line) and not isinstance(self, Word):
            self.lines.append(line)
            parent = self.get_parent()
            if isinstance(parent, Document):
                parent.lines.append(line)
            else:
                parent.add_line(line)

    def add_block(self, block):
        if isinstance(self, Page):
            self.blocks.append(block)
            self.parentdocument.blocks.append(block)

    def set_position(self, position: tuple):
        if not isinstance(self, Page):
            if position:
                self.position = BoundingBox(position)


class Page(PageElement):

    def __init__(self, index, language, parentdocument: Document, dimensions: tuple) -> None:
        super().__init__(parentdocument, dimensions=dimensions)
        self.index = index
        self.language = language
        self.parentdocument = parentdocument
        self.dimensions = dimensions
        self.blocks = []
        self.metadata = []


class Block(PageElement):

    def __init__(self, parentpage: Page, position: tuple) -> None:
        super().__init__(parentpage, position=position)


class Line(PageElement):

    def __init__(self, parentblock: Block, position: tuple) -> None:
        super().__init__(parentblock, position=position)


class Word(PageElement):

    def __init__(self, text: str, parentline: Line, position: tuple) -> None:
        super().__init__(parentline, position=position)
        self.text = text


class Metadata():

    def __init__(self, metadata_name: str, metadata_type: str, metadata_value: Any) -> None:
        self.metadata_name = metadata_name
        self.metadata_type = metadata_type
        self.metadata_value = metadata_value
        self.occurrences = []

    def add_position(self, page: Page, words: list[Word], position: BoundingBox):
        self.occurrences.append((page, words, position))


class DateMetadata(Metadata):

    def __init__(self, metadata_name: str, metadata_type: str, metadata_value: datetime) -> None:
        super().__init__(metadata_name, metadata_type, metadata_value)

class MoneyMetadata(Metadata):

    def __init__(self, metadata_name: str, metadata_type: str, metadata_value: Price) -> None:
        super().__init__(metadata_name, metadata_type, metadata_value)
