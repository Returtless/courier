package com.courierplanning.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface RoutePointsDao {
    @Query("SELECT * FROM route_points WHERE route_id = :routeId ORDER BY position ASC")
    suspend fun list(routeId: Long): List<RoutePointEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(points: List<RoutePointEntity>)

    @Query("DELETE FROM route_points WHERE route_id = :routeId")
    suspend fun deleteByRouteId(routeId: Long)
}
