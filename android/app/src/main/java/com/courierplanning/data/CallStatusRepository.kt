package com.courierplanning.data

import com.courierplanning.data.db.CallStatusEntity
import com.courierplanning.data.db.CallStatusesDao

/**
 * Сохранение статусов звонков; планирование WorkManager можно добавить позже.
 */
class CallStatusRepository(
    private val dao: CallStatusesDao,
) {
    suspend fun upsertAndSchedule(cs: CallStatusEntity) {
        dao.insert(cs)
    }
}
