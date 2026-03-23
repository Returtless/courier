package com.courierplanning.data.db

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Как [src.models.geocache.GeocodeCacheDB]: ключ — нормализованный адрес (lower + trim).
 */
@Entity(tableName = "geocode_cache")
data class GeocodeCacheEntity(
    @PrimaryKey
    @ColumnInfo(name = "address")
    val address: String,
    @ColumnInfo(name = "latitude")
    val latitude: Double,
    @ColumnInfo(name = "longitude")
    val longitude: Double,
    @ColumnInfo(name = "gis_id")
    val gisId: String?,
    /** UTC epoch millis, как в Python `updated_at`. */
    @ColumnInfo(name = "updated_at")
    val updatedAtMillis: Long,
)
