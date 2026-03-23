package com.courierplanning.data.db

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "routes",
    indices = [Index(value = ["route_date"], unique = true)],
)
data class RouteEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "route_date")
    val routeDate: String,
    @ColumnInfo(name = "start_lat")
    val startLat: Double,
    @ColumnInfo(name = "start_lon")
    val startLon: Double,
    @ColumnInfo(name = "start_time_iso")
    val startTimeIso: String,
    @ColumnInfo(name = "total_distance_km")
    val totalDistanceKm: Double,
    @ColumnInfo(name = "total_time_min")
    val totalTimeMin: Double,
    @ColumnInfo(name = "estimated_completion_iso")
    val estimatedCompletionIso: String,
)
