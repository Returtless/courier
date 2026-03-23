package com.courierplanning.data.db

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

/**
 * Миграции Room. Версия 1 — схема без `geocode_cache` и без колонки `orders.gis_id`
 * (как при первом выпуске приложения до этого изменения).
 *
 * Версия 2 добавляет таблицу кэша геокодирования и колонку `gis_id` у заказов.
 */
object CourierDatabaseMigrations {

    val MIGRATION_1_2 = object : Migration(1, 2) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    address TEXT NOT NULL PRIMARY KEY,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    gis_id TEXT,
                    updated_at INTEGER NOT NULL
                )
                """.trimIndent(),
            )
            if (!ordersColumnExists(db, "gis_id")) {
                db.execSQL("ALTER TABLE orders ADD COLUMN gis_id TEXT")
            }
        }
    }

    private fun ordersColumnExists(db: SupportSQLiteDatabase, columnName: String): Boolean {
        val cursor = db.query("PRAGMA table_info(orders)")
        return try {
            val nameIdx = cursor.getColumnIndex("name")
            if (nameIdx < 0) return@try false
            while (cursor.moveToNext()) {
                if (columnName == cursor.getString(nameIdx)) return@try true
            }
            false
        } finally {
            cursor.close()
        }
    }
}
