package com.courierplanning.data.db

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "settings")
data class SettingsEntity(
    @PrimaryKey
    val id: Int = 1,
    @ColumnInfo(name = "call_advance_minutes")
    val callAdvanceMinutes: Int = 30,
    @ColumnInfo(name = "service_time_minutes")
    val serviceTimeMinutes: Int = 10,
)
