package com.courierplanning.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface GeocodeCacheDao {
    @Query("SELECT * FROM geocode_cache WHERE address = :addressKey LIMIT 1")
    suspend fun getByAddress(addressKey: String): GeocodeCacheEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: GeocodeCacheEntity)
}
