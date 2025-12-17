"""
Парсер изображений для извлечения данных о заказе из скриншотов
Поддерживает Chefmarket и другие форматы
"""
import logging
import re
import os
from typing import Dict, Optional, List
from PIL import Image
import pytesseract
import io

logger = logging.getLogger(__name__)

# Служебные фразы, которые не должны попадать в поля заказа
SERVICE_PHRASES = [
    'заказ оплачен',
    'адрес доставки',
    'написать',
    'основной',
    'комментарий к заказу',
    'комментарий',
    'доставлен',
    'возврат',
    'покупатель',
    'buyer',
    'delivery address',
    'comment to order',
    'delivered',
    'return',
    'order paid',
    'write',
    'main',
    'заказы',
    'orders',
    'профиль',
    'profile'
]

# Словарь для исправления частых OCR ошибок в именах
OCR_NAME_FIXES = {
    'днастасия': 'Анастасия',
    'анастасия': 'Анастасия',
    'виталий': 'Виталий',
    'иван': 'Иван',
    'мария': 'Мария',
    'елена': 'Елена',
    'ольга': 'Ольга',
    'татьяна': 'Татьяна',
    'наталья': 'Наталья',
    'сергей': 'Сергей',
    'андрей': 'Андрей',
    'дмитрий': 'Дмитрий',
    'александр': 'Александр',
    'максим': 'Максим',
    'артем': 'Артем',
    'алексей': 'Алексей',
    'павел': 'Павел',
    'николай': 'Николай',
    'михаил': 'Михаил',
}


