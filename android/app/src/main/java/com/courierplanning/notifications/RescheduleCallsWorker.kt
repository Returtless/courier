package com.courierplanning.notifications

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.courierplanning.data.db.AppDatabase
import com.courierplanning.data.db.CallStatusEntity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.temporal.ChronoUnit

class RescheduleCallsWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val db = AppDatabase.get(applicationContext)
        val now = Instant.now()
        val horizon = now.plus(24, ChronoUnit.HOURS)
        val active: List<CallStatusEntity> = db.callStatusDao().getActiveBetween(
            now.minus(1, ChronoUnit.HOURS).toString(),
            horizon.toString(),
        )
        active.forEach { cs ->
            val triggerIso = cs.nextAttemptIso ?: cs.callTimeIso
            CallAlarmScheduler.scheduleExact(applicationContext, cs.id, Instant.parse(triggerIso))
        }
        Result.success()
    }
}

