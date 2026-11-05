"""Example cooperative checklist, not a statement of legal requirements."""
from . import config

def examples():
    return [text.strip() for text in config.DOCUMENT_CHECKLIST.split(';') if text.strip()]

def message(request_id=None):
    heading=f'الطلب #{request_id}\n' if request_id else ''
    return heading+'لائحة أولية كمثال فقط، ماشي وثائق مفروضة قانونيا:\n'+'\n'.join('• '+item for item in examples())+'\nصيفط غير الوثائق اللي عندك واللي كتخص الطلب، وخبّي المعطيات الشخصية اللي ما محتاجينهاش. الإدارة كتراجعهم وتقدر تطلب وثائق إضافية. PDF أو JPEG/PNG، حتى 5 ميغا للوثيقة.'+(f'\nزيد #{request_id} فالوصف ملي تصيفط الوثائق.' if request_id else '\nمن بعد تأكيد الطلب، صيفط الوثائق مع رقم الطلب فالوصف.')
