package com.courierplanning.notifications

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.courierplanning.MainActivity
import com.courierplanning.data.db.AppDatabase
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Receives AlarmManager triggers for call notifications.
 *
 * For MVP: shows notification with basic actions.
 */
class CallAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val callStatusId = intent?.getLongExtra("callStatusId", -1L) ?: -1L
        if (callStatusId <= 0) return

        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val db = AppDatabase.get(context)
                val cs = db.callStatusDao().getById(callStatusId) ?: return@launch

                val openCalls = Intent(context, MainActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    putExtra("screen", "calls")
                    putExtra("callStatusId", callStatusId)
                }

                val contentPi = androidx.core.app.TaskStackBuilder.create(context)
                    .addNextIntentWithParentStack(openCalls)
                    .getPendingIntent(callStatusId.toInt(), android.app.PendingIntent.FLAG_UPDATE_CURRENT or android.app.PendingIntent.FLAG_IMMUTABLE)

                val notif = NotificationCompat.Builder(context, Notifications.CHANNEL_CALLS)
                    .setSmallIcon(android.R.drawable.ic_menu_call)
                    .setContentTitle("Пора звонить: №${cs.orderNumber}")
                    .setContentText(cs.phone)
                    .setPriority(NotificationCompat.PRIORITY_HIGH)
                    .setAutoCancel(true)
                    .setContentIntent(contentPi)
                    .build()

                NotificationManagerCompat.from(context).notify(callStatusId.toInt(), notif)
            } finally {
                pendingResult.finish()
            }
        }
    }
}

