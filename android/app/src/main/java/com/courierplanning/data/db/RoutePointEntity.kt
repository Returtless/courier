package com.courierplanning.data.db

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "route_points",
    foreignKeys = [
        ForeignKey(
            entity = RouteEntity::class,
            parentColumns = ["id"],
            childColumns = ["route_id"],
            onDelete = ForeignKey.CASCADE,
        ),
    ],
    indices = [Index("route_id")],
)
data class RoutePointEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "route_id")
    val routeId: Long,
    val position: Int,
    @ColumnInfo(name = "order_number")
    val orderNumber: String,
    @ColumnInfo(name = "estimated_arrival_iso")
    val estimatedArrivalIso: String,
    @ColumnInfo(name = "call_time_iso")
    val callTimeIso: String? = null,
    @ColumnInfo(name = "distance_from_previous_km")
    val distanceFromPreviousKm: Double,
    @ColumnInfo(name = "time_from_previous_min")
    val timeFromPreviousMin: Double,
    @ColumnInfo(name = "window_start")
    val windowStart: String? = null,
    @ColumnInfo(name = "window_end")
    val windowEnd: String? = null,
    @ColumnInfo(name = "is_late")
    val isLate: Boolean = false,
)
