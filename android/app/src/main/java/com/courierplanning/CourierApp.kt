package com.courierplanning

import android.app.Application
import com.courierplanning.data.db.AppDatabase

class CourierApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // Eager init DB so receivers/workers can reuse singleton safely.
        AppDatabase.get(this)
    }
}

