# 🔄 Этап 8: Рефакторинг Bot Handlers - В процессе

## ✅ Что сделано:

### 1. Обновлен CourierBot
- ✅ Все сервисы получаются через DI контейнер
- ✅ `maps_service` из контейнера
- ✅ `order_service`, `route_service`, `call_service` из контейнера
- ✅ Добавлен вспомогательный метод `get_today_orders_dict()` для обратной совместимости
- ✅ Обновлен `_main_menu_markup()` для использования `route_service` вместо `db_service`

### 2. Начата замена в OrderHandlers
- ✅ Заменены некоторые использования `db_service.get_today_orders` на `get_today_orders_dict`
- ⏳ Осталось заменить еще ~7 использований в order_handlers.py
- ⏳ Заменить использования `db_service.get_route_data` на `route_service.get_route`
- ⏳ Заменить использования `db_service.save_order` на `order_service.create_order/update_order`

## 📋 Что осталось сделать:

### OrderHandlers
- [ ] Заменить все `db_service.get_today_orders` → `get_today_orders_dict`
- [ ] Заменить `db_service.get_route_data` → `route_service.get_route`
- [ ] Заменить `db_service.save_order` → `order_service.create_order/update_order`
- [ ] Заменить прямые обращения к CallStatusDB → `call_service` или `call_status_repository`

### RouteHandlers
- [ ] Заменить все `db_service.get_today_orders` → `get_today_orders_dict`
- [ ] Заменить `db_service.get_route_data` → `route_service.get_route`
- [ ] Заменить `db_service.get_start_location` → `route_service.get_start_location`
- [ ] Заменить `db_service.save_start_location` → `route_service.save_start_location`
- [ ] Заменить `db_service.get_confirmed_calls` → через `call_service`

### ImportHandlers
- [ ] Заменить `db_service.get_today_orders` → `get_today_orders_dict`
- [ ] Заменить `db_service.save_order` → `order_service.create_order/update_order`

### Остальные handlers
- [ ] CallHandlers - проверить использования
- [ ] SettingsHandlers - проверить использования
- [ ] TrafficHandlers - проверить использования

## 📝 Примечания:

- `db_service` оставлен для обратной совместимости, но помечен как устаревший
- Вспомогательный метод `get_today_orders_dict()` преобразует DTO в словари для обратной совместимости
- После полного рефакторинга `db_service` будет удален

