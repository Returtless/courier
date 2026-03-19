package com.courierplanning

import android.content.Context
import com.courierplanning.data.CallStatusRepository
import com.courierplanning.data.db.AppDatabase

object AppServices {
    @Volatile
    private var initialized = false

    lateinit var db: AppDatabase
        private set

    lateinit var callStatusRepository: CallStatusRepository
        private set

    fun init(context: Context) {
        if (initialized) return
        synchronized(this) {
            if (initialized) return
            db = AppDatabase.get(context)
            callStatusRepository = CallStatusRepository(context, db.callStatusDao())
            initialized = true
        }
    }
}

