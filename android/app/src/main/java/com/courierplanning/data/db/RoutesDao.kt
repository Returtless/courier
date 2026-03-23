package com.courierplanning.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface RoutesDao {
    @Query("SELECT * FROM routes WHERE route_date = :routeDate LIMIT 1")
    suspend fun getByDate(routeDate: String): RouteEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(route: RouteEntity): Long

    @Query("DELETE FROM routes WHERE route_date = :routeDate")
    suspend fun deleteByDate(routeDate: String)
}
