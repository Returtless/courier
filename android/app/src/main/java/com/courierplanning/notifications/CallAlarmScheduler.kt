package com.courierplanning.notifications

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import java.time.Instant

object CallAlarmScheduler {
    fun scheduleExact(context: Context, callStatusId: Long, triggerAt: Instant) {
        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pi = pendingIntent(context, callStatusId)
        val triggerAtMs = triggerAt.toEpochMilli()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && !am.canScheduleExactAlarms()) {
            // Fallback: use inexact alarm.
            am.set(AlarmManager.RTC_WAKEUP, triggerAtMs, pi)
            return
        }
        am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAtMs, pi)
    }

    fun cancel(context: Context, callStatusId: Long) {
        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        am.cancel(pendingIntent(context, callStatusId))
    }

    private fun pendingIntent(context: Context, callStatusId: Long): PendingIntent {
        val intent = Intent(context, CallAlarmReceiver::class.java).apply {
            action = "com.courierplanning.CALL_ALARM"
            putExtra("callStatusId", callStatusId)
        }
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        return PendingIntent.getBroadcast(context, callStatusId.toInt(), intent, flags)
    }
}

