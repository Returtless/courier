package com.courierplanning.data.db

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "call_statuses",
    indices = [
        Index(value = ["order_number", "call_date"], unique = true),
    ],
)
data class CallStatusEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "order_number")
    val orderNumber: String,
    @ColumnInfo(name = "call_date")
    val callDate: String,
    @ColumnInfo(name = "call_time_iso")
    val callTimeIso: String,
    @ColumnInfo(name = "arrival_time_iso")
    val arrivalTimeIso: String? = null,
    val phone: String = "",
    @ColumnInfo(name = "customer_name")
    val customerName: String? = null,
    val status: String = "pending",
    @ColumnInfo(name = "next_attempt_iso")
    val nextAttemptIso: String? = null,
)
