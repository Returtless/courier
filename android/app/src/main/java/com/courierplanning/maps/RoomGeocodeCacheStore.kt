package com.courierplanning.maps

import com.courierplanning.data.db.GeocodeCacheDao
import com.courierplanning.data.db.GeocodeCacheEntity

/**
 * [GeocodeCacheStore] поверх Room ([GeocodeCacheDao]).
 */
class RoomGeocodeCacheStore(
    private val dao: GeocodeCacheDao,
) : GeocodeCacheStore {
    override suspend fun get(addressKey: String): GeocodeResult? {
        val row = dao.getByAddress(addressKey) ?: return null
        return GeocodeResult(lat = row.latitude, lon = row.longitude, gisId = row.gisId)
    }

    override suspend fun put(addressKey: String, result: GeocodeResult) {
        dao.insert(
            GeocodeCacheEntity(
                address = addressKey,
                latitude = result.lat,
                longitude = result.lon,
                gisId = result.gisId,
                updatedAtMillis = System.currentTimeMillis(),
            ),
        )
    }
}
