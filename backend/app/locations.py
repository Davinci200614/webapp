"""Literal location cleanup and a small shared spelling dictionary."""
import re
from .employment import normalize


def clean_location(value):
    value = re.sub(r'^(?:في|ف|fi|f)\s+', '', value.strip(), flags=re.IGNORECASE).strip()
    value = re.sub(r'^(?:فنواحي|نواحي)\s+', '', value).strip()
    return re.sub(r'^ف(?=سلا|مكناس|بولمان|[إا]نز[كغ]ان|دكالة|ال)', '', value)


def location_key(value):
    value = normalize(clean_location(value))
    groups = {
        'سلا الجديدة': ('سلا الجديدة', 'سلا جديدة', 'sale al jadida', 'sale el jadida', 'sala al jadida'),
        'انزكان': ('انزكان', 'انزغان', 'inzegane', 'inezgane', 'inzgan', 'inzgane'),
        'بولمان': ('بولمان', 'boulemane', 'boulmane'),
        'مكناس': ('مكناس', 'meknes'),
        'فاس': ('فاس', 'fes', 'fez'),
    }
    for canonical, variants in groups.items():
        for variant in variants:
            value = re.sub(r'(?<!\w)' + re.escape(variant) + r'(?!\w)', canonical, value)
    return value


def is_literal_location(value):
    """Only short place-like replies may bypass semantic understanding."""
    value = value.strip()
    if not value or len(value.split()) > 4:
        return False
    return re.search(
        r'(?<!\w)(?:خويا|اخويا|كاينة|كاين|كينا|كين|عندي|عندنا|واحد|شي|الأرض|الارض|ارض|أرض|'
        r'بغيت|كنقلب|ماعرفتش|فين|واش|قريبة|قريب|قرب|حدا|تقريبا|نعم|لا|تعديل|'
        r'mon|ma|terrain|terre|situé|situe|située|situee|près|pres|vers|chez|je|nous|my|near|located)(?!\w)',
        value, flags=re.IGNORECASE,
    ) is None
