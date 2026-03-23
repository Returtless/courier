package com.courierplanning.data.db

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "orders",
    indices = [
        Index(value = ["order_date", "order_number"], unique = true),
    ],
)
data class OrderEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "order_date")
    val orderDate: String,
    @ColumnInfo(name = "order_number")
    val orderNumber: String,
    val address: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @ColumnInfo(name = "delivery_time_start")
    val deliveryTimeStart: String? = null,
    @ColumnInfo(name = "delivery_time_end")
    val deliveryTimeEnd: String? = null,
    @ColumnInfo(name = "manual_arrival_time")
    val manualArrivalTime: String? = null,
    val phone: String? = null,
    @ColumnInfo(name = "customer_name")
    val customerName: String? = null,
    /** ID объекта 2GIS после геокода; добавлено в миграции 1→2. */
    @ColumnInfo(name = "gis_id")
    val gisId: String? = null,
)