class ImageOrderParser:
    """Парсер заказов из изображений (скриншотов)"""
    
    def __init__(self):
        # Настройка Tesseract
        # Приоритет: переменная окружения > автоматическое определение
        import os
        tesseract_cmd = os.getenv('TESSERACT_CMD')
        
        if tesseract_cmd:
            # Используем путь из переменной окружения
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            logger.debug(f"Используется Tesseract из переменной окружения: {tesseract_cmd}")
        elif os.path.exists('/usr/bin/tesseract'):
            # Docker/Linux (стандартный путь)
            pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
            logger.debug("Используется Tesseract из /usr/bin/tesseract (Docker/Linux)")
        elif os.path.exists('/usr/local/bin/tesseract'):
            # Mac/Linux альтернативный путь
            pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'
            logger.debug("Используется Tesseract из /usr/local/bin/tesseract (Mac/Linux)")
        # Для Windows путь можно задать через переменную окружения TESSERACT_CMD
        # или он будет найден автоматически, если Tesseract установлен в стандартное место
        
        # Проверяем доступность Tesseract
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract OCR успешно инициализирован (версия: {version})")
        except Exception as e:
            logger.warning(f"Tesseract OCR не найден: {e}. Установите Tesseract для работы с изображениями.")
            # В Docker это не должно происходить, но на всякий случай логируем
    
    def parse_order_from_image(self, image_data: bytes) -> Optional[Dict]:
        """
        Извлечение данных о заказе из изображения
        
        Args:
            image_data: Байты изображения
            
        Returns:
            Словарь с данными заказа или None
        """
        logger.info("📸 Начало парсинга изображения заказа")
        logger.debug(f"Размер изображения: {len(image_data)} байт")
        
        try:
            # Открываем изображение
            image = Image.open(io.BytesIO(image_data))
            image_size = image.size
            image_format = image.format
            logger.info(f"📷 Изображение открыто: размер {image_size[0]}x{image_size[1]}, формат {image_format}")
            
            # Извлекаем текст с помощью OCR
            # Используем русский и английский языки
            logger.info("🔍 Начало OCR распознавания текста (rus+eng)...")
            ocr_start_time = __import__('time').time()
            try:
                text = pytesseract.image_to_string(image, lang='rus+eng')
                logger.info(f"✅ OCR завершен успешно (rus+eng), извлечено {len(text)} символов")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка OCR с русским языком: {e}, пробуем только английский")
                try:
                    text = pytesseract.image_to_string(image, lang='eng')
                    logger.info(f"✅ OCR завершен успешно (eng), извлечено {len(text)} символов")
                except Exception as e2:
                    logger.error(f"❌ Ошибка OCR даже с английским языком: {e2}")
                    raise
            
            ocr_duration = __import__('time').time() - ocr_start_time
            logger.info(f"⏱️ OCR занял {ocr_duration:.2f} секунд")
            
            # Логируем весь извлеченный текст
            logger.info(f"📝 Полный текст, извлеченный из изображения ({len(text)} символов, {len(text.splitlines())} строк):")
            logger.info(f"═══════════════════════════════════════════════════════════════")
            logger.info(f"{text}")
            logger.info(f"═══════════════════════════════════════════════════════════════")
            logger.info(f"📊 Статистика текста: всего символов={len(text)}, строк={len(text.splitlines())}")
            
            # Парсим данные из текста
            logger.info("🔎 Начало парсинга извлеченного текста...")
            parse_start_time = __import__('time').time()
            order_data = self._parse_text(text)
            parse_duration = __import__('time').time() - parse_start_time
            logger.info(f"⏱️ Парсинг занял {parse_duration:.2f} секунд")
            
            if order_data:
                logger.info(f"✅ Парсинг успешно завершен, извлечено полей: {len(order_data)}")
                logger.info(f"📦 Извлеченные данные: {order_data}")
            else:
                logger.warning("⚠️ Парсинг не вернул данных (обязательные поля не найдены)")
            
            return order_data
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка парсинга изображения: {e}", exc_info=True)
            return None
    
    def _filter_service_phrases(self, text: str) -> str:
        """Удаление служебных фраз из текста (для последующей очистки полей)."""
        filtered_text = text
        for phrase in SERVICE_PHRASES:
            # Удаляем фразу с учетом регистра и границ слов
            pattern = r'\b' + re.escape(phrase) + r'\b'
            filtered_text = re.sub(pattern, '', filtered_text, flags=re.IGNORECASE)
        # Удаляем множественные пробелы
        filtered_text = re.sub(r'\s+', ' ', filtered_text)
        return filtered_text.strip()

    def _clean_field_value(self, value: str) -> str:
        """
        Общая очистка значения поля от служебных фраз и мелких OCR‑артефактов.
        Используется после того, как поле уже извлечено (адрес, имя, комментарий и т.п.).
        """
        if not value:
            return value

        # Удаляем служебные фразы
        cleaned_value = self._filter_service_phrases(value)

        # Убираем одиночные/двойные не буквенно‑цифровые символы, оставшиеся после OCR
        cleaned_value = re.sub(r'\b[^\w\s]{1,2}\b', '', cleaned_value)

        # Нормализуем пробелы
        cleaned_value = re.sub(r'\s+', ' ', cleaned_value).strip()
        return cleaned_value
    
    def _fix_ocr_name_errors(self, name: str) -> str:
        """Исправление частых OCR ошибок в именах"""
        if not name:
            return name
        
        name_lower = name.lower()
        
        # Исправляем частую ошибку OCR: "д" вместо "А" в начале имени
        # Например: "днастасия" -> "Анастасия"
        if name_lower.startswith('дна') or name_lower.startswith('дн'):
            if 'настасия' in name_lower or 'наста' in name_lower:
                fixed_name = 'Анастасия'
                logger.debug(f"🔧 Исправлено имя (OCR ошибка 'д'->'А'): '{name}' -> '{fixed_name}'")
                return fixed_name
        
        # Проверяем словарь исправлений
        if name_lower in OCR_NAME_FIXES:
            fixed_name = OCR_NAME_FIXES[name_lower]
            logger.debug(f"🔧 Исправлено имя: '{name}' -> '{fixed_name}'")
            return fixed_name
        
        # Если имя начинается с маленькой буквы, но это известное имя - исправляем
        if name[0].islower():
            name_capitalized = name[0].upper() + name[1:] if len(name) > 1 else name.upper()
            name_lower_cap = name_capitalized.lower()
            if name_lower_cap in OCR_NAME_FIXES:
                fixed_name = OCR_NAME_FIXES[name_lower_cap]
                logger.debug(f"🔧 Исправлено имя (с заглавной): '{name}' -> '{fixed_name}'")
                return fixed_name
        
        # Если имя начинается с маленькой буквы, делаем первую букву заглавной
        if name[0].islower() and len(name) > 1:
            fixed_name = name[0].upper() + name[1:]
            logger.debug(f"🔧 Исправлена заглавная буква: '{name}' -> '{fixed_name}'")
            return fixed_name
        
        return name
    
    def _parse_text(self, text: str) -> Optional[Dict]:
        """
        Парсинг текста для извлечения данных заказа
        
        Args:
            text: Текст, извлеченный из изображения
            
        Returns:
            Словарь с данными заказа
        """
        logger.debug("🔍 Начало парсинга текста для извлечения данных заказа")
        # НЕ удаляем служебные фразы из всего текста сразу - они нужны для поиска секций
        # Вместо этого удаляем их из конкретных полей после извлечения
        order_data = {}
        extracted_fields = []
        
        # 1. Номер заказа
        logger.debug("🔎 Поиск номера заказа...")
        order_number = self._extract_order_number(text)
        if order_number:
            order_data['order_number'] = order_number
            extracted_fields.append(f"order_number={order_number}")
            logger.info(f"✅ Номер заказа найден: {order_number}")
        else:
            logger.warning("⚠️ Номер заказа не найден")
        
        # 2. Адрес доставки
        logger.debug("🔎 Поиск адреса доставки...")
        address = self._extract_address(text)
        if address:
            order_data['address'] = address
            extracted_fields.append(f"address={address[:50]}...")
            logger.info(f"✅ Адрес найден: {address[:100]}...")
            
            # Извлекаем подъезд и квартиру из адреса
            entrance_match = re.search(r'подъезд\s+(\d+)', address, re.IGNORECASE)
            if entrance_match:
                order_data['entrance_number'] = entrance_match.group(1)
                extracted_fields.append(f"entrance_number={entrance_match.group(1)}")
                logger.info(f"✅ Подъезд найден: {entrance_match.group(1)}")
            
            apartment_match = re.search(r'кв\.?\s*(\d+)', address, re.IGNORECASE)
            if apartment_match:
                order_data['apartment_number'] = apartment_match.group(1)
                extracted_fields.append(f"apartment_number={apartment_match.group(1)}")
                logger.info(f"✅ Квартира найдена: {apartment_match.group(1)}")
        else:
            logger.warning("⚠️ Адрес доставки не найден")
        
        # 3. Имя покупателя
        logger.debug("🔎 Поиск имени покупателя...")
        customer_name = self._extract_customer_name(text)
        if customer_name:
            order_data['customer_name'] = customer_name
            extracted_fields.append(f"customer_name={customer_name}")
            logger.info(f"✅ Имя покупателя найдено: {customer_name}")
        else:
            logger.debug("ℹ️ Имя покупателя не найдено (необязательное поле)")
        
        # 4. Телефон
        logger.debug("🔎 Поиск телефона...")
        phone = self._extract_phone(text)
        if phone:
            order_data['phone'] = phone
            extracted_fields.append(f"phone={phone}")
            logger.info(f"✅ Телефон найден: {phone}")
        else:
            logger.debug("ℹ️ Телефон не найден (необязательное поле)")
        
        # 5. Комментарий
        logger.debug("🔎 Поиск комментария...")
        comment = self._extract_comment(text)
        if comment:
            order_data['comment'] = comment
            extracted_fields.append(f"comment={comment[:50]}...")
            logger.info(f"✅ Комментарий найден: {comment[:100]}...")
        else:
            logger.debug("ℹ️ Комментарий не найден (необязательное поле)")
        
        # 6. Временное окно доставки
        logger.debug("🔎 Поиск временного окна доставки...")
        time_window = self._extract_delivery_time_window(text)
        if time_window:
            order_data['delivery_time_window'] = time_window
            extracted_fields.append(f"delivery_time_window={time_window}")
            logger.info(f"✅ Временное окно доставки найдено: {time_window}")
        else:
            logger.debug("ℹ️ Временное окно доставки не найдено (необязательное поле)")
        
        logger.info(f"📊 Итого извлечено полей: {len(order_data)} ({', '.join(extracted_fields)})")
        
        # Проверяем обязательные поля
        if not order_data.get('order_number') or not order_data.get('address'):
            missing_fields = []
            if not order_data.get('order_number'):
                missing_fields.append('номер заказа')
            if not order_data.get('address'):
                missing_fields.append('адрес')
            logger.warning(f"❌ Не удалось извлечь обязательные поля: {', '.join(missing_fields)}")
            return None
        
        logger.info("✅ Парсинг текста успешно завершен, все обязательные поля найдены")
        return order_data
    
    def _extract_order_number(self, text: str) -> Optional[str]:
        """Извлечение номера заказа"""
        logger.debug("🔍 Поиск номера заказа с помощью регулярных выражений...")
        # Паттерны: "Заказ № 3269184", "Заказ №3269184", "3269184"
        patterns = [
            (r'Заказ\s*№?\s*(\d+)', 'Заказ № N'),
            (r'order\s*№?\s*(\d+)', 'order № N'),
            (r'№\s*(\d{6,})', '№ N (6+ цифр)'),
        ]
        
        for pattern, description in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                order_number = match.group(1)
                logger.debug(f"✅ Номер заказа найден паттерном '{description}': {order_number}")
                return order_number
        
        logger.debug("⚠️ Номер заказа не найден ни одним из паттернов")
        return None
    
    def _extract_address(self, text: str) -> Optional[str]:
        """Извлечение адреса доставки"""
        logger.debug("🔍 Поиск адреса доставки с помощью регулярных выражений...")
        # Ищем секцию "Адрес доставки:" или "Delivery address:"
        # Используем более гибкий паттерн, который захватывает многострочный адрес до "Покупатель:"
        address_patterns = [
            (r'Адрес\s+доставки:?\s*(.+?)(?=\n\s*Покупатель:|\n\s*Buyer:|\n\s*Имя:|\n\s*Телефон:|\n\s*Phone:)', 'Адрес доставки:'),
            (r'Delivery\s+address:?\s*(.+?)(?=\n\s*Покупатель:|\n\s*Buyer:|\n\s*Имя:|\n\s*Телефон:|\n\s*Phone:)', 'Delivery address:'),
            (r'Адрес:?\s*(.+?)(?=\n\s*Покупатель:|\n\s*Buyer:)', 'Адрес:'),
        ]
        
        for pattern, description in address_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                address_raw = match.group(1).strip()
                logger.debug(f"🔍 Найден адрес паттерном '{description}': {address_raw[:200]}...")
                
                # Разбиваем на строки и очищаем каждую
                lines = address_raw.split('\n')
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    # Пропускаем пустые строки и маркеры бесконтактной доставки
                    if not line or re.match(r'^!?\s*Бесконтактная\s*$', line, re.IGNORECASE):
                        continue
                    # Удаляем служебные фразы из строки адреса
                    line_cleaned = self._clean_field_value(line)
                    if not line_cleaned:
                        continue
                    
                    # Убираем артефакты OCR (одиночные символы типа "&", "97.4," и т.д.)
                    # Но сохраняем если это часть адреса (например, "д 52 к 3")
                    if len(line_cleaned) > 1 or line_cleaned in [',', '.', '-']:
                        cleaned_lines.append(line_cleaned)
                
                # Объединяем строки в один адрес
                address = ' '.join(cleaned_lines)
                
                # Дополнительная очистка: убираем артефакты OCR
                # Убираем паттерны типа "97.4," или "&" в конце строк
                address = re.sub(r'\s+\d+\.\d+,\s*', ' ', address)  # Убираем "97.4,"
                address = re.sub(r'\s+&\s*$', '', address)  # Убираем "&" в конце
                address = re.sub(r'\s+&\s+', ' ', address)  # Убираем "&" в середине
                address = re.sub(r'\s+', ' ', address)  # Нормализуем пробелы
                address = address.strip()
                
                # Удаляем служебные фразы из адреса
                address = self._clean_field_value(address)
                logger.debug(f"🧹 Очищенный адрес: {address[:200]}...")
                
                if len(address) > 10:  # Минимальная длина адреса
                    logger.debug(f"✅ Адрес валиден (длина {len(address)} символов): {address[:100]}...")
                    return address
                else:
                    logger.debug(f"⚠️ Адрес слишком короткий ({len(address)} символов), пропускаем")
        
        logger.debug("⚠️ Адрес доставки не найден ни одним из паттернов")
        return None
    
    def _extract_customer_name(self, text: str) -> Optional[str]:
        """Извлечение имени покупателя"""
        logger.debug("🔍 Поиск имени покупателя с помощью регулярных выражений...")
        # Паттерны: "Имя: Виталий", "Name: Vitaliy"
        patterns = [
            (r'Имя:?\s*([А-Яа-яЁёA-Za-z]+)', 'Имя:'),
            (r'Name:?\s*([А-Яа-яЁёA-Za-z]+)', 'Name:'),
            (r'Покупатель:.*?Имя:?\s*([А-Яа-яЁёA-Za-z]+)', 'Покупатель: Имя:'),
        ]
        
        for pattern, description in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                logger.debug(f"🔍 Найдено имя паттерном '{description}': {name}")
                
                # Удаляем служебные фразы из имени
                name = self._clean_field_value(name)
                
                # Исправляем OCR ошибки
                name = self._fix_ocr_name_errors(name)
                
                if len(name) >= 2:  # Минимальная длина имени
                    logger.debug(f"✅ Имя валидно (длина {len(name)} символов): {name}")
                    return name
                else:
                    logger.debug(f"⚠️ Имя слишком короткое ({len(name)} символов), пропускаем")
        
        logger.debug("⚠️ Имя покупателя не найдено ни одним из паттернов")
        return None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Извлечение телефона"""
        logger.debug("🔍 Поиск телефона с помощью регулярных выражений...")
        # Паттерны: "+79118364369", "79118364369", "8 (911) 836-43-69"
        phone_patterns = [
            (r'Телефон:?\s*(\+?7\d{10})', 'Телефон:'),
            (r'Phone:?\s*(\+?7\d{10})', 'Phone:'),
            (r'(\+7\d{10})', '+7XXXXXXXXXX'),
            (r'(8\d{10})', '8XXXXXXXXXX'),
            (r'(\+?\d[\d\s\-\(\)]{9,})', 'гибкий паттерн'),
        ]
        
        for pattern, description in phone_patterns:
            match = re.search(pattern, text)
            if match:
                phone_raw = match.group(1)
                logger.debug(f"🔍 Найден телефон паттерном '{description}': {phone_raw}")
                
                # Очищаем от пробелов и символов
                phone = re.sub(r'[\s\-\(\)]', '', phone_raw)
                logger.debug(f"🧹 Телефон после очистки: {phone}")
                
                # Нормализуем формат
                phone_before = phone
                if phone.startswith('8'):
                    phone = '+7' + phone[1:]
                    logger.debug(f"🔄 Нормализация: 8... -> +7...")
                elif not phone.startswith('+'):
                    phone = '+7' + phone
                    logger.debug(f"🔄 Нормализация: добавлен +7")
                
                if len(phone) >= 11:  # Минимальная длина телефона
                    logger.debug(f"✅ Телефон валиден (длина {len(phone)} символов): {phone}")
                    return phone
                else:
                    logger.debug(f"⚠️ Телефон слишком короткий ({len(phone)} символов), пропускаем")
        
        logger.debug("⚠️ Телефон не найден ни одним из паттернов")
        return None
    
    def _extract_comment(self, text: str) -> Optional[str]:
        """Извлечение комментария к заказу"""
        logger.debug("🔍 Поиск комментария к заказу...")
        # Ищем секцию "Комментарий к заказу:" или "Comment to order:"
        comment_patterns = [
            (r'Комментарий\s+к\s+заказу:?\s*(.+?)(?=\n\n|\nДоставлен|\nDelivered|\nВозврат|\nReturn|$)', 'Комментарий к заказу:'),
            (r'Comment\s+to\s+order:?\s*(.+?)(?=\n\n|\nДоставлен|\nDelivered|\nВозврат|\nReturn|$)', 'Comment to order:'),
            (r'Комментарий:?\s*(.+?)(?=\n\n|\nДоставлен|\nDelivered|$)', 'Комментарий:'),
        ]
        
        comments = []
        
        # Проверяем на бесконтактную доставку
        if re.search(r'бесконтактная', text, re.IGNORECASE):
            comments.append("Бесконтактная доставка")
            logger.debug("✅ Найден маркер 'Бесконтактная доставка'")
        
        for pattern, description in comment_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                comment = match.group(1).strip()
                logger.debug(f"🔍 Найден комментарий паттерном '{description}': {comment[:100]}...")
                
                # Удаляем служебные фразы из комментария
                comment = self._clean_field_value(comment)
                
                if comment and len(comment) > 5:  # Минимальная длина комментария
                    comments.append(comment)
                    logger.debug(f"✅ Комментарий валиден (длина {len(comment)} символов)")
                    break
                else:
                    logger.debug(f"⚠️ Комментарий слишком короткий или пустой после очистки ({len(comment) if comment else 0} символов), пропускаем")
        
        if comments:
            result = "\n".join(comments)
            # Дополнительная очистка результата от служебных фраз
            result = self._clean_field_value(result)
            logger.debug(f"✅ Комментарий собран: {result[:100]}...")
            return result if result else None
        
        logger.debug("⚠️ Комментарий не найден")
        return None
    
    def _extract_delivery_time_window(self, text: str) -> Optional[str]:
        """Извлечение временного окна доставки"""
        logger.debug("🔍 Поиск временного окна доставки...")
        # Паттерны: "10:00 - 13:00", "10:00-13:00", "(10:00-13:00)"
        time_patterns = [
            (r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', 'HH:MM - HH:MM'),
            (r'\((\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\)', '(HH:MM - HH:MM)'),
            (r'(\d{1,2}:\d{2})\s*—\s*(\d{1,2}:\d{2})', 'HH:MM — HH:MM (длинное тире)'),
        ]
        
        for pattern, description in time_patterns:
            match = re.search(pattern, text)
            if match:
                start_time = match.group(1)
                end_time = match.group(2)
                time_window = f"{start_time}-{end_time}"
                logger.debug(f"✅ Временное окно найдено паттерном '{description}': {time_window}")
                return time_window
        
        logger.debug("⚠️ Временное окно доставки не найдено ни одним из паттернов")
        return None

