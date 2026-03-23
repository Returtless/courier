package com.courierplanning

import android.content.Context
import com.courierplanning.data.CallStatusRepository
import com.courierplanning.data.db.CourierDatabase

/**
 * Точка входа к Room и репозиториям. Вызовите [init] из [android.app.Application].
 */
object AppServices {
    lateinit var db: CourierDatabase
        private set

    lateinit var callStatusRepository: CallStatusRepository
        private set

    val isReady: Boolean get() = ::db.isInitialized

    fun init(context: Context) {
        if (::db.isInitialized) return
        val database = CourierDatabase.build(context)
        db = database
        callStatusRepository = CallStatusRepository(database.callStatusesDao())
    }
}
