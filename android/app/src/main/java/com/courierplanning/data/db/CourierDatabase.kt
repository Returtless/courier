package com.courierplanning.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [
        OrderEntity::class,
        RouteEntity::class,
        RoutePointEntity::class,
        SettingsEntity::class,
        CallStatusEntity::class,
        GeocodeCacheEntity::class,
    ],
    version = 2,
    exportSchema = false,
)
abstract class CourierDatabase : RoomDatabase() {
    abstract fun ordersDao(): OrdersDao
    abstract fun routesDao(): RoutesDao
    abstract fun routePointsDao(): RoutePointsDao
    abstract fun settingsDao(): SettingsDao
    abstract fun callStatusesDao(): CallStatusesDao
    abstract fun geocodeCacheDao(): GeocodeCacheDao

    companion object {
        private val callback = object : Callback() {
            override fun onCreate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    INSERT OR IGNORE INTO settings (id, call_advance_minutes, service_time_minutes)
                    VALUES (1, 30, 10)
                    """.trimIndent(),
                )
            }

            override fun onOpen(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    INSERT OR IGNORE INTO settings (id, call_advance_minutes, service_time_minutes)
                    VALUES (1, 30, 10)
                    """.trimIndent(),
                )
            }
        }

        fun build(context: Context): CourierDatabase =
            Room.databaseBuilder(
                context.applicationContext,
                CourierDatabase::class.java,
                "courier.db",
            )
                .addMigrations(CourierDatabaseMigrations.MIGRATION_1_2)
                .addCallback(callback)
                .build()
    }
}
