package com.courierplanning.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface OrdersDao {
    @Query("SELECT * FROM orders WHERE order_date = :routeDate ORDER BY id ASC")
    suspend fun listByDate(routeDate: String): List<OrderEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(order: OrderEntity): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(orders: List<OrderEntity>)

    @Query(
        """
        UPDATE orders SET latitude = :lat, longitude = :lon, gis_id = :gisId
        WHERE order_number = :orderNumber AND order_date = :orderDate
        """,
    )
    suspend fun updateGeocode(
        orderNumber: String,
        orderDate: String,
        lat: Double,
        lon: Double,
        gisId: String?,
    )
}
