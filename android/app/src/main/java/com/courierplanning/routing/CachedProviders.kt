package com.courierplanning.routing

import com.courierplanning.data.db.GeocodeCacheDao
import com.courierplanning.data.db.GeocodeCacheEntity
import com.courierplanning.data.db.RouteMetricsCacheDao
import com.courierplanning.data.db.RouteMetricsCacheEntity

class CachedRoutingProvider(
    private val delegate: RoutingProvider,
    private val cacheDao: RouteMetricsCacheDao,
) : RoutingProvider {
    override val name: String get() = delegate.name

    override suspend fun getMetrics(from: LatLon, to: LatLon): RouteMetrics {
        val fromKey = from.key()
        val toKey = to.key()
        val cached = cacheDao.get(delegate.name, fromKey, toKey)
        if (cached != null) {
            return RouteMetrics(distanceKm = cached.distanceKm, travelMin = cached.travelMin)
        }
        val v = delegate.getMetrics(from, to)
        cacheDao.upsert(
            RouteMetricsCacheEntity(
                provider = delegate.name,
                fromKey = fromKey,
                toKey = toKey,
                distanceKm = v.distanceKm,
                travelMin = v.travelMin,
            )
        )
        return v
    }
}

class CachedGeocodingProvider(
    private val delegate: GeocodingProvider,
    private val cacheDao: GeocodeCacheDao,
) : GeocodingProvider {
    override val name: String get() = delegate.name

    override suspend fun geocode(address: String): GeocodeResult? {
        val cached = cacheDao.get(delegate.name, address)
        if (cached != null) {
            return GeocodeResult(lat = cached.lat, lon = cached.lon, gisId = cached.gisId)
        }
        val v = delegate.geocode(address)
        cacheDao.upsert(
            GeocodeCacheEntity(
                provider = delegate.name,
                address = address,
                lat = v?.lat,
                lon = v?.lon,
                gisId = v?.gisId,
            )
        )
        return v
    }
}

