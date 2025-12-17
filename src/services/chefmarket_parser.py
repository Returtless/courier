"""
Парсер заказов с сайта ШефМаркет (deliver.chefmarket.ru)
Использует Playwright для автоматизации браузера
"""
import logging
import re
import os
from typing import List, Dict
from datetime import datetime, date

logger = logging.getLogger(__name__)


class ChefMarketParser:
    """Парсер заказов с сайта ШефМаркет"""
    
    def __init__(self):
        self.base_url = "https://deliver.chefmarket.ru"
        self.last_screenshot_path = None  # Путь к последнему скриншоту (если был сделан)
    
    async def import_orders(self, login: str, password: str, target_date: date = None) -> List[Dict]:
        """
        Импорт всех заказов с детальной информацией
        
        Args:
            login: Логин от сайта
            password: Пароль от сайта
            target_date: Дата заказов (по умолчанию сегодня)
        
        Returns:
            Список словарей с данными заказов
        
        Note:
            Если заказов нет, скриншот сохраняется в self.last_screenshot_path
        """
        self.last_screenshot_path = None  # Сбрасываем путь к скриншоту перед новым импортом
        if target_date is None:
            target_date = date.today()
        
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright не установлен! Запустите: pip install playwright && playwright install chromium")
            raise
        
        orders = []
        
        try:
            async with async_playwright() as p:
                # Запускаем браузер
                # Режим отладки: установите PARSER_DEBUG=1 в env для просмотра браузера
                debug_mode = os.getenv("PARSER_DEBUG", "0") == "1"
                
                browser = await p.chromium.launch(
                    headless=not debug_mode,  # headless=False если PARSER_DEBUG=1
                    args=['--no-sandbox', '--disable-setuid-sandbox'],  # Для Docker
                    slow_mo=1000 if debug_mode else 0  # Замедление для отладки
                )
                
                if debug_mode:
                    logger.info("🐛 РЕЖИМ ОТЛАДКИ: браузер будет видимым")
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = await context.new_page()
                
                logger.info("🔐 Авторизация на сайте ШефМаркет...")
                
                # 1. Переходим на страницу входа
                await page.goto(f"{self.base_url}/login", wait_until='networkidle', timeout=30000)
                
                # 2. Вводим учетные данные (точные селекторы со страницы авторизации)
                await page.fill('input#input-user', login)
                await page.fill('input#input-password', password)
                
                # 3. Нажимаем кнопку "Войти"
                await page.click('button.login_button')
                
                # 4. Ждем перехода на страницу заказов
                try:
                    await page.wait_for_url("**/orders", timeout=10000)
                    logger.info("✅ Авторизация успешна! Перешли на /orders")
                except:
                    # Если не перешло на /orders, проверяем что произошло
                    current_url = page.url
                    logger.warning(f"Не перешли на /orders автоматически. Текущий URL: {current_url}")
                    
                    if "/orders" not in current_url:
                        logger.error("❌ Авторизация не удалась - не попали на страницу заказов")
                        # Сохраняем скриншот в директорию data (которая монтируется как volume)
                        os.makedirs("data", exist_ok=True)
                        screenshot_path = os.path.join("data", "auth_error.png")
                        await page.screenshot(path=screenshot_path)
                        logger.error(f"Скриншот сохранен в {screenshot_path}")
                        logger.error(f"📁 Полный путь: {os.path.abspath(screenshot_path)}")
                        raise Exception("Ошибка авторизации. Проверьте логин и пароль.")
                
                # 5. Дополнительная проверка авторизации
                # Проверяем наличие элементов авторизованного пользователя
                logger.info("🔍 Проверка элементов страницы...")
                
                # Ждем загрузки основного контента
                try:
                    await page.wait_for_selector('.app-footer, .footer', timeout=5000)
                    logger.info("✅ Найден footer (элемент авторизованного пользователя)")
                except:
                    logger.warning("⚠️ Footer не найден - возможно, структура сайта изменилась")
                
                # Проверяем наличие заголовка "Заказы на [дата]"
                date_header = await page.locator('div:has-text("Заказы на")').count()
                if date_header > 0:
                    header_text = await page.locator('div:has-text("Заказы на")').first.inner_text()
                    logger.info(f"✅ Найден заголовок: {header_text}")
                else:
                    logger.warning("⚠️ Заголовок с датой не найден")
                
                logger.info(f"📦 Получение списка заказов...")
                
                # Ждем загрузки контейнера с заказами и появления хотя бы одного заказа
                try:
                    # Ждем появления контейнера
                    await page.wait_for_selector('.index-orders', timeout=10000)
                    logger.info("✅ Контейнер .index-orders найден")
                    
                    # Дополнительно ждем появления хотя бы одного заказа (это важно для SPA)
                    await page.wait_for_selector('.index-orders .link, .index-orders .order-cell', timeout=10000)
                    logger.info("✅ Заказы загружены на странице")
                except Exception as e:
                    logger.warning(f"⚠️ Ожидание загрузки заказов: {e}")
                    # Пробуем продолжить, возможно заказы уже загружены
                
                # 6. Получаем все ссылки на заказы ВНУТРИ контейнера .index-orders
                # Ищем более специфично: заказы внутри .index-orders, а не все .link на странице
                order_links = await page.query_selector_all('.index-orders .link')
                logger.info(f"📊 Найдено заказов по селектору '.index-orders .link': {len(order_links)}")
                
                # Если заказов нет, пробуем альтернативные селекторы
                if len(order_links) == 0:
                    logger.warning("⚠️ Заказы не найдены по селектору '.index-orders .link', пробуем альтернативные варианты...")
                    
                    # Альтернативный вариант 1: используем JavaScript для поиска всех .link внутри .index-orders
                    try:
                        # Используем evaluate для получения всех .link элементов
                        link_count = await page.evaluate('''() => {
                            const indexOrders = document.querySelector('.index-orders');
                            if (!indexOrders) return 0;
                            return indexOrders.querySelectorAll('.link').length;
                        }''')
                        logger.info(f"📊 JavaScript поиск: найдено {link_count} .link в .index-orders")
                        
                        if link_count > 0:
                            # Теперь получаем элементы через Playwright
                            order_links = await page.query_selector_all('.index-orders .link')
                            logger.info(f"📊 После JavaScript проверки: найдено {len(order_links)} .link")
                    except Exception as e:
                        logger.debug(f"Ошибка JavaScript поиска: {e}")
                    
                    # Альтернативный вариант 2: ищем все .link на странице и фильтруем те, что внутри .index-orders
                    if len(order_links) == 0:
                        all_links = await page.query_selector_all('.link')
                        logger.info(f"📊 Всего .link на странице: {len(all_links)}")
                        
                        # Фильтруем только те, что внутри .index-orders через JavaScript
                        found_links = []
                        for link in all_links:
                            is_in_index_orders = await link.evaluate('(el) => el.closest(".index-orders") !== null')
                            if is_in_index_orders:
                                found_links.append(link)
                        order_links = found_links
                        logger.info(f"📊 Отфильтровано .link внутри .index-orders: {len(order_links)}")
                    
                    # Диагностика: проверяем, есть ли элементы с номерами заказов
                    if len(order_links) == 0:
                        order_numbers_found = await page.locator('.index-orders:has-text("№")').count()
                        logger.info(f"📊 Элементов с '№' в .index-orders: {order_numbers_found}")
                        
                        # Пробуем найти заказы через order-header__id
                        order_ids = await page.query_selector_all('.index-orders .order-header__id')
                        logger.info(f"📊 Найдено .order-header__id: {len(order_ids)}")
                        
                        if len(order_ids) > 0:
                            # Если нашли order-header__id, значит заказы есть, но .link не найдены
                            # Пробуем найти родительские .link через JavaScript
                            link_selectors = await page.evaluate('''() => {
                                const ids = document.querySelectorAll('.index-orders .order-header__id');
                                const links = [];
                                ids.forEach(id => {
                                    const link = id.closest('.link');
                                    if (link && !links.includes(link)) {
                                        links.push(link);
                                    }
                                });
                                return links.length;
                            }''')
                            logger.info(f"📊 JavaScript поиск .link через .order-header__id: найдено {link_selectors}")
                            
                            # Если JavaScript нашел ссылки, пробуем получить их через Playwright еще раз
                            if link_selectors > 0:
                                order_links = await page.query_selector_all('.index-orders .link')
                                logger.info(f"📊 После диагностики: найдено {len(order_links)} .link")
                
                # Если заказов все еще нет, делаем скриншот для проверки
                if len(order_links) == 0:
                    logger.warning("⚠️ Список заказов пуст!")
                    # Сохраняем скриншот в директорию data (которая монтируется как volume)
                    os.makedirs("data", exist_ok=True)
                    screenshot_path = os.path.join("data", "empty_orders_list.png")
                    await page.screenshot(path=screenshot_path, full_page=True)
                    self.last_screenshot_path = screenshot_path  # Сохраняем путь для отправки пользователю
                    logger.info(f"📸 Скриншот пустого списка сохранен в {screenshot_path}")
                    logger.info(f"📁 Полный путь: {os.path.abspath(screenshot_path)}")
                    
                    # Дополнительная диагностика: проверяем структуру страницы
                    try:
                        index_orders_exists = await page.query_selector('.index-orders') is not None
                        logger.info(f"🔍 Диагностика: .index-orders существует: {index_orders_exists}")
                        
                        if index_orders_exists:
                            index_orders_text = await page.locator('.index-orders').first.inner_text()
                            logger.info(f"🔍 Содержимое .index-orders (первые 500 символов): {index_orders_text[:500]}")
                    except Exception as e:
                        logger.debug(f"Ошибка диагностики: {e}")
                    
                    logger.info("Возможные причины:")
                    logger.info("  - На сегодня действительно нет заказов")
                    logger.info("  - Заказы на другую дату (проверьте дату в заголовке)")
                    logger.info("  - Изменилась структура сайта (селектор .link или .index-orders)")
                    return []  # Возвращаем пустой список
                
                # 7. Проходим по каждому заказу
                # ВАЖНО: не сохраняем ссылки на элементы, так как они становятся неактуальными после навигации
                # Вместо этого находим элементы заново перед каждым кликом
                total_orders = len(order_links)
                
                for i in range(1, total_orders + 1):
                    try:
                        logger.info(f"📋 Обработка заказа {i}/{total_orders}...")
                        
                        # Убеждаемся, что мы на странице списка заказов
                        if "/orders" not in page.url:
                            logger.info(f"🔄 Возвращаемся на страницу списка заказов...")
                            await page.goto(f"{self.base_url}/orders", wait_until='networkidle', timeout=10000)
                            await page.wait_for_selector('.index-orders .link, .index-orders .order-cell', timeout=10000)
                        
                        # Находим все заказы заново (элементы могли стать неактуальными)
                        current_order_links = await page.query_selector_all('.index-orders .link')
                        
                        if len(current_order_links) < i:
                            logger.warning(f"⚠️ Заказ {i} не найден (всего заказов: {len(current_order_links)})")
                            continue
                        
                        # Берем i-й заказ (индекс i-1, так как начинаем с 1)
                        link_element = current_order_links[i - 1]
                        
                        # СНАЧАЛА извлекаем время доставки ИЗ СПИСКА (до клика)
                        time_window = None
                        try:
                            # Ищем временное окно в карточке заказа
                            time_elem = await link_element.query_selector('.order-header__range-time')
                            if time_elem:
                                time_text = await time_elem.inner_text()
                                # Извлекаем время из "(10:00-13:00)"
                                match = re.search(r'\((\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\)', time_text)
                                if match:
                                    time_window = f"{match.group(1)}-{match.group(2)}"
                        except Exception as e:
                            logger.debug(f"Не удалось извлечь время из списка: {e}")
                        
                        # Кликаем на заказ
                        await link_element.click()
                        await page.wait_for_load_state('networkidle', timeout=10000)
                        
                        # Извлекаем детальные данные
                        order_data = await self._extract_order_details(page)
                        
                        if order_data:
                            # Добавляем время доставки из списка
                            if time_window and not order_data.get('delivery_time_window'):
                                order_data['delivery_time_window'] = time_window
                            
                            orders.append(order_data)
                            logger.info(f"✅ Заказ №{order_data.get('order_number')} обработан")
                        
                        # Возвращаемся назад к списку
                        await page.go_back()
                        await page.wait_for_load_state('networkidle', timeout=5000)
                        
                        # Дополнительное ожидание для стабилизации страницы
                        await page.wait_for_selector('.index-orders .link, .index-orders .order-cell', timeout=5000)
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки заказа {i}: {e}")
                        # Пытаемся вернуться к списку
                        try:
                            await page.goto(f"{self.base_url}/orders", wait_until='networkidle', timeout=10000)
                            await page.wait_for_selector('.index-orders .link, .index-orders .order-cell', timeout=10000)
                        except Exception as nav_error:
                            logger.error(f"❌ Ошибка возврата к списку: {nav_error}")
                        continue
                
                await browser.close()
                logger.info(f"✅ Импорт завершен! Обработано заказов: {len(orders)}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка импорта: {e}", exc_info=True)
            raise
        
        return orders
    
    async def _extract_order_details(self, page) -> Dict | None:
        """
        Извлечение данных со страницы заказа ШефМаркет
        
        Структура страницы:
        - Номер: .order-nav__order-id
        - Адрес: .address-body__text
        - Имя: .customer-body__info-name
        - Телефон: .customer-body__info-tel a[href^="tel:"]
        - Бесконтактная: .order-address__contactless
        - Комментарий: .comment
        """
        try:
            # Ждем загрузки основного контента
            await page.wait_for_selector('.order-nav, .order-page', timeout=5000)
            
            # 1. Номер заказа - из заголовка навигации
            order_number = await self._safe_extract(page, '.order-nav__order-id')
            if order_number:
                # Извлекаем цифры из "Заказ № 3269184"
                match = re.search(r'№?\s*(\d+)', order_number)
                order_number = match.group(1) if match else None
            
            # 2. Адрес - полный адрес с подъездом и квартирой
            address = await self._safe_extract(page, '.address-body__text')
            
            # 3. Имя клиента - извлекаем только имя без "Имя: "
            customer_name_raw = await self._safe_extract(page, '.customer-body__info-name')
            customer_name = None
            if customer_name_raw:
                # Убираем "Имя: " из начала
                customer_name = re.sub(r'^Имя:\s*', '', customer_name_raw, flags=re.IGNORECASE).strip()
            
            # 4. Телефон - из ссылки tel:
            phone = None
            try:
                phone_element = await page.query_selector('.customer-body__info-tel a[href^="tel:"]')
                if phone_element:
                    phone = await phone_element.inner_text()
                    phone = phone.strip()
            except:
                # Fallback - ищем в тексте
                phone_text = await self._safe_extract(page, '.customer-body__info-tel')
                if phone_text:
                    phone_match = re.search(r'\+?\d[\d\s\-\(\)]{9,}', phone_text)
                    if phone_match:
                        phone = phone_match.group(0).strip()
            
            # 5. Временное окно - попробуем найти в navigation или на странице списка
            # На странице заказа может не быть времени, нужно брать из предыдущей страницы
            time_window = None
            # Пока оставим None, время будет браться из списка на главной странице
            
            # 6. Бесконтактная доставка
            contactless = await self._safe_extract(page, '.order-address__contactless')
            is_contactless = contactless and "бесконтактная" in contactless.lower()
            
            # 7. Комментарий к заказу
            order_comment = await self._safe_extract(page, '.comment')
            
            # Формируем итоговый комментарий
            comments = []
            if is_contactless:
                comments.append("Бесконтактная доставка")
            if order_comment:
                comments.append(order_comment)
            
            final_comment = "\n".join(comments) if comments else None
            
            # 8. Извлекаем подъезд и квартиру из адреса
            entrance_number = None
            apartment_number = None
            
            if address:
                # Подъезд
                entrance_match = re.search(r'подъезд\s+(\d+)', address, re.IGNORECASE)
                if entrance_match:
                    entrance_number = entrance_match.group(1)
                
                # Квартира
                apartment_match = re.search(r'кв\.?\s*(\d+)', address, re.IGNORECASE)
                if apartment_match:
                    apartment_number = apartment_match.group(1)
            
            # Формируем результат
            order_data = {
                'order_number': order_number,
                'customer_name': customer_name,
                'phone': phone,
                'address': address,
                'entrance_number': entrance_number,
                'apartment_number': apartment_number,
                'delivery_time_window': time_window,  # Будет None, заполнится из списка
                'comment': final_comment
            }
            
            logger.debug(f"Извлечены данные заказа: {order_data}")
            
            # Проверяем обязательные поля
            if not order_number:
                logger.warning(f"Номер заказа не найден на странице")
                return None
            
            if not address:
                logger.warning(f"Адрес не найден для заказа {order_number}")
                return None
            
            return order_data
            
        except Exception as e:
            logger.error(f"Ошибка извлечения данных заказа: {e}", exc_info=True)
            return None
    
    async def _safe_extract(self, page, selector: str) -> str | None:
        """Безопасное извлечение текста по селектору"""
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                return text.strip() if text else None
        except Exception as e:
            logger.debug(f"Элемент не найден по селектору '{selector}': {e}")
        return None

