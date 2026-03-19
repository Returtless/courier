package com.courierplanning.notifications

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager

/**
 * Restores scheduled call alarms/work after device reboot.
 * Implementation will be wired to Room (CallStatusEntity) later.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        // Schedule resync in background to avoid heavy work in receiver.
        val req = OneTimeWorkRequestBuilder<RescheduleCallsWorker>().build()
        WorkManager.getInstance(context).enqueue(req)
    }
}

