package com.courierplanning.routeopt.parity

import com.courierplanning.routeopt.cluster.ClusterSynchronizer
import com.courierplanning.routeopt.math.DeliveryTimeWindowParser
import java.time.ZonedDateTime

/**
 * Parity pipeline aligned with Python [src.services.route_optimizer_genetic.GeneticRouteOptimizer.optimize_route_sync]:
 * заказы с координатами → кластеризация + синхронизация окон → оптимизация
 * ([MatrixParityOptimizer]: один заказ — как [_build_single_order_route], иначе GA как в Python).
 */
object ParityRouteFacade {

    fun optimize(input: ParityOptimizeInputJson): ParityOptimizeOutputJson {
        val startZdt = ZonedDateTime.parse(input.startTimeIso)
        val zone = startZdt.zone
        val orderDate = startZdt.toLocalDate()

        // Match Python: truthy lat/lon (exclude 0.0 used as "missing" in some payloads).
        val withCoords = input.orders.filter { it.lat != 0.0 && it.lon != 0.0 }
        if (withCoords.isEmpty()) {
            return MatrixParityOptimizer.optimizeFromOrders(input, emptyList())
        }

        val clusterOrders = withCoords.map { o ->
            ClusterSynchronizer.ClusterOrder(
                orderNumber = o.orderNumber,
                lat = o.lat,
                lon = o.lon,
                windowStart = o.windowStart?.let { DeliveryTimeWindowParser.parseExplicitHhMm(it) },
                windowEnd = o.windowEnd?.let { DeliveryTimeWindowParser.parseExplicitHhMm(it) },
            )
        }

        val clustered = ClusterSynchronizer.clusterAndSynchronize(
            clusterOrders,
            orderDate,
            zone,
            input.startLocation.lat,
            input.startLocation.lon,
        )

        val manualByNumber = input.orders.associate { o ->
            o.orderNumber to o.manualArrivalIso?.let { iso ->
                ZonedDateTime.parse(iso).withZoneSameInstant(zone)
            }
        }

        val internal = clustered.map { c ->
            MatrixParityOptimizer.InternalOrder(
                orderNumber = c.orderNumber,
                lat = c.lat,
                lon = c.lon,
                windowStart = c.windowStart,
                windowEnd = c.windowEnd,
                manualArrival = manualByNumber[c.orderNumber],
            )
        }

        return MatrixParityOptimizer.optimizeFromOrders(input, internal)
    }
}
