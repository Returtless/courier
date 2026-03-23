package com.courierplanning

import android.app.Application

class CourierApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        AppServices.init(this)
    }
}
