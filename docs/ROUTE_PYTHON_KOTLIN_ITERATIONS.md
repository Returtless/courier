# Итерации выравнивания Kotlin ↔ Python (ветка без OR-Tools)

## Итерация 1 — алгоритм GA и константы

| Было (расхождение) | Стало |
|--------------------|--------|
| Kotlin: полный перебор при N≤8 | Только **GA** при N≥2, как `GeneticRouteOptimizer._genetic_algorithm` |
| Kotlin: `kotlin.random.Random` | **`SplitMix64Rng`**, тот же алгоритм, что в `src/services/genetic_rng.py` |
| Турнир: возможны повторы индексов | **`sampleDistinctIndices`** как `random.sample` |
| OX-кроссовер: другой вариант | **Точная копия** `_order_crossover` (сегмент `randint(0,n-2)` × `randint(start+1,n-1)`, обход с пропуском `start`) |
| Swap-мутация: `i` и `j` могли совпасть | Два **различных** индекса, как `random.sample` |
| Один заказ: `buildRouteFromChromosome` + post-process + manual | **`buildSingleOrderRouteNoManual`** как `_build_single_order_route` (без manual, без постобработки) |
| Haversine-матрица без сети: 40 км/ч | **30 км/ч** как оценка `GREEDY_EST_KM_PER_MIN = 0.5` (~30 км/ч) |

## Итерация 2 — golden / Python export

| Было | Стало |
|------|--------|
| `export_optimizer_golden.py`: `random.seed` + MT | **`patch_random_module(SplitMix64Rng(seed))`** + `random.seed` = no-op, чтобы совпадать с JVM |
| Документация: «exhaustive» | README parity + комментарии тестов обновлены под GA + SplitMix |

## Оставшиеся расхождения (не закрыты кодом в этой сессии)

1. **Рантайм Telegram-бот (Python)** по-прежнему использует модуль `random` (MT), не SplitMix — побитово с Kotlin не совпадёт; для прод-сравнения либо патчить бота, либо сравнивать только по метрикам.
2. **Матрица**: Python может считать ноги через `get_route_sync` по одной; Kotlin — из предрасчитанной матрицы (эквивалентно при одинаковых числах в JSON).
3. **`user_id` / UserSettingsService** в генетике Python — на Android время обслуживания только из JSON.
4. **OR-Tools** на Python — на Kotlin отсутствует (по условию задачи).

После изменений **обязательно** перегенерировать `expected.json`:

`PYTHONPATH=. python tools/export_optimizer_golden.py --fixture parity_fixtures/tiny_two_orders`  
`PYTHONPATH=. python tools/export_optimizer_golden.py --fixture parity_fixtures/telegram_spb_route_head5`
