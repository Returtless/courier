package com.courierplanning.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build

object Notifications {
    const val CHANNEL_CALLS = "calls"
    const val CHANNEL_ROUTE = "route"
    const val CHANNEL_IMPORT = "import"

    fun ensureChannels(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        val channels = listOf(
            NotificationChannel(CHANNEL_CALLS, "Звонки", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Уведомления о звонках по заказам"
            },
            NotificationChannel(CHANNEL_ROUTE, "Маршрут", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "Уведомления по маршруту"
            },
            NotificationChannel(CHANNEL_IMPORT, "Импорт", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Уведомления об импорте"
            },
        )
        nm.createNotificationChannels(channels)
    }
}

