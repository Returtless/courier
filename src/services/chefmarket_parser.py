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
    
    async def import_orders(self, login: str, password: str, target_date: date = None) -> List[Dict]:
        """
        Импорт всех заказов с детальной информацией
        
        Args:
            login: Логин от сайта
            password: Пароль от сайта
            target_date: Дата заказов (по умолчанию сегодня)
        
        Returns:
            Список словарей с данными заказов
        """
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
                        await page.screenshot(path="auth_error.png")
                        logger.error("Скриншот сохранен в auth_error.png")
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
                
                # 6. Получаем все ссылки на заказы
                order_links = await page.query_selector_all('.link')
                logger.info(f"📊 Найдено заказов на странице: {len(order_links)}")
                
                # Если заказов нет, делаем скриншот для проверки
                if len(order_links) == 0:
                    logger.warning("⚠️ Список заказов пуст!")
                    screenshot_path = "empty_orders_list.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    logger.info(f"📸 Скриншот пустого списка сохранен в {screenshot_path}")
                    logger.info("Возможные причины:")
                    logger.info("  - На сегодня действительно нет заказов")
                    logger.info("  - Заказы на другую дату (проверьте дату в заголовке)")
                    logger.info("  - Изменилась структура сайта (селектор .link)")
                    return []  # Возвращаем пустой список
                
                # 7. Проходим по каждому заказу
                for i, link_element in enumerate(order_links, 1):
                    try:
                        logger.info(f"📋 Обработка заказа {i}/{len(order_links)}...")
                        
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
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки заказа {i}: {e}")
                        # Пытаемся вернуться к списку
                        try:
                            await page.goto(f"{self.base_url}/orders", timeout=5000)
                        except:
                            pass
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

