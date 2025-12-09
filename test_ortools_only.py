#!/usr/bin/env python3
"""
Тест только OR-Tools оптимизации без зависимостей от карт
"""

import numpy as np
from datetime import datetime, timedelta


def test_ortools_basic():
    """Тест базовой функциональности OR-Tools"""
    print("🧮 Тестирование OR-Tools...")

    try:
        from ortools.constraint_solver import routing_enums_pb2
        from ortools.constraint_solver import pywrapcp
        print("✅ OR-Tools импортирован успешно")
    except ImportError as e:
        print(f"❌ OR-Tools не установлен: {e}")
        print("Установите: pip install ortools")
        return False

    # Создание простой задачи оптимизации
    print("\n📊 Создание тестовой задачи...")

    # Матрица расстояний (5 точек)
    distance_matrix = np.array([
        [0, 10, 15, 20, 25],  # От точки 0
        [10, 0, 12, 18, 22],  # От точки 1
        [15, 12, 0, 8, 15],   # От точки 2
        [20, 18, 8, 0, 10],   # От точки 3
        [25, 22, 15, 10, 0],  # От точки 4
    ])

    # Матрица времени (в минутах)
    time_matrix = np.array([
        [0, 12, 18, 24, 30],
        [12, 0, 15, 22, 27],
        [18, 15, 0, 10, 18],
        [24, 22, 10, 0, 12],
        [30, 27, 18, 12, 0],
    ])

    print(f"📍 Точек: {len(distance_matrix)}")
    print("Матрица расстояний:")
    print(distance_matrix)
    print("\nМатрица времени:")
    print(time_matrix)

    # Решение задачи
    print("\n⏳ Решение оптимизации...")

    try:
        manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(distance_matrix[from_node][to_node] * 1000)  # в метрах

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Настройки поиска
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
        search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.AUTOMATIC
        search_parameters.time_limit.seconds = 10

        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            print("✅ OR-Tools нашел решение!")

            # Вывод маршрута
            route = []
            index = routing.Start(0)
            route_distance = 0
            route_time = 0

            print("\n🚚 ОПТИМАЛЬНЫЙ МАРШРУТ:")
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                route.append(node)
                print(f"   Точка {node}")

                if len(route) > 1:
                    prev_node = route[-2]
                    route_distance += distance_matrix[prev_node][node]
                    route_time += time_matrix[prev_node][node]

                index = solution.Value(routing.NextVar(index))

            route.append(manager.IndexToNode(index))  # Возврат к началу

            print("\n📊 РЕЗУЛЬТАТЫ:")
            print(f"   📏 Расстояние: {route_distance} км")
            print(f"   ⏱️ Время: {route_time} мин")
            print(f"   📍 Маршрут: {' -> '.join(map(str, route))}")

            return True
        else:
            print("❌ OR-Tools не нашел решение")
            return False

    except Exception as e:
        print(f"❌ Ошибка OR-Tools: {e}")
        return False


def test_route_optimizer_import():
    """Тест импорта RouteOptimizer"""
    print("\n🔍 Тестирование импорта RouteOptimizer...")

    try:
        from src.services.route_optimizer import RouteOptimizer
        print("✅ RouteOptimizer импортирован")

        # Создание экземпляра
        optimizer = RouteOptimizer(None)  # Без карт
        print("✅ RouteOptimizer инициализирован")

        return True
    except Exception as e:
        print(f"❌ Ошибка импорта RouteOptimizer: {e}")
        return False


def main():
    print("🧮 ТЕСТИРОВАНИЕ OR-TOOLS ОПТИМИЗАЦИИ")
    print("=" * 50)

    # Тест OR-Tools
    ortools_ok = test_ortools_basic()

    # Тест импорта
    import_ok = test_route_optimizer_import()

    print("\n" + "=" * 50)
    if ortools_ok and import_ok:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("OR-Tools готов к работе в системе оптимизации маршрутов")
    else:
        print("⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        if not ortools_ok:
            print("   - OR-Tools не работает")
        if not import_ok:
            print("   - RouteOptimizer не импортируется")


if __name__ == "__main__":
    main()
