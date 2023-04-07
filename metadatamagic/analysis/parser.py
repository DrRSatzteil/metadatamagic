import logging

from babel import Locale
from dateparser.date import DateDataParser
from thefuzz import fuzz
from price_parser import Price

from ..io import DEFAULT_LANGUAGE, MIN_CONFIDENCE
from ..model import Page, Word

__all__ = ['parse_dates', 'parse_prices', 'parse_matching_strings']

_logger = logging.getLogger(__name__)

DATE_PARSER_SETTINGS = {'PREFER_DAY_OF_MONTH': 'first',
                        'PREFER_DATES_FROM': 'past', 'REQUIRE_PARTS': ['month', 'year']}


def parse_dates(page: Page):
    dates = []
    parser = get_date_parser(page.language, DEFAULT_LANGUAGE)
    combinations = create_word_combinations(page.words, max_length=3)
    for combination in combinations:
        text = ' '.join([word.text for word in combination])
        # Compensate common OCR errors
        text = text.replace('O', '0')
        try:
            date = parser.get_date_data(text)
            if date.date_obj is not None:
                dates.append((date.date_obj, combination))
        except Exception as e:
            logging.warning(
                'Failed to parse date for text {0}: {1}'.format(text, e))
    return dates


def parse_prices(page: Page, currency: str):
    prices = []
    separators = get_decimal_separators(page.language, DEFAULT_LANGUAGE)
    for word in page.words:
        for sep in separators:
            price = Price.fromstring(
                word.text, currency_hint=currency, decimal_separator=sep)
            if price.amount and price.currency:
                prices.append((price, [word]))
    return prices


def parse_matching_strings(page: Page, search: str, limit: int=None):
    results = []
    for block in page.blocks:
        block_results = []
        combos = create_word_combinations(block.words, len(block.words))
        for combo in combos:
            _, _, combo_ratio = match_score(search, combo)
            if combo_ratio > MIN_CONFIDENCE * 0.8:
                block_results.append((combo, combo_ratio))
        for result_tuple in block_results:
            if not has_better_match(result_tuple, block_results):
                results.append(result_tuple)
    if len(results) > 0:
        results_sorted = sorted(results, key = lambda x: x[1], reverse=True)
        if limit and len(results) > limit:
            return results_sorted[:limit]
        return results_sorted
    return results


def match_score(search: str, words: list[Word]) -> tuple[int, int, int]:
    text_low = get_string_from_words(words).lower()
    search_low = search.lower()
    ratio = fuzz.ratio(search_low, text_low)
    partial_ratio = fuzz.partial_ratio(search_low, text_low)
    combo_ratio = round((ratio * partial_ratio) / 100)
    return (ratio, partial_ratio, combo_ratio)


def has_better_match(matching_combo: tuple[list[Word], int], all_combos: list[tuple[list[Word], int]]):
    for compare in all_combos:
        if any(word in matching_combo[0] for word in compare[0]):
            if not matching_combo[0] == compare[0]:
                if matching_combo[1] < compare[1]:
                    return True
    return False


def get_string_from_words(input):
    if isinstance(input, str):
        return input
    if isinstance(input, list):
        return ' '.join(word.text for word in input if isinstance(word, Word))


def create_word_combinations(words: list[Word], max_length=1) -> list[Word]:
    result = []
    if max_length == 0:
        return result

    lastwords = []
    for word in words:
        result.append([word])
        i = 0
        while i < len(lastwords):
            sliced = lastwords[i:]
            sliced.append(word)
            result.append(sliced)
            i += 1

        if len(lastwords) >= max_length:
            lastwords.pop()
        lastwords.append(word)
    return result


def get_date_parser(language: str = None, fallback_language: str = None) -> DateDataParser:
    if language is None:
        if fallback_language is not None:
            return get_date_parser(language=fallback_language)
        else:
            return get_date_parser('unknown')

    if language == 'unknown':
        return DateDataParser(settings=DATE_PARSER_SETTINGS)
    else:
        try:
            parser = DateDataParser(
                languages=[language], settings=DATE_PARSER_SETTINGS)
            # Unfortunately the DateDataParser constructor does not throw an exception when we use unsupported languages so
            # we only know if the parser works when we use it for the first time...
            parser.get_date_data('1970/01/01')
            return parser
        except:
            _logger.warning(
                'Could not retrieve parser for language {0}. Returning fallback parser'.format(language))
            # Return the default parser. Fall back to no language if default is also not found
            if language == fallback_language:
                return get_date_parser('unknown')
            else:
                return get_date_parser(language=fallback_language)


def get_decimal_separators(language: str = None, fallback_language: str = None) -> str:
    try:
        locale = Locale(language)
        decimal = {'.'}
        decimal.update(locale.number_symbols['decimal'])
        return decimal
    except Exception as e:
        _logger.warning('Language {0} is not supported'.format(language))
        if language == fallback_language:
            return {'.'}
        else:
            return get_decimal_separators(language=fallback_language)
